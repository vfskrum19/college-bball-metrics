"""
Fetch game predictions from KenPom Fanmatch API
Pulls daily game predictions for momentum tracking

Run from project root:
    python scrapers/fetch_games.py              # Fetch last 30 days
    python scrapers/fetch_games.py --days 45    # Fetch last 45 days
    python scrapers/fetch_games.py --date 2026-01-15  # Fetch specific date
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
import sqlite3
from datetime import datetime, timedelta
import time
import argparse

# Load environment variables
load_dotenv()

# Configuration
KENPOM_API_KEY = os.getenv('KENPOM_API_KEY')
BASE_URL = "https://kenpom.com"
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = 2026

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def make_request(endpoint, params):
    """Make request to KenPom API with authentication"""
    headers = {
        'Authorization': f'Bearer {KENPOM_API_KEY}'
    }
    
    url = f"{BASE_URL}/api.php"
    params['endpoint'] = endpoint
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {endpoint}: {e}")
        return None

def get_team_id_by_name(cursor, team_name, season=CURRENT_SEASON):
    """Look up team_id from team name"""
    result = cursor.execute(
        'SELECT team_id FROM teams WHERE name = ? AND season = ?',
        (team_name, season)
    ).fetchone()
    return result['team_id'] if result else None

def fetch_fanmatch_for_date(date_str, season=CURRENT_SEASON):
    """
    Fetch fanmatch predictions for a specific date
    Returns tuple of (inserted, skipped)
    """
    data = make_request('fanmatch', {'d': date_str})
    
    if not data:
        return 0, 0  # Return tuple for consistency
    
    db = get_db()
    cursor = db.cursor()
    
    inserted = 0
    skipped = 0
    
    for game in data:
        game_id = game.get('GameID')
        
        # Skip if game already exists
        existing = cursor.execute(
            'SELECT id FROM games WHERE game_id = ?', (game_id,)
        ).fetchone()
        
        if existing:
            skipped += 1
            continue
        
        # Look up team IDs
        home_name = game.get('Home')
        away_name = game.get('Visitor')
        
        home_team_id = get_team_id_by_name(cursor, home_name, season)
        away_team_id = get_team_id_by_name(cursor, away_name, season)
        
        if not home_team_id or not away_team_id:
            # Try to find close matches if exact match fails
            if not home_team_id:
                print(f"  ⚠ Could not find home team: {home_name}")
            if not away_team_id:
                print(f"  ⚠ Could not find away team: {away_name}")
            continue
        
        # Insert game with predictions (scores will be null until we fetch results)
        cursor.execute('''
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
            game_id,
            season,
            game.get('DateOfGame'),
            home_team_id,
            away_team_id,
            game.get('HomePred'),
            game.get('VisitorPred'),
            game.get('HomeWP'),
            game.get('PredTempo'),
            game.get('HomeRank'),
            game.get('VisitorRank'),
            game.get('ThrillScore')
        ))
        inserted += 1
    
    db.commit()
    db.close()
    
    return inserted, skipped

def fetch_games_range(days_back=30, season=CURRENT_SEASON):
    """
    Fetch fanmatch data for a range of dates
    """
    print(f"\n{'='*60}")
    print(f"Fetching KenPom Fanmatch Data")
    print(f"{'='*60}\n")
    
    if not KENPOM_API_KEY:
        print("❌ KENPOM_API_KEY not set in .env file")
        return
    
    end_date = datetime.now() - timedelta(days=1)  # Yesterday (today's games incomplete)
    start_date = end_date - timedelta(days=days_back)
    
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (yesterday)")
    print(f"Fetching {days_back} days of game data...")
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
        
        # Be nice to the API
        time.sleep(0.5)
        
        current_date += timedelta(days=1)
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Days processed: {days_back}")
    print(f"  Days with games: {days_with_games}")
    print(f"  Games inserted: {total_inserted}")
    print(f"  Games skipped (already existed): {total_skipped}")
    print(f"{'='*60}\n")
    
    return total_inserted

def get_games_missing_scores():
    """Get list of games that have predictions but no actual scores"""
    db = get_db()
    cursor = db.cursor()
    
    games = cursor.execute('''
        SELECT g.*, 
               ht.name as home_name, 
               at.name as away_name
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        WHERE g.home_score IS NULL 
          AND g.game_date < date('now')
        ORDER BY g.game_date DESC
    ''').fetchall()
    
    db.close()
    return games

def show_stats():
    """Show current games table statistics"""
    db = get_db()
    cursor = db.cursor()
    
    # Total games
    total = cursor.execute('SELECT COUNT(*) FROM games').fetchone()[0]
    
    # Games with scores
    with_scores = cursor.execute(
        'SELECT COUNT(*) FROM games WHERE home_score IS NOT NULL'
    ).fetchone()[0]
    
    # Games without scores (past games)
    missing_scores = cursor.execute('''
        SELECT COUNT(*) FROM games 
        WHERE home_score IS NULL AND game_date < date('now')
    ''').fetchone()[0]
    
    # Date range
    date_range = cursor.execute('''
        SELECT MIN(game_date), MAX(game_date) FROM games
    ''').fetchone()
    
    db.close()
    
    print(f"\n{'='*60}")
    print("Games Table Statistics")
    print(f"{'='*60}")
    print(f"  Total games: {total}")
    print(f"  With scores: {with_scores}")
    print(f"  Missing scores (past games): {missing_scores}")
    if date_range[0]:
        print(f"  Date range: {date_range[0]} to {date_range[1]}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch KenPom game predictions')
    parser.add_argument('--days', type=int, default=30, help='Number of days to fetch (default: 30)')
    parser.add_argument('--date', type=str, help='Fetch specific date (YYYY-MM-DD)')
    parser.add_argument('--stats', action='store_true', help='Show games table statistics')
    
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