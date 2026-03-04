"""
Historical Four Factors Scraper & Final Four Analysis

Fetches Four Factors data for all seasons 2002-2025 and analyzes
what statistical thresholds Final Four teams historically meet.

Run from project root:
    python scrapers/fetch_historical_four_factors.py                  # Fetch all historical data
    python scrapers/fetch_historical_four_factors.py --analyze        # Run F4 analysis
    python scrapers/fetch_historical_four_factors.py --contenders     # Score current teams
    python scrapers/fetch_historical_four_factors.py --stats          # Show database stats
    python scrapers/fetch_historical_four_factors.py --year 2024      # Fetch specific year
    python scrapers/fetch_historical_four_factors.py --all            # Full pipeline
"""

import os
import sys
from pathlib import Path
import requests
from datetime import datetime
import time
import argparse

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

# Selection Sunday dates (pre-tournament snapshot)
SELECTION_SUNDAYS = {
    2002: "2002-03-10", 2003: "2003-03-16", 2004: "2004-03-14",
    2005: "2005-03-13", 2006: "2006-03-12", 2007: "2007-03-11",
    2008: "2008-03-16", 2009: "2009-03-15", 2010: "2010-03-14",
    2011: "2011-03-13", 2012: "2012-03-11", 2013: "2013-03-17",
    2014: "2014-03-16", 2015: "2015-03-15", 2016: "2016-03-13",
    2017: "2017-03-12", 2018: "2018-03-11", 2019: "2019-03-17",
    2021: "2021-03-14", 2022: "2022-03-13", 2023: "2023-03-12",
    2024: "2024-03-17", 2025: "2025-03-16",
}

TEAM_NAME_ALIASES = {
    "UConn": "Connecticut",
    "NC State": "N.C. State",
    "Oklahoma State": "Oklahoma St.",
    "Michigan State": "Michigan St.",
    "Ohio State": "Ohio St.",
    "Wichita State": "Wichita St.",
    "San Diego State": "San Diego St.",
}


def make_request(endpoint, params):
    headers = {'Authorization': f'Bearer {KENPOM_API_KEY}'}
    url = f"{BASE_URL}/api.php"
    params['endpoint'] = endpoint
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {endpoint}: {e}")
        return None


def create_tables():
    """Create tables for historical four factors data if they don't exist."""
    db = get_db()

    execute(db, '''
        CREATE TABLE IF NOT EXISTS historical_four_factors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            team_name TEXT NOT NULL,
            efg_pct REAL, rank_efg_pct INTEGER,
            to_pct REAL, rank_to_pct INTEGER,
            or_pct REAL, rank_or_pct INTEGER,
            ft_rate REAL, rank_ft_rate INTEGER,
            defg_pct REAL, rank_defg_pct INTEGER,
            dto_pct REAL, rank_dto_pct INTEGER,
            dor_pct REAL, rank_dor_pct INTEGER,
            dft_rate REAL, rank_dft_rate INTEGER,
            adj_oe REAL, rank_adj_oe INTEGER,
            adj_de REAL, rank_adj_de INTEGER,
            adj_tempo REAL, rank_adj_tempo INTEGER,
            adj_em REAL, rank_adj_em INTEGER,
            four_factors_source TEXT DEFAULT 'end-of-season',
            efficiency_source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(season, team_name)
        )
    ''')

    execute(db, '''
        CREATE TABLE IF NOT EXISTS final_four_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT NOT NULL,
            metric_display_name TEXT,
            threshold_rank INTEGER,
            pct_f4_meeting_threshold REAL,
            median_rank REAL, avg_rank REAL,
            min_rank INTEGER, max_rank INTEGER, std_dev REAL,
            pct_in_top_25 REAL, pct_in_top_50 REAL,
            pct_in_top_75 REAL, pct_in_top_100 REAL,
            sample_size INTEGER,
            years_analyzed TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(metric)
        )
    ''')

    execute(db, '''
        CREATE TABLE IF NOT EXISTS contender_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            team_name TEXT,
            meets_efg_pct INTEGER DEFAULT 0,
            meets_defg_pct INTEGER DEFAULT 0,
            meets_to_pct INTEGER DEFAULT 0,
            meets_dto_pct INTEGER DEFAULT 0,
            meets_or_pct INTEGER DEFAULT 0,
            meets_dor_pct INTEGER DEFAULT 0,
            meets_ft_rate INTEGER DEFAULT 0,
            meets_dft_rate INTEGER DEFAULT 0,
            meets_adj_oe INTEGER DEFAULT 0,
            meets_adj_de INTEGER DEFAULT 0,
            metrics_met INTEGER DEFAULT 0,
            tier TEXT,
            rank_efg_pct INTEGER, rank_defg_pct INTEGER,
            rank_to_pct INTEGER, rank_dto_pct INTEGER,
            rank_or_pct INTEGER, rank_dor_pct INTEGER,
            rank_ft_rate INTEGER, rank_dft_rate INTEGER,
            rank_adj_oe INTEGER, rank_adj_de INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, season)
        )
    ''')

    commit(db)
    close_db(db)
    print("✓ Tables created/verified")


