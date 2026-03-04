"""
Fetch historical rating snapshots from KenPom Archive API
Stores periodic snapshots for calculating rating trajectory

Run from project root:
    python scrapers/fetch_momentum_ratings.py              # Fetch last 30 days
    python scrapers/fetch_momentum_ratings.py --days 45    # Fetch last 45 days
    python scrapers/fetch_momentum_ratings.py --date 2026-01-15
    python scrapers/fetch_momentum_ratings.py --stats
"""

import os
import sys
from pathlib import Path
import requests
from datetime import datetime, timedelta
import time
import argparse

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


def fetch_snapshot_for_date(date_str, season=CURRENT_SEASON):
    """
    Fetch rating snapshot for a specific date.
    Returns (inserted, skipped) tuple.
    """
    db = get_db()

    existing = execute(db,
        'SELECT COUNT(*) as c FROM momentum_ratings WHERE snapshot_date = ?',
        (date_str,)
    ).fetchone()['c']

    if existing > 0:
        close_db(db)
        return 0, existing

    data = make_request('archive', {'d': date_str})
    if not data:
        close_db(db)
        return 0, 0

    inserted = 0
    for rating in data:
        team_name = rating.get('TeamName')
        team_result = execute(db,
            'SELECT team_id FROM teams WHERE name = ? AND season = ?',
            (team_name, season)
        ).fetchone()

        if not team_result:
            continue

        try:
            execute(db, '''
                INSERT INTO momentum_ratings (
                    team_id, snapshot_date, season,
                    rank_adj_em, adj_em, adj_oe, adj_de,
                    rank_adj_oe, rank_adj_de
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                team_result['team_id'], date_str, season,
                rating.get('RankAdjEM'), rating.get('AdjEM'),
                rating.get('AdjOE'), rating.get('AdjDE'),
                rating.get('RankAdjOE'), rating.get('RankAdjDE')
            ))
            inserted += 1
        except Exception:
            pass  # Already exists

    commit(db)
    close_db(db)
    return inserted, 0


def fetch_ratings_range(days_back=30, interval=3, season=CURRENT_SEASON):
    """Fetch rating snapshots for a range of dates, every N days."""
    print(f"\n{'='*60}")
    print(f"Fetching KenPom Rating Snapshots [{db_type()}]")
    print(f"{'='*60}\n")

    if not KENPOM_API_KEY:
        print("❌ KENPOM_API_KEY not set in environment")
        return

    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back)

    dates_to_fetch = []
    current_date = start_date
    while current_date <= end_date:
        dates_to_fetch.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=interval)

    yesterday_str = end_date.strftime('%Y-%m-%d')
    start_str = start_date.strftime('%Y-%m-%d')

    if yesterday_str not in dates_to_fetch:
        dates_to_fetch.append(yesterday_str)
    if start_str not in dates_to_fetch:
        dates_to_fetch.insert(0, start_str)

    dates_to_fetch = sorted(set(dates_to_fetch))

    print(f"Date range: {start_str} to {yesterday_str}")
    print(f"Fetching {len(dates_to_fetch)} snapshots (every {interval} days)...\n")

    total_inserted = 0
    total_skipped = 0

    for date_str in dates_to_fetch:
        print(f"  {date_str}...", end=" ", flush=True)
        inserted, skipped = fetch_snapshot_for_date(date_str, season)

        if skipped > 0:
            print(f"⏭ already exists")
            total_skipped += 1
        elif inserted > 0:
            print(f"✓ {inserted} teams")
            total_inserted += inserted
        else:
            print("⚠ no data")

        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"  Snapshots fetched: {len(dates_to_fetch) - total_skipped}")
    print(f"  Teams inserted: {total_inserted}")
    print(f"  Dates skipped (already existed): {total_skipped}")
    print(f"{'='*60}\n")
    return total_inserted


def fetch_yesterday_snapshot(season=CURRENT_SEASON):
    """Fetch just yesterday's snapshot (most recent complete data)."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Fetching yesterday's snapshot ({yesterday})...")
    inserted, skipped = fetch_snapshot_for_date(yesterday, season)
    if skipped > 0:
        print(f"✓ Already have this snapshot")
    elif inserted > 0:
        print(f"✓ Inserted {inserted} team ratings")
    else:
        print("⚠ Could not fetch data")
    return inserted


def show_stats():
    db = get_db()
    total = execute(db, 'SELECT COUNT(*) as c FROM momentum_ratings').fetchone()['c']
    dates = execute(db, 'SELECT COUNT(DISTINCT snapshot_date) as c FROM momentum_ratings').fetchone()['c']
    date_range = execute(db, 'SELECT MIN(snapshot_date) as mn, MAX(snapshot_date) as mx FROM momentum_ratings').fetchone()
    recent = execute(db, '''
        SELECT snapshot_date, COUNT(*) as team_count
        FROM momentum_ratings
        GROUP BY snapshot_date
        ORDER BY snapshot_date DESC
        LIMIT 5
    ''').fetchall()
    close_db(db)

    print(f"\n{'='*60}")
    print(f"Momentum Ratings [{db_type()}]")
    print(f"{'='*60}")
    print(f"  Total rows: {total}  Unique dates: {dates}")
    if date_range and date_range['mn']:
        print(f"  Date range: {date_range['mn']} to {date_range['mx']}")
    if recent:
        print(f"\n  Recent snapshots:")
        for sd in recent:
            print(f"    {sd['snapshot_date']}: {sd['team_count']} teams")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch KenPom rating snapshots')
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--interval', type=int, default=3)
    parser.add_argument('--date', type=str, help='Fetch specific date (YYYY-MM-DD)')
    parser.add_argument('--today', action='store_true', help="Fetch yesterday's snapshot")
    parser.add_argument('--stats', action='store_true')
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.today:
        fetch_yesterday_snapshot()
    elif args.date:
        inserted, skipped = fetch_snapshot_for_date(args.date)
        print(f"✓ {inserted} inserted, {skipped} already existed")
    else:
        fetch_ratings_range(days_back=args.days, interval=args.interval)
        show_stats()