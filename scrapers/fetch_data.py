import os
from pathlib import Path
from dotenv import load_dotenv
import requests
import sqlite3
import json
from datetime import datetime
import time

# Load environment variables from .env file
load_dotenv()

# Configuration
KENPOM_API_KEY = os.getenv('KENPOM_API_KEY')
BASE_URL = "https://kenpom.com"
# Get project root (parent of this file's directory)
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

def fetch_teams(season=CURRENT_SEASON):
    """Fetch all teams for a season (preserves branding data)"""
    print(f"Fetching teams for {season}...")
    data = make_request('teams', {'y': season})
    
    if not data:
        print("Failed to fetch teams")
        return
    
    db = get_db()
    cursor = db.cursor()
    
    # Save existing branding data before refresh
    existing_branding = {}
    try:
        rows = cursor.execute(
            'SELECT team_id, logo_url, primary_color, secondary_color FROM teams WHERE season = ?',
            (season,)
        ).fetchall()
        for row in rows:
            existing_branding[row['team_id']] = {
                'logo_url': row['logo_url'],
                'primary_color': row['primary_color'],
                'secondary_color': row['secondary_color']
            }
    except Exception:
        pass  # Columns might not exist yet
    
    # Clear existing teams for this season
    cursor.execute('DELETE FROM teams WHERE season = ?', (season,))
    
    # Insert teams, restoring branding if it existed
    for team in data:
        team_id = team.get('TeamID')
        branding = existing_branding.get(team_id, {})
        cursor.execute('''
            INSERT INTO teams (team_id, name, conference, coach, arena, arena_city, arena_state, season,
                               logo_url, primary_color, secondary_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            team_id,
            team.get('TeamName'),
            team.get('ConfShort'),
            team.get('Coach'),
            team.get('Arena'),
            team.get('ArenaCity'),
            team.get('ArenaState'),
            season,
            branding.get('logo_url'),
            branding.get('primary_color'),
            branding.get('secondary_color')
        ))
    
    db.commit()
    db.close()
    print(f"✓ Inserted {len(data)} teams ({len(existing_branding)} with preserved branding)")

def fetch_ratings(season=CURRENT_SEASON):
    """Fetch current ratings for all teams"""
    print(f"Fetching ratings for {season}...")
    data = make_request('ratings', {'y': season})
    
    if not data:
        print("Failed to fetch ratings")
        return
    
    db = get_db()
    cursor = db.cursor()
    
    # Get all team IDs from database
    teams = cursor.execute('SELECT team_id FROM teams WHERE season = ?', (season,)).fetchall()
    team_ids = {team['team_id'] for team in teams}
    
    # Clear old ratings for this season
    cursor.execute('DELETE FROM ratings WHERE season = ?', (season,))
    
    # Insert new ratings
    inserted = 0
    for rating in data:
        team_id = None
        # Find team_id by name (since API returns TeamName but not TeamID in ratings)
        team_name = rating.get('TeamName')
        team_result = cursor.execute('SELECT team_id FROM teams WHERE name = ? AND season = ?', 
                                     (team_name, season)).fetchone()
        if team_result:
            team_id = team_result['team_id']
        
        if team_id and team_id in team_ids:
            cursor.execute('''
                INSERT INTO ratings (
                    team_id, season, data_through, wins, losses,
                    adj_em, rank_adj_em, adj_oe, rank_adj_oe, adj_de, rank_adj_de,
                    tempo, rank_tempo, adj_tempo, rank_adj_tempo,
                    luck, rank_luck, sos, rank_sos, ncsos, rank_ncsos
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                team_id,
                rating.get('Season'),
                rating.get('DataThrough'),
                rating.get('Wins'),
                rating.get('Losses'),
                rating.get('AdjEM'),
                rating.get('RankAdjEM'),
                rating.get('AdjOE'),
                rating.get('RankAdjOE'),
                rating.get('AdjDE'),
                rating.get('RankAdjDE'),
                rating.get('Tempo'),
                rating.get('RankTempo'),
                rating.get('AdjTempo'),
                rating.get('RankAdjTempo'),
                rating.get('Luck'),
                rating.get('RankLuck'),
                rating.get('SOS'),
                rating.get('RankSOS'),
                rating.get('NCSOS'),
                rating.get('RankNCSOS')
            ))
            inserted += 1
    
    db.commit()
    db.close()
    print(f"✓ Inserted {inserted} team ratings")

