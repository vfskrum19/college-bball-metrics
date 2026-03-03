"""
Fetch historical rating snapshots from KenPom Archive API
Stores periodic snapshots for calculating rating trajectory

Run from project root:
    python scrapers/fetch_momentum_ratings.py              # Fetch key dates for last 30 days
    python scrapers/fetch_momentum_ratings.py --days 45    # Fetch last 45 days
    python scrapers/fetch_momentum_ratings.py --date 2026-01-15  # Fetch specific date
    python scrapers/fetch_momentum_ratings.py --stats      # Show statistics
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

def fetch_snapshot_for_date(date_str, season=CURRENT_SEASON):
    """
    Fetch rating snapshot for a specific date
    Returns number of teams inserted
    """
    # Check if we already have this date
    db = get_db()
    cursor = db.cursor()
    
    existing = cursor.execute(
        'SELECT COUNT(*) FROM momentum_ratings WHERE snapshot_date = ?', 
        (date_str,)
    ).fetchone()[0]
    
    if existing > 0:
        db.close()
        return 0, existing  # Already have this date
    
    # Fetch from KenPom
    data = make_request('archive', {'d': date_str})
    
    if not data:
        db.close()
        return 0, 0
    
    inserted = 0
    
    for rating in data:
        team_name = rating.get('TeamName')
        
        # Look up team_id
        team_result = cursor.execute(
            'SELECT team_id FROM teams WHERE name = ? AND season = ?',
            (team_name, season)
        ).fetchone()
        
        if not team_result:
            continue
        
        team_id = team_result['team_id']
        
        # Insert snapshot
        try:
            cursor.execute('''
                INSERT INTO momentum_ratings (
                    team_id, snapshot_date, season,
                    rank_adj_em, adj_em, adj_oe, adj_de,
                    rank_adj_oe, rank_adj_de
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                team_id,
                date_str,
                season,
                rating.get('RankAdjEM'),
                rating.get('AdjEM'),
                rating.get('AdjOE'),
                rating.get('AdjDE'),
                rating.get('RankAdjOE'),
                rating.get('RankAdjDE')
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            # Already exists (shouldn't happen but just in case)
            pass
    
    db.commit()
    db.close()
    
    return inserted, 0

def fetch_ratings_range(days_back=30, interval=3, season=CURRENT_SEASON):
    """
    Fetch rating snapshots for a range of dates
    
    Args:
        days_back: How many days to go back
        interval: Fetch every N days (default 3 for efficiency)
    
    Note: We use YESTERDAY as the end date since today's data is incomplete
    (games still being played). Each snapshot is offset by 1 day to ensure
    we have complete data for that period.
    """
    print(f"\n{'='*60}")
    print(f"Fetching KenPom Rating Snapshots")
    print(f"{'='*60}\n")
    
    if not KENPOM_API_KEY:
        print("❌ KENPOM_API_KEY not set in .env file")
        return
    
    # Use YESTERDAY as end date (today's data is incomplete)
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back)
    
    # Calculate dates to fetch (every N days, offset by 1 to get complete data)
    dates_to_fetch = []
    current_date = start_date
    
    while current_date <= end_date:
        dates_to_fetch.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=interval)
    
    # Always include yesterday (most recent complete data) and the start date
    yesterday_str = end_date.strftime('%Y-%m-%d')
    start_str = start_date.strftime('%Y-%m-%d')
    
    if yesterday_str not in dates_to_fetch:
        dates_to_fetch.append(yesterday_str)
    if start_str not in dates_to_fetch:
        dates_to_fetch.insert(0, start_str)
    
    dates_to_fetch = sorted(set(dates_to_fetch))
    
    print(f"Date range: {start_str} to {yesterday_str} (yesterday)")
    print(f"Fetching {len(dates_to_fetch)} snapshots (every {interval} days)...\n")
    print(f"Note: Using yesterday as end date - today's data is incomplete\n")
    
    total_inserted = 0
    total_skipped = 0
    
    for date_str in dates_to_fetch:
        print(f"  {date_str}...", end=" ", flush=True)
        
        inserted, skipped = fetch_snapshot_for_date(date_str, season)
        
        if skipped > 0:
            print(f"⏭ already exists ({skipped} teams)")
            total_skipped += 1
        elif inserted > 0:
            print(f"✓ {inserted} teams")
            total_inserted += inserted
        else:
            print("⚠ no data")
        
        # Be nice to the API
        time.sleep(0.5)
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Dates processed: {len(dates_to_fetch)}")
    print(f"  New snapshots: {len(dates_to_fetch) - total_skipped}")
    print(f"  Teams inserted: {total_inserted}")
    print(f"  Dates skipped (already existed): {total_skipped}")
    print(f"{'='*60}\n")
    
    return total_inserted

def fetch_yesterday_snapshot(season=CURRENT_SEASON):
    """Quick function to fetch yesterday's snapshot (most recent complete data)"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Fetching yesterday's snapshot ({yesterday})...")
    print(f"Note: Using yesterday since today's games may still be in progress\n")
    inserted, skipped = fetch_snapshot_for_date(yesterday, season)
    
    if skipped > 0:
        print(f"✓ Already have today's snapshot")
    elif inserted > 0:
        print(f"✓ Inserted {inserted} team ratings")
    else:
        print("⚠ Could not fetch today's data")
    
    return inserted

