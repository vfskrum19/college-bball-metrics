"""
Fetch KenPom data (teams, ratings, four factors, archive snapshots)

Run from project root:
    python scrapers/fetch_data.py               # Full sync
    python scrapers/fetch_data.py teams         # Teams only
    python scrapers/fetch_data.py ratings       # Ratings only
    python scrapers/fetch_data.py four-factors  # Four factors only
    python scrapers/fetch_data.py archive YYYY-MM-DD
"""

import os
import sys
from pathlib import Path
import requests
from datetime import datetime
import time

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from utils.db import get_db, close_db, execute, commit, insert_or_replace, db_type

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


def fetch_teams(season=CURRENT_SEASON):
    """Fetch all teams for a season (preserves branding data)"""
    print(f"Fetching teams for {season}...")
    data = make_request('teams', {'y': season})
    if not data:
        print("Failed to fetch teams")
        return

    db = get_db()

    # Save existing branding data before refresh
    existing_branding = {}
    try:
        rows = execute(db,
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
        pass

    execute(db, 'DELETE FROM teams WHERE season = ?', (season,))

    for team in data:
        team_id = team.get('TeamID')
        branding = existing_branding.get(team_id, {})
        execute(db, '''
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

    commit(db)
    close_db(db)
    print(f"✓ Inserted {len(data)} teams ({len(existing_branding)} with preserved branding)")


def fetch_ratings(season=CURRENT_SEASON):
    """Fetch current ratings for all teams"""
    print(f"Fetching ratings for {season}...")
    data = make_request('ratings', {'y': season})
    if not data:
        print("Failed to fetch ratings")
        return

    db = get_db()
    team_ids = {row['team_id'] for row in execute(db, 'SELECT team_id FROM teams WHERE season = ?', (season,)).fetchall()}

    execute(db, 'DELETE FROM ratings WHERE season = ?', (season,))

    inserted = 0
    for rating in data:
        team_name = rating.get('TeamName')
        team_result = execute(db, 'SELECT team_id FROM teams WHERE name = ? AND season = ?',
                              (team_name, season)).fetchone()
        if not team_result:
            continue
        team_id = team_result['team_id']
        if team_id not in team_ids:
            continue

        execute(db, '''
            INSERT INTO ratings (
                team_id, season, data_through, wins, losses,
                adj_em, rank_adj_em, adj_oe, rank_adj_oe, adj_de, rank_adj_de,
                tempo, rank_tempo, adj_tempo, rank_adj_tempo,
                luck, rank_luck, sos, rank_sos, ncsos, rank_ncsos
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            team_id, rating.get('Season'), rating.get('DataThrough'),
            rating.get('Wins'), rating.get('Losses'),
            rating.get('AdjEM'), rating.get('RankAdjEM'),
            rating.get('AdjOE'), rating.get('RankAdjOE'),
            rating.get('AdjDE'), rating.get('RankAdjDE'),
            rating.get('Tempo'), rating.get('RankTempo'),
            rating.get('AdjTempo'), rating.get('RankAdjTempo'),
            rating.get('Luck'), rating.get('RankLuck'),
            rating.get('SOS'), rating.get('RankSOS'),
            rating.get('NCSOS'), rating.get('RankNCSOS')
        ))
        inserted += 1

    commit(db)
    close_db(db)
    print(f"✓ Inserted {inserted} team ratings")


def fetch_four_factors(season=CURRENT_SEASON):
    """Fetch four factors for all teams"""
    print(f"Fetching four factors for {season}...")
    data = make_request('four-factors', {'y': season})
    if not data:
        print("Failed to fetch four factors")
        return

    db = get_db()
    execute(db, 'DELETE FROM four_factors WHERE season = ?', (season,))

    inserted = 0
    for ff in data:
        team_name = ff.get('TeamName')
        team_result = execute(db, 'SELECT team_id FROM teams WHERE name = ? AND season = ?',
                              (team_name, season)).fetchone()
        if not team_result:
            continue

        execute(db, '''
            INSERT INTO four_factors (
                team_id, season, data_through,
                efg_pct, rank_efg_pct, to_pct, rank_to_pct,
                or_pct, rank_or_pct, ft_rate, rank_ft_rate,
                defg_pct, rank_defg_pct, dto_pct, rank_dto_pct,
                dor_pct, rank_dor_pct, dft_rate, rank_dft_rate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            team_result['team_id'], ff.get('Season'), ff.get('DataThrough'),
            ff.get('eFG_Pct'), ff.get('RankeFG_Pct'),
            ff.get('TO_Pct'), ff.get('RankTO_Pct'),
            ff.get('OR_Pct'), ff.get('RankOR_Pct'),
            ff.get('FT_Rate'), ff.get('RankFT_Rate'),
            ff.get('DeFG_Pct'), ff.get('RankDeFG_Pct'),
            ff.get('DTO_Pct'), ff.get('RankDTO_Pct'),
            ff.get('DOR_Pct'), ff.get('RankDOR_Pct'),
            ff.get('DFT_Rate'), ff.get('RankDFT_Rate')
        ))
        inserted += 1

    commit(db)
    close_db(db)
    print(f"✓ Inserted {inserted} four factors records")


def fetch_archive_snapshot(date_str, season=CURRENT_SEASON):
    """Fetch and store a historical snapshot of ratings"""
    print(f"Fetching archive for {date_str}...")
    data = make_request('archive', {'d': date_str})
    if not data:
        print(f"Failed to fetch archive for {date_str}")
        return

    db = get_db()
    execute(db, 'DELETE FROM ratings_archive WHERE archive_date = ?', (date_str,))

    inserted = 0
    for rating in data:
        team_name = rating.get('TeamName')
        team_result = execute(db, 'SELECT team_id FROM teams WHERE name = ? AND season = ?',
                              (team_name, season)).fetchone()
        if not team_result:
            continue

        execute(db, '''
            INSERT INTO ratings_archive (
                team_id, season, archive_date, is_preseason,
                adj_em, rank_adj_em, adj_oe, rank_adj_oe,
                adj_de, rank_adj_de, adj_tempo, rank_adj_tempo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            team_result['team_id'], season,
            rating.get('ArchiveDate'),
            1 if rating.get('Preseason') == 'true' else 0,
            rating.get('AdjEM'), rating.get('RankAdjEM'),
            rating.get('AdjOE'), rating.get('RankAdjOE'),
            rating.get('AdjDE'), rating.get('RankAdjDE'),
            rating.get('AdjTempo'), rating.get('RankAdjTempo')
        ))
        inserted += 1

    commit(db)
    close_db(db)
    print(f"✓ Inserted {inserted} archive records for {date_str}")


def full_sync(season=CURRENT_SEASON):
    """Perform a full sync of all data"""
    print(f"\n{'='*50}")
    print(f"Starting full sync [{db_type()}] for {season} season")
    print(f"{'='*50}\n")

    fetch_teams(season)
    time.sleep(1)

    fetch_ratings(season)
    time.sleep(1)

    fetch_four_factors(season)
    time.sleep(1)

    # Preseason archive
    print("\nFetching preseason data...")
    preseason_data = make_request('archive', {'preseason': 'true', 'y': season})
    if preseason_data:
        db = get_db()
        for rating in preseason_data:
            team_name = rating.get('TeamName')
            team_result = execute(db, 'SELECT team_id FROM teams WHERE name = ? AND season = ?',
                                  (team_name, season)).fetchone()
            if not team_result:
                continue
            # insert_or_replace handles SQLite vs PostgreSQL upsert syntax
            insert_or_replace(db, 'ratings_archive',
                ['team_id', 'season', 'archive_date', 'is_preseason',
                 'adj_em', 'rank_adj_em', 'adj_oe', 'rank_adj_oe',
                 'adj_de', 'rank_adj_de', 'adj_tempo', 'rank_adj_tempo'],
                (team_result['team_id'], season, 'preseason', 1,
                 rating.get('AdjEM'), rating.get('RankAdjEM'),
                 rating.get('AdjOE'), rating.get('RankAdjOE'),
                 rating.get('AdjDE'), rating.get('RankAdjDE'),
                 rating.get('AdjTempo'), rating.get('RankAdjTempo')),
                conflict_columns=['team_id', 'season', 'archive_date']
            )
        commit(db)
        close_db(db)
        print(f"✓ Inserted preseason data")

    print(f"\n{'='*50}")
    print(f"Sync complete! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")


if __name__ == '__main__':
    if not KENPOM_API_KEY:
        print("⚠️  KENPOM_API_KEY not set in environment")
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
                fetch_archive_snapshot(sys.argv[2])
            else:
                print("Usage: python fetch_data.py archive YYYY-MM-DD")
        else:
            print("Unknown command. Use: teams, ratings, four-factors, or archive")
    else:
        full_sync()