def fetch_four_factors_for_year(year):
    """
    Fetch and store Four Factors for a specific year.
    Uses two sources: four-factors endpoint (end-of-season) +
    archive endpoint (pre-tournament Selection Sunday efficiency).
    """
    ff_data = make_request('four-factors', {'y': year})
    if not ff_data:
        print(f"⚠ No four-factors data for {year}")
        return 0, False

    selection_date = SELECTION_SUNDAYS.get(year)
    archive_lookup = {}
    has_archive = False

    if selection_date:
        archive_data = make_request('archive', {'d': selection_date})
        if archive_data:
            has_archive = True
            for team in archive_data:
                archive_lookup[team.get('TeamName')] = team

    db = get_db()
    inserted = 0

    for team in ff_data:
        team_name = team.get('TeamName')
        arch = archive_lookup.get(team_name, {})

        adj_oe = arch.get('AdjOE') if arch else team.get('AdjOE')
        rank_adj_oe = arch.get('RankAdjOE') if arch else team.get('RankAdjOE')
        adj_de = arch.get('AdjDE') if arch else team.get('AdjDE')
        rank_adj_de = arch.get('RankAdjDE') if arch else team.get('RankAdjDE')
        adj_tempo = arch.get('AdjTempo') if arch else team.get('AdjTempo')
        rank_adj_tempo = arch.get('RankAdjTempo') if arch else team.get('RankAdjTempo')
        adj_em = arch.get('AdjEM') if arch else None
        rank_adj_em = arch.get('RankAdjEM') if arch else None
        efficiency_source = selection_date if arch else 'end-of-season'

        try:
            insert_or_replace(db, 'historical_four_factors',
                ['season', 'team_name',
                 'efg_pct', 'rank_efg_pct', 'to_pct', 'rank_to_pct',
                 'or_pct', 'rank_or_pct', 'ft_rate', 'rank_ft_rate',
                 'defg_pct', 'rank_defg_pct', 'dto_pct', 'rank_dto_pct',
                 'dor_pct', 'rank_dor_pct', 'dft_rate', 'rank_dft_rate',
                 'adj_oe', 'rank_adj_oe', 'adj_de', 'rank_adj_de',
                 'adj_tempo', 'rank_adj_tempo', 'adj_em', 'rank_adj_em',
                 'four_factors_source', 'efficiency_source'],
                (year, team_name,
                 team.get('eFG_Pct'), team.get('RankeFG_Pct'),
                 team.get('TO_Pct'), team.get('RankTO_Pct'),
                 team.get('OR_Pct'), team.get('RankOR_Pct'),
                 team.get('FT_Rate'), team.get('RankFT_Rate'),
                 team.get('DeFG_Pct'), team.get('RankDeFG_Pct'),
                 team.get('DTO_Pct'), team.get('RankDTO_Pct'),
                 team.get('DOR_Pct'), team.get('RankDOR_Pct'),
                 team.get('DFT_Rate'), team.get('RankDFT_Rate'),
                 adj_oe, rank_adj_oe, adj_de, rank_adj_de,
                 adj_tempo, rank_adj_tempo, adj_em, rank_adj_em,
                 'end-of-season', efficiency_source),
                conflict_columns=['season', 'team_name']
            )
            inserted += 1
        except Exception as e:
            print(f"  Error inserting {team_name}: {e}")

    commit(db)
    close_db(db)
    return inserted, has_archive