def show_stats():
    """Show momentum_ratings table statistics"""
    db = get_db()
    cursor = db.cursor()
    
    # Total snapshots
    total = cursor.execute('SELECT COUNT(*) FROM momentum_ratings').fetchone()[0]
    
    # Unique dates
    dates = cursor.execute(
        'SELECT COUNT(DISTINCT snapshot_date) FROM momentum_ratings'
    ).fetchone()[0]
    
    # Date range
    date_range = cursor.execute('''
        SELECT MIN(snapshot_date), MAX(snapshot_date) FROM momentum_ratings
    ''').fetchone()
    
    # Snapshot dates
    snapshot_dates = cursor.execute('''
        SELECT snapshot_date, COUNT(*) as team_count
        FROM momentum_ratings
        GROUP BY snapshot_date
        ORDER BY snapshot_date DESC
        LIMIT 10
    ''').fetchall()
    
    # Sample trajectory for a top team
    sample = cursor.execute('''
        SELECT mr.snapshot_date, t.name, mr.rank_adj_em, mr.adj_em
        FROM momentum_ratings mr
        JOIN teams t ON mr.team_id = t.team_id
        WHERE t.name IN (
            SELECT t2.name FROM teams t2
            JOIN ratings r ON t2.team_id = r.team_id
            WHERE r.rank_adj_em <= 5
            LIMIT 1
        )
        ORDER BY mr.snapshot_date DESC
        LIMIT 5
    ''').fetchall()
    
    db.close()
    
    print(f"\n{'='*60}")
    print("Momentum Ratings Table Statistics")
    print(f"{'='*60}")
    print(f"  Total snapshots: {total}")
    print(f"  Unique dates: {dates}")
    if date_range[0]:
        print(f"  Date range: {date_range[0]} to {date_range[1]}")
    
    if snapshot_dates:
        print(f"\nRecent snapshots:")
        for sd in snapshot_dates[:5]:
            print(f"    {sd['snapshot_date']}: {sd['team_count']} teams")
    
    if sample:
        print(f"\nSample trajectory ({sample[0]['name']}):")
        for s in reversed(sample):
            print(f"    {s['snapshot_date']}: Rank #{s['rank_adj_em']} (AdjEM: {s['adj_em']:.2f})")
    
    print(f"{'='*60}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch KenPom rating snapshots')
    parser.add_argument('--days', type=int, default=30, help='Number of days to fetch (default: 30)')
    parser.add_argument('--interval', type=int, default=3, help='Days between snapshots (default: 3)')
    parser.add_argument('--date', type=str, help='Fetch specific date (YYYY-MM-DD)')
    parser.add_argument('--today', action='store_true', help='Fetch just today\'s snapshot')
    parser.add_argument('--stats', action='store_true', help='Show table statistics')
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
    elif args.today:
        fetch_yesterday_snapshot()
    elif args.date:
        print(f"Fetching snapshot for {args.date}...")
        inserted, skipped = fetch_snapshot_for_date(args.date)
        if skipped:
            print(f"✓ Already exists")
        else:
            print(f"✓ {inserted} teams inserted")
    else:
        fetch_ratings_range(days_back=args.days, interval=args.interval)
        show_stats()