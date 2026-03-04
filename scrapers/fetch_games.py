"""
Fetch game predictions from KenPom Fanmatch API
Pulls daily game predictions for momentum tracking

Run from project root:
    python scrapers/fetch_games.py              # Fetch last 30 days
    python scrapers/fetch_games.py --days 45    # Fetch last 45 days
    python scrapers/fetch_games.py --date 2026-01-15  # Fetch specific date
"""

import os
import sys
from pathlib import Path
import requests
from datetime import datetime, timedelta
import time
import argparse

# ============================================================
# DATABASE SETUP
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from utils.db import get_db, close_db, execute, commit, db_type

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

KENPOM_API_KEY = os.getenv('KENPOM_API_KEY')
BASE_URL = "https://kenpom.com"
CURRENT_SEASON = 2026


def make_request(endpoint, params):
    headers = {'Authorization': f'Bearer {KENPOM_API_KEY}'}
    url = f"{BASE_URL}/api.php"
    params['endpoint'] = endpoint
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {endpoint}: {e}")
        return None


def get_team_id_by_name(db, team_name, season=CURRENT_SEASON):
    result = execute(db, 
        'SELECT team_id FROM teams WHERE name = ? AND season = ?',
        (team_name, season)
    ).fetchone()
    return result['team_id'] if result else None


def fetch_fanmatch_for_date(date_str, season=CURRENT_SEASON):
    """Fetch fanmatch predictions for a specific date. Returns (inserted, skipped)."""
    data = make_request('fanmatch', {'d': date_str})
    if not data:
        return 0, 0

    db = get_db()
    inserted = 0
    skipped = 0

    for game in data:
        game_id = game.get('GameID')

        existing = execute(db, 'SELECT id FROM games WHERE game_id = ?', (game_id,)).fetchone()
        if existing:
            skipped += 1
            continue

        home_name = game.get('Home')
        away_name = game.get('Visitor')
        home_team_id = get_team_id_by_name(db, home_name, season)
        away_team_id = get_team_id_by_name(db, away_name, season)

        if not home_team_id or not away_team_id:
            if not home_team_id: print(f"  ⚠ Could not find home team: {home_name}")
            if not away_team_id: print(f"  ⚠ Could not find away team: {away_name}")
            continue

        execute(db, '''
            INSERT INTO games (
                game_id, season, game_date,
                home_team_id, away_team_id,
                home_pred, away_pred,
                home_win_prob, pred_tempo,
                home_rank, away_rank,
                thrill_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            game_id, season, game.get('DateOfGame'),
            home_team_id, away_team_id,
            game.get('HomePred'), game.get('VisitorPred'),
            game.get('HomeWP'), game.get('PredTempo'),
            game.get('HomeRank'), game.get('VisitorRank'),
            game.get('ThrillScore')
        ))
        inserted += 1

    commit(db)
    close_db(db)
    return inserted, skipped


def fetch_games_range(days_back=30, season=CURRENT_SEASON):
    print(f"\n{'='*60}")
    print(f"Fetching KenPom Fanmatch Data [{db_type()}]")
    print(f"{'='*60}\n")

    if not KENPOM_API_KEY:
        print("❌ KENPOM_API_KEY not set in environment")
        return

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back)

    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Note: Using yesterday as end date - today's games may be incomplete\n")

    total_inserted = 0
    total_skipped = 0
    days_with_games = 0

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        print(f"  {date_str}...", end=" ", flush=True)

        inserted, skipped = fetch_fanmatch_for_date(date_str, season)

        if inserted > 0 or skipped > 0:
            print(f"✓ {inserted} new, {skipped} existing")
            days_with_games += 1
        else:
            print("no games")

        total_inserted += inserted
        total_skipped += skipped
        time.sleep(0.5)
        current_date += timedelta(days=1)

    print(f"\n{'='*60}")
    print(f"  Days processed: {days_back}")
    print(f"  Days with games: {days_with_games}")
    print(f"  Games inserted: {total_inserted}")
    print(f"  Games already existed: {total_skipped}")
    print(f"{'='*60}\n")
    return total_inserted


def show_stats():
    db = get_db()
    total = execute(db, 'SELECT COUNT(*) as c FROM games').fetchone()['c']
    with_scores = execute(db, 'SELECT COUNT(*) as c FROM games WHERE home_score IS NOT NULL').fetchone()['c']
    missing = execute(db, "SELECT COUNT(*) as c FROM games WHERE home_score IS NULL AND game_date < CURRENT_DATE").fetchone()['c']
    date_range = execute(db, 'SELECT MIN(game_date) as mn, MAX(game_date) as mx FROM games').fetchone()
    close_db(db)

    print(f"\n{'='*60}")
    print(f"Games Table Statistics [{db_type()}]")
    print(f"{'='*60}")
    print(f"  Total games: {total}")
    print(f"  With scores: {with_scores}")
    print(f"  Missing scores (past games): {missing}")
    if date_range and date_range['mn']:
        print(f"  Date range: {date_range['mn']} to {date_range['mx']}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch KenPom game predictions')
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--date', type=str, help='Fetch specific date (YYYY-MM-DD)')
    parser.add_argument('--stats', action='store_true')
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.date:
        print(f"Fetching games for {args.date}...")
        inserted, skipped = fetch_fanmatch_for_date(args.date)
        print(f"✓ {inserted} games inserted, {skipped} skipped")
    else:
        fetch_games_range(days_back=args.days)
        show_stats()