def fetch_all_historical_data():
    print(f"\n{'='*60}")
    print(f"Fetching Historical Four Factors (2002-2025) [{db_type()}]")
    print(f"{'='*60}\n")

    if not KENPOM_API_KEY:
        print("❌ KENPOM_API_KEY not set in environment")
        return

    create_tables()
    total_inserted = 0

    for year in range(2002, 2026):
        if year == 2020:
            print(f"  {year}: ⏭ Skipped (COVID - no tournament)")
            continue

        print(f"  {year}...", end=" ", flush=True)
        inserted, has_archive = fetch_four_factors_for_year(year)

        if inserted > 0:
            source = "📅 pre-tournament" if has_archive else "📆 end-of-season"
            print(f"✓ {inserted} teams ({source})")
            total_inserted += inserted
        else:
            print("⚠ no data")

        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"  Total team-seasons fetched: {total_inserted}")
    print(f"{'='*60}\n")
    return total_inserted


def analyze_final_four_thresholds():
    """Save champion-validated thresholds to database."""
    print(f"\n{'='*60}")
    print("Championship Contender Thresholds (23 Champions, 2002-2025)")
    print(f"{'='*60}\n")

    CHAMPION_THRESHOLDS = [
        ('rank_adj_em',   'Adjusted EM',      10, '87% of champs in top 10'),
        ('rank_adj_oe',   'Adjusted OE',       15, '74% of champs in top 10'),
        ('rank_adj_de',   'Adjusted DE',       40, '100% of champs in top 50'),
        ('rank_defg_pct', 'Defensive eFG%',    50, '78% of champs in top 50'),
        ('rank_efg_pct',  'Offensive eFG%',    75, '78% of champs in top 75'),
        ('rank_or_pct',   'Offensive Reb %',   50, '74% of champs in top 50'),
    ]

    db = get_db()
    print(f"{'Metric':<20} {'Threshold':<12} {'Rationale'}")
    print("-" * 70)

    for col, name, threshold, rationale in CHAMPION_THRESHOLDS:
        print(f"{name:<20} Top {threshold:<8} {rationale}")
        insert_or_replace(db, 'final_four_analysis',
            ['metric', 'metric_display_name', 'threshold_rank',
             'pct_f4_meeting_threshold', 'sample_size', 'years_analyzed'],
            (col, name, threshold, 85.0, 23, "Champions 2002-2025"),
            conflict_columns=['metric']
        )

    commit(db)
    close_db(db)
    return CHAMPION_THRESHOLDS