def fetch_four_factors(season=CURRENT_SEASON):
    """Fetch four factors for all teams"""
    print(f"Fetching four factors for {season}...")
    data = make_request('four-factors', {'y': season})
    
    if not data:
        print("Failed to fetch four factors")
        return
    
    db = get_db()
    cursor = db.cursor()
    
    # Clear old four factors for this season
    cursor.execute('DELETE FROM four_factors WHERE season = ?', (season,))
    
    # Insert new four factors
    inserted = 0
    for ff in data:
        team_name = ff.get('TeamName')
        team_result = cursor.execute('SELECT team_id FROM teams WHERE name = ? AND season = ?', 
                                     (team_name, season)).fetchone()
        
        if team_result:
            team_id = team_result['team_id']
            cursor.execute('''
                INSERT INTO four_factors (
                    team_id, season, data_through,
                    efg_pct, rank_efg_pct, to_pct, rank_to_pct,
                    or_pct, rank_or_pct, ft_rate, rank_ft_rate,
                    defg_pct, rank_defg_pct, dto_pct, rank_dto_pct,
                    dor_pct, rank_dor_pct, dft_rate, rank_dft_rate
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                team_id,
                ff.get('Season'),
                ff.get('DataThrough'),
                ff.get('eFG_Pct'),
                ff.get('RankeFG_Pct'),
                ff.get('TO_Pct'),
                ff.get('RankTO_Pct'),
                ff.get('OR_Pct'),
                ff.get('RankOR_Pct'),
                ff.get('FT_Rate'),
                ff.get('RankFT_Rate'),
                ff.get('DeFG_Pct'),
                ff.get('RankDeFG_Pct'),
                ff.get('DTO_Pct'),
                ff.get('RankDTO_Pct'),
                ff.get('DOR_Pct'),
                ff.get('RankDOR_Pct'),
                ff.get('DFT_Rate'),
                ff.get('RankDFT_Rate')
            ))
            inserted += 1
    
    db.commit()
    db.close()
    print(f"✓ Inserted {inserted} four factors records")

def fetch_archive_snapshot(date_str, season=CURRENT_SEASON):
    """Fetch and store a historical snapshot of ratings"""
    print(f"Fetching archive for {date_str}...")
    data = make_request('archive', {'d': date_str})
    
    if not data:
        print(f"Failed to fetch archive for {date_str}")
        return
    
    db = get_db()
    cursor = db.cursor()
    
    # Delete existing archive data for this date
    cursor.execute('DELETE FROM ratings_archive WHERE archive_date = ?', (date_str,))
    
    inserted = 0
    for rating in data:
        team_name = rating.get('TeamName')
        team_result = cursor.execute('SELECT team_id FROM teams WHERE name = ? AND season = ?', 
                                     (team_name, season)).fetchone()
        
        if team_result:
            team_id = team_result['team_id']
            cursor.execute('''
                INSERT INTO ratings_archive (
                    team_id, season, archive_date, is_preseason,
                    adj_em, rank_adj_em, adj_oe, rank_adj_oe,
                    adj_de, rank_adj_de, adj_tempo, rank_adj_tempo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                team_id,
                season,
                rating.get('ArchiveDate'),
                rating.get('Preseason') == 'true',
                rating.get('AdjEM'),
                rating.get('RankAdjEM'),
                rating.get('AdjOE'),
                rating.get('RankAdjOE'),
                rating.get('AdjDE'),
                rating.get('RankAdjDE'),
                rating.get('AdjTempo'),
                rating.get('RankAdjTempo')
            ))
            inserted += 1
    
    db.commit()
    db.close()
    print(f"✓ Inserted {inserted} archive records for {date_str}")

def full_sync(season=CURRENT_SEASON):
    """Perform a full sync of all data"""
    print(f"\n{'='*50}")
    print(f"Starting full sync for {season} season")
    print(f"{'='*50}\n")
    
    # Step 1: Fetch teams (required first to get team IDs)
    fetch_teams(season)
    time.sleep(1)  # Be nice to the API
    
    # Step 2: Fetch current ratings
    fetch_ratings(season)
    time.sleep(1)
    
    # Step 3: Fetch four factors
    fetch_four_factors(season)
    time.sleep(1)
    
    # Step 4: Fetch preseason archive (optional but useful)
    print("\nFetching preseason data...")
    preseason_data = make_request('archive', {'preseason': 'true', 'y': season})
    if preseason_data:
        db = get_db()
        cursor = db.cursor()
        for rating in preseason_data:
            team_name = rating.get('TeamName')
            team_result = cursor.execute('SELECT team_id FROM teams WHERE name = ? AND season = ?', 
                                         (team_name, season)).fetchone()
            if team_result:
                team_id = team_result['team_id']
                cursor.execute('''
                    INSERT OR REPLACE INTO ratings_archive (
                        team_id, season, archive_date, is_preseason,
                        adj_em, rank_adj_em, adj_oe, rank_adj_oe,
                        adj_de, rank_adj_de, adj_tempo, rank_adj_tempo
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    team_id, season, 'preseason', True,
                    rating.get('AdjEM'), rating.get('RankAdjEM'),
                    rating.get('AdjOE'), rating.get('RankAdjOE'),
                    rating.get('AdjDE'), rating.get('RankAdjDE'),
                    rating.get('AdjTempo'), rating.get('RankAdjTempo')
                ))
        db.commit()
        db.close()
        print(f"✓ Inserted preseason data")
    
    print(f"\n{'='*50}")
    print(f"Sync complete! Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

if __name__ == '__main__':
    import sys
    
    if not KENPOM_API_KEY:
        print("⚠️  Please set your KENPOM_API_KEY in the .env file")
        print("   Create a .env file in the project root with:")
        print("   KENPOM_API_KEY=your_api_key_here")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'teams':
            fetch_teams()
        elif command == 'ratings':
            fetch_ratings()
        elif command == 'four-factors':
            fetch_four_factors()
        elif command == 'archive':
            if len(sys.argv) > 2:
                date_str = sys.argv[2]  # Format: YYYY-MM-DD
                fetch_archive_snapshot(date_str)
            else:
                print("Usage: python fetch_data.py archive YYYY-MM-DD")
        else:
            print("Unknown command. Use: teams, ratings, four-factors, or archive")
    else:
        # Default: full sync
        full_sync()