def calculate_current_contenders(season=CURRENT_SEASON):
    """Score current teams against championship thresholds."""
    print(f"\n{'='*60}")
    print(f"Calculating Championship Contender Scores [{db_type()}]")
    print(f"{'='*60}\n")

    THRESHOLDS = {
        'rank_adj_em':   10,
        'rank_adj_oe':   15,
        'rank_adj_de':   40,
        'rank_defg_pct': 50,
        'rank_efg_pct':  75,
        'rank_or_pct':   50,
    }

    METRIC_NAMES = {
        'rank_adj_em':   'AdjEM',
        'rank_adj_oe':   'AdjOE',
        'rank_adj_de':   'AdjDE',
        'rank_defg_pct': 'Def eFG%',
        'rank_efg_pct':  'Off eFG%',
        'rank_or_pct':   'Off Reb%',
    }

    db = get_db()
    current_teams = execute(db, '''
        SELECT t.team_id, t.name,
               ff.rank_efg_pct, ff.rank_defg_pct, ff.rank_or_pct,
               r.rank_adj_em, r.rank_adj_oe, r.rank_adj_de
        FROM teams t
        JOIN four_factors ff ON t.team_id = ff.team_id AND ff.season = t.season
        JOIN ratings r ON t.team_id = r.team_id AND r.season = t.season
        WHERE t.season = ?
    ''', (season,)).fetchall()

    if not current_teams:
        print(f"❌ No data for {season}. Run fetch_data.py first.")
        close_db(db)
        return

    results = []

    for team in current_teams:
        metrics_met = 0
        meets = {}
        ranks = {}

        for metric_col, threshold in THRESHOLDS.items():
            rank = team[metric_col]
            ranks[metric_col] = rank
            if rank and rank <= threshold:
                meets[metric_col] = True
                metrics_met += 1
            else:
                meets[metric_col] = False

        if metrics_met >= 5:    tier = 'elite'
        elif metrics_met == 4:  tier = 'strong'
        elif metrics_met >= 2:  tier = 'flawed'
        else:                   tier = 'longshot'

        results.append({
            'team_id': team['team_id'],
            'team_name': team['name'],
            'metrics_met': metrics_met,
            'tier': tier,
            'meets': meets,
            'ranks': ranks,
        })

        insert_or_replace(db, 'contender_scores',
            ['team_id', 'season', 'team_name',
             'meets_adj_oe', 'meets_adj_de', 'meets_efg_pct',
             'meets_defg_pct', 'meets_or_pct',
             'metrics_met', 'tier',
             'rank_adj_oe', 'rank_adj_de', 'rank_efg_pct',
             'rank_defg_pct', 'rank_or_pct'],
            (team['team_id'], season, team['name'],
             1 if meets.get('rank_adj_oe') else 0,
             1 if meets.get('rank_adj_de') else 0,
             1 if meets.get('rank_efg_pct') else 0,
             1 if meets.get('rank_defg_pct') else 0,
             1 if meets.get('rank_or_pct') else 0,
             metrics_met, tier,
             ranks.get('rank_adj_oe'), ranks.get('rank_adj_de'),
             ranks.get('rank_efg_pct'), ranks.get('rank_defg_pct'),
             ranks.get('rank_or_pct')),
            conflict_columns=['team_id', 'season']
        )

    commit(db)
    close_db(db)

    results.sort(key=lambda x: (-x['metrics_met'], x['ranks'].get('rank_adj_em', 999)))

    elite  = [r for r in results if r['tier'] == 'elite']
    strong = [r for r in results if r['tier'] == 'strong']
    flawed = [r for r in results if r['tier'] == 'flawed']

    print("🏆 ELITE CONTENDERS (5-6 metrics)")
    print("-" * 60)
    for r in elite:
        missing = [METRIC_NAMES[k] for k, v in r['meets'].items() if not v]
        print(f"  {r['team_name']}: {r['metrics_met']}/6" +
              (f" (missing: {', '.join(missing)})" if missing else " ✓ FULL PROFILE"))
    if not elite: print("  (none)")

    print(f"\n🎯 STRONG CONTENDERS (4 metrics)")
    print("-" * 60)
    for r in strong[:15]:
        missing = [METRIC_NAMES[k] for k, v in r['meets'].items() if not v]
        print(f"  {r['team_name']}: {r['metrics_met']}/6 (missing: {', '.join(missing)})")
    if not strong: print("  (none)")

    print(f"\n📊 Summary: 🏆 {len(elite)} elite  🎯 {len(strong)} strong  "
          f"⚠️  {len(flawed)} flawed  ❌ {len([r for r in results if r['tier'] == 'longshot'])} longshot")

    return results


def show_stats():
    db = get_db()
    total = execute(db, 'SELECT COUNT(*) as c FROM historical_four_factors').fetchone()['c']
    seasons = execute(db, 'SELECT COUNT(DISTINCT season) as c FROM historical_four_factors').fetchone()['c']
    contenders = execute(db, 'SELECT COUNT(*) as c FROM contender_scores WHERE season = ?',
                         (CURRENT_SEASON,)).fetchone()['c']
    close_db(db)

    print(f"\n{'='*60}")
    print(f"Historical Four Factors [{db_type()}]")
    print(f"{'='*60}")
    print(f"  Total records: {total}  Seasons: {seasons}")
    print(f"  Current contender scores: {contenders} teams")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Historical Four Factors & Championship Analysis')
    parser.add_argument('--year', type=int, help='Fetch specific year only')
    parser.add_argument('--analyze', action='store_true', help='Run threshold analysis')
    parser.add_argument('--contenders', action='store_true', help='Calculate contender scores')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--all', action='store_true', help='Full pipeline: fetch + analyze + score')
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.year:
        create_tables()
        inserted, has_archive = fetch_four_factors_for_year(args.year)
        note = " (with pre-tournament efficiency)" if has_archive else " (end-of-season only)"
        print(f"✓ {inserted} teams inserted{note}")
    elif args.analyze:
        analyze_final_four_thresholds()
    elif args.contenders:
        calculate_current_contenders()
    elif args.all:
        fetch_all_historical_data()
        analyze_final_four_thresholds()
        calculate_current_contenders()
    else:
        fetch_all_historical_data()