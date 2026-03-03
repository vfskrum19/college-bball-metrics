"""
Historical Four Factors Scraper & Final Four Analysis

Fetches Four Factors data for all seasons 2002-2025 and analyzes
what statistical thresholds Final Four teams historically meet.

This powers the Championship Contender tier list feature.

Run from project root:
    python scrapers/fetch_historical_four_factors.py                  # Fetch all historical data
    python scrapers/fetch_historical_four_factors.py --analyze        # Run F4 analysis
    python scrapers/fetch_historical_four_factors.py --stats          # Show database stats
    python scrapers/fetch_historical_four_factors.py --year 2024      # Fetch specific year
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
import sqlite3
from datetime import datetime
import time
import argparse
import json

# Load environment variables
load_dotenv()

# Configuration
KENPOM_API_KEY = os.getenv('KENPOM_API_KEY')
BASE_URL = "https://kenpom.com"
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

# Selection Sunday dates (when brackets are revealed = pre-tournament snapshot)
SELECTION_SUNDAYS = {
    2002: "2002-03-10",
    2003: "2003-03-16",
    2004: "2004-03-14",
    2005: "2005-03-13",
    2006: "2006-03-12",
    2007: "2007-03-11",
    2008: "2008-03-16",
    2009: "2009-03-15",
    2010: "2010-03-14",
    2011: "2011-03-13",
    2012: "2012-03-11",
    2013: "2013-03-17",
    2014: "2014-03-16",
    2015: "2015-03-15",
    2016: "2016-03-13",
    2017: "2017-03-12",
    2018: "2018-03-11",
    2019: "2019-03-17",
    # 2020: No tournament
    2021: "2021-03-14",
    2022: "2022-03-13",
    2023: "2023-03-12",
    2024: "2024-03-17",
    2025: "2025-03-16",
}

# Historical Final Four teams with seeds (2002-2025)
# Format: {year: [(team_name, seed), ...]}
FINAL_FOUR_TEAMS = {
    2002: [("Maryland", 1), ("Kansas", 1), ("Indiana", 5), ("Oklahoma", 2)],
    2003: [("Texas", 1), ("Kansas", 2), ("Syracuse", 3), ("Marquette", 3)],
    2004: [("Duke", 1), ("Connecticut", 2), ("Georgia Tech", 3), ("Oklahoma St.", 2)],
    2005: [("Illinois", 1), ("North Carolina", 1), ("Louisville", 4), ("Michigan St.", 5)],
    2006: [("Florida", 3), ("UCLA", 2), ("LSU", 4), ("George Mason", 11)],
    2007: [("Florida", 1), ("UCLA", 2), ("Georgetown", 2), ("North Carolina", 1)],
    2008: [("Kansas", 1), ("Memphis", 1), ("UCLA", 1), ("North Carolina", 1)],
    2009: [("North Carolina", 1), ("Michigan St.", 2), ("Connecticut", 1), ("Villanova", 3)],
    2010: [("Duke", 1), ("Butler", 5), ("West Virginia", 2), ("Michigan St.", 5)],
    2011: [("Connecticut", 3), ("Butler", 8), ("Kentucky", 4), ("VCU", 11)],
    2012: [("Kentucky", 1), ("Kansas", 2), ("Ohio St.", 2), ("Louisville", 4)],
    2013: [("Louisville", 1), ("Michigan", 4), ("Syracuse", 4), ("Wichita St.", 9)],
    2014: [("Connecticut", 7), ("Kentucky", 8), ("Florida", 1), ("Wisconsin", 2)],
    2015: [("Duke", 1), ("Wisconsin", 1), ("Kentucky", 1), ("Michigan St.", 7)],
    2016: [("Villanova", 2), ("North Carolina", 1), ("Oklahoma", 2), ("Syracuse", 10)],
    2017: [("North Carolina", 1), ("Gonzaga", 1), ("Oregon", 3), ("South Carolina", 7)],
    2018: [("Villanova", 1), ("Michigan", 3), ("Kansas", 1), ("Loyola Chicago", 11)],
    2019: [("Virginia", 1), ("Texas Tech", 3), ("Michigan St.", 2), ("Auburn", 5)],
    # 2020: Tournament canceled - no data
    2021: [("Baylor", 1), ("Gonzaga", 1), ("UCLA", 11), ("Houston", 2)],
    2022: [("Kansas", 1), ("North Carolina", 8), ("Duke", 2), ("Villanova", 2)],
    2023: [("Connecticut", 4), ("San Diego St.", 5), ("Miami FL", 5), ("Florida Atlantic", 9)],
    2024: [("Connecticut", 1), ("Purdue", 1), ("Alabama", 4), ("N.C. State", 11)],
    2025: [("Florida", 1), ("Auburn", 1), ("Houston", 1), ("Duke", 1)],  # Seeds TBD, using 1 as placeholder
}

# Team name variations (KenPom uses different names sometimes)
TEAM_NAME_ALIASES = {
    "UConn": "Connecticut",
    "NC State": "N.C. State",
    "Oklahoma State": "Oklahoma St.",
    "Michigan State": "Michigan St.",
    "Ohio State": "Ohio St.",
    "Wichita State": "Wichita St.",
    "San Diego State": "San Diego St.",
    "Florida Atlantic": "Florida Atlantic",
}


def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def create_tables():
    """Create tables for historical four factors data"""
    db = get_db()
    cursor = db.cursor()
    
    # Historical Four Factors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historical_four_factors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            team_name TEXT NOT NULL,
            
            -- Offensive Four Factors (end-of-season)
            efg_pct REAL,
            rank_efg_pct INTEGER,
            to_pct REAL,
            rank_to_pct INTEGER,
            or_pct REAL,
            rank_or_pct INTEGER,
            ft_rate REAL,
            rank_ft_rate INTEGER,
            
            -- Defensive Four Factors (end-of-season)
            defg_pct REAL,
            rank_defg_pct INTEGER,
            dto_pct REAL,
            rank_dto_pct INTEGER,
            dor_pct REAL,
            rank_dor_pct INTEGER,
            dft_rate REAL,
            rank_dft_rate INTEGER,
            
            -- Efficiency ratings (PRE-TOURNAMENT from archive endpoint)
            adj_oe REAL,
            rank_adj_oe INTEGER,
            adj_de REAL,
            rank_adj_de INTEGER,
            adj_tempo REAL,
            rank_adj_tempo INTEGER,
            adj_em REAL,
            rank_adj_em INTEGER,
            
            -- Data source tracking
            four_factors_source TEXT DEFAULT 'end-of-season',
            efficiency_source TEXT,  -- Will store the Selection Sunday date
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(season, team_name)
        )
    ''')
    
    # Final Four analysis results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS final_four_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT NOT NULL,
            metric_display_name TEXT,
            
            -- Threshold analysis
            threshold_rank INTEGER,
            pct_f4_meeting_threshold REAL,
            
            -- Distribution stats
            median_rank REAL,
            avg_rank REAL,
            min_rank INTEGER,
            max_rank INTEGER,
            std_dev REAL,
            
            -- Percentile cutoffs
            pct_in_top_25 REAL,
            pct_in_top_50 REAL,
            pct_in_top_75 REAL,
            pct_in_top_100 REAL,
            
            sample_size INTEGER,
            years_analyzed TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(metric)
        )
    ''')
    
    # Championship contender current season scores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contender_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            team_name TEXT,
            
            -- Individual metric pass/fail (1 = meets threshold, 0 = doesn't)
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
            
            -- Summary
            metrics_met INTEGER DEFAULT 0,
            tier TEXT,  -- 'elite', 'strong', 'flawed', 'longshot'
            
            -- Current ranks for display
            rank_efg_pct INTEGER,
            rank_defg_pct INTEGER,
            rank_to_pct INTEGER,
            rank_dto_pct INTEGER,
            rank_or_pct INTEGER,
            rank_dor_pct INTEGER,
            rank_ft_rate INTEGER,
            rank_dft_rate INTEGER,
            rank_adj_oe INTEGER,
            rank_adj_de INTEGER,
            
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, season)
        )
    ''')
    
    db.commit()
    db.close()
    print("✓ Tables created/verified")


def make_request(endpoint, params):
    """Make request to KenPom API with authentication"""
    headers = {
        'Authorization': f'Bearer {KENPOM_API_KEY}'
    }
    
    url = f"{BASE_URL}/api.php"
    params['endpoint'] = endpoint
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {endpoint}: {e}")
        return None


def fetch_four_factors_for_year(year):
    """
    Fetch and store Four Factors for a specific year.
    
    Uses TWO data sources:
    1. four-factors endpoint → eFG%, TO%, OR%, FTRate (end-of-season only)
    2. archive endpoint → AdjOE, AdjDE, AdjTempo (pre-tournament Selection Sunday)
    """
    
    # Step 1: Get Four Factors (end-of-season)
    ff_data = make_request('four-factors', {'y': year})
    
    if not ff_data:
        print(f"⚠ No four-factors data for {year}")
        return 0
    
    # Step 2: Get pre-tournament efficiency from archive
    selection_date = SELECTION_SUNDAYS.get(year)
    archive_data = None
    archive_lookup = {}
    
    if selection_date:
        archive_data = make_request('archive', {'d': selection_date})
        if archive_data:
            # Create lookup by team name
            for team in archive_data:
                archive_lookup[team.get('TeamName')] = team
    
    db = get_db()
    cursor = db.cursor()
    
    inserted = 0
    for team in ff_data:
        team_name = team.get('TeamName')
        
        # Get pre-tournament efficiency if available
        archive_team = archive_lookup.get(team_name, {})
        
        # Use archive data for efficiency (pre-tournament), fall back to four-factors if not available
        adj_oe = archive_team.get('AdjOE') if archive_team else team.get('AdjOE')
        rank_adj_oe = archive_team.get('RankAdjOE') if archive_team else team.get('RankAdjOE')
        adj_de = archive_team.get('AdjDE') if archive_team else team.get('AdjDE')
        rank_adj_de = archive_team.get('RankAdjDE') if archive_team else team.get('RankAdjDE')
        adj_tempo = archive_team.get('AdjTempo') if archive_team else team.get('AdjTempo')
        rank_adj_tempo = archive_team.get('RankAdjTempo') if archive_team else team.get('RankAdjTempo')
        adj_em = archive_team.get('AdjEM') if archive_team else None
        rank_adj_em = archive_team.get('RankAdjEM') if archive_team else None
        
        efficiency_source = selection_date if archive_team else 'end-of-season'
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO historical_four_factors (
                    season, team_name,
                    efg_pct, rank_efg_pct, to_pct, rank_to_pct,
                    or_pct, rank_or_pct, ft_rate, rank_ft_rate,
                    defg_pct, rank_defg_pct, dto_pct, rank_dto_pct,
                    dor_pct, rank_dor_pct, dft_rate, rank_dft_rate,
                    adj_oe, rank_adj_oe, adj_de, rank_adj_de,
                    adj_tempo, rank_adj_tempo, adj_em, rank_adj_em,
                    four_factors_source, efficiency_source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                year,
                team_name,
                team.get('eFG_Pct'),
                team.get('RankeFG_Pct'),
                team.get('TO_Pct'),
                team.get('RankTO_Pct'),
                team.get('OR_Pct'),
                team.get('RankOR_Pct'),
                team.get('FT_Rate'),
                team.get('RankFT_Rate'),
                team.get('DeFG_Pct'),
                team.get('RankDeFG_Pct'),
                team.get('DTO_Pct'),
                team.get('RankDTO_Pct'),
                team.get('DOR_Pct'),
                team.get('RankDOR_Pct'),
                team.get('DFT_Rate'),
                team.get('RankDFT_Rate'),
                adj_oe,
                rank_adj_oe,
                adj_de,
                rank_adj_de,
                adj_tempo,
                rank_adj_tempo,
                adj_em,
                rank_adj_em,
                'end-of-season',
                efficiency_source,
            ))
            inserted += 1
        except sqlite3.Error as e:
            print(f"  Error inserting {team_name}: {e}")
    
    db.commit()
    db.close()
    
    return inserted, bool(archive_data)


def fetch_all_historical_data():
    """Fetch Four Factors for all historical seasons"""
    print("\n" + "="*60)
    print("Fetching Historical Four Factors (2002-2025)")
    print("="*60 + "\n")
    
    if not KENPOM_API_KEY:
        print("❌ KENPOM_API_KEY not set in .env file")
        return
    
    create_tables()
    
    total_inserted = 0
    years = list(range(2002, 2026))  # 2002-2025
    
    for year in years:
        if year == 2020:
            print(f"  {year}: ⏭ Skipped (COVID - no tournament)")
            continue
            
        print(f"  {year}...", end=" ", flush=True)
        result = fetch_four_factors_for_year(year)
        
        # Handle both old (int) and new (tuple) return values
        if isinstance(result, tuple):
            inserted, has_archive = result
        else:
            inserted, has_archive = result, False
        
        if inserted > 0:
            archive_status = "📅 pre-tournament" if has_archive else "📆 end-of-season"
            print(f"✓ {inserted} teams ({archive_status})")
            total_inserted += inserted
        else:
            print("⚠ no data")
        
        time.sleep(0.5)  # Be nice to API
    
    print(f"\n{'='*60}")
    print(f"Summary: {total_inserted} total team-seasons fetched")
    print(f"{'='*60}\n")
    
    return total_inserted


def normalize_team_name(name):
    """Normalize team name for matching"""
    return TEAM_NAME_ALIASES.get(name, name)


def analyze_final_four_thresholds():
    """
    Analyze historical CHAMPIONS to determine metric thresholds
    
    Based on analysis of 23 National Champions (2002-2025):
    - Only uses metrics that actually correlate with winning titles
    - Drops weak predictors (Forced TO%, FT Rate, Defensive Reb%, etc.)
    """
    print("\n" + "="*60)
    print("Championship Contender Thresholds (Based on 23 Champions)")
    print("="*60 + "\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # National Champions only (not all Final Four teams)
    NATIONAL_CHAMPIONS = {
        2002: "Maryland", 2003: "Syracuse", 2004: "Connecticut",
        2005: "North Carolina", 2006: "Florida", 2007: "Florida",
        2008: "Kansas", 2009: "North Carolina", 2010: "Duke",
        2011: "Connecticut", 2012: "Kentucky", 2013: "Louisville",
        2014: "Connecticut", 2015: "Duke", 2016: "Villanova",
        2017: "North Carolina", 2018: "Villanova", 2019: "Virginia",
        # 2020: Cancelled
        2021: "Baylor", 2022: "Kansas", 2023: "Connecticut",
        2024: "Connecticut", 2025: "Florida",
    }
    
    # Only metrics that actually predict champions
    # Format: (db_column, display_name, threshold, rationale)
    CHAMPION_THRESHOLDS = [
        ('rank_adj_em', 'Adjusted EM', 10, '87% of champs in top 10, 100% in top 25'),
        ('rank_adj_oe', 'Adjusted OE', 15, '74% of champs in top 10, 96% in top 25'),
        ('rank_adj_de', 'Adjusted DE', 40, '100% of champs in top 50'),
        ('rank_defg_pct', 'Defensive eFG%', 50, '78% of champs in top 50'),
        ('rank_efg_pct', 'Offensive eFG%', 75, '78% of champs in top 75'),
        ('rank_or_pct', 'Offensive Reb %', 50, '74% of champs in top 50'),
    ]
    
    print("Thresholds based on National Champions analysis:\n")
    print(f"{'Metric':<20} {'Threshold':<12} {'Rationale'}")
    print("-"*70)
    
    for col, name, threshold, rationale in CHAMPION_THRESHOLDS:
        print(f"{name:<20} Top {threshold:<8} {rationale}")
        
        # Save to database
        cursor.execute('''
            INSERT OR REPLACE INTO final_four_analysis (
                metric, metric_display_name, threshold_rank, 
                pct_f4_meeting_threshold, sample_size, years_analyzed
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (col, name, threshold, 85.0, 23, "Champions 2002-2025"))
    
    db.commit()
    db.close()
    
    print("\n" + "="*60)
    print("TIER CRITERIA")
    print("="*60)
    print("""
🏆 ELITE CONTENDER (5-6 metrics met)
   → Has the full championship DNA profile
   → Historically, this is what it takes to win it all

🎯 STRONG CONTENDER (4 metrics met)  
   → Missing 1-2 pieces but still dangerous
   → Could win with a hot tournament run

⚠️  FLAWED CONTENDER (2-3 metrics met)
   → Has some elite traits but significant gaps
   → Would need things to break right

❌ LONG SHOT (0-1 metrics met)
   → Doesn't match championship profile
   → Would be a historic outlier to win
""")
    
    return CHAMPION_THRESHOLDS


def calculate_current_contenders(season=2026):
    """
    Calculate which current teams meet the championship thresholds
    Uses only the 6 metrics that actually predict champions
    """
    print(f"\n{'='*60}")
    print(f"Calculating Championship Contender Scores ({season})")
    print("="*60 + "\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # Champion-validated thresholds (only metrics that matter)
    THRESHOLDS = {
        'rank_adj_em': 10,      # 87% of champs in top 10
        'rank_adj_oe': 15,      # 96% of champs in top 25
        'rank_adj_de': 40,      # 100% of champs in top 50
        'rank_defg_pct': 50,    # 78% of champs in top 50
        'rank_efg_pct': 75,     # 78% of champs in top 75
        'rank_or_pct': 50,      # 74% of champs in top 50
    }
    
    METRIC_NAMES = {
        'rank_adj_em': 'AdjEM',
        'rank_adj_oe': 'AdjOE', 
        'rank_adj_de': 'AdjDE',
        'rank_defg_pct': 'Def eFG%',
        'rank_efg_pct': 'Off eFG%',
        'rank_or_pct': 'Off Reb%',
    }
    
    print("Using champion-validated thresholds:")
    for metric, threshold in THRESHOLDS.items():
        print(f"  {METRIC_NAMES[metric]}: Top {threshold}")
    print()
    
    # Get current ratings - need to join four_factors with ratings for AdjEM
    current_teams = cursor.execute('''
        SELECT 
            t.team_id, t.name,
            ff.rank_efg_pct, ff.rank_defg_pct, ff.rank_or_pct,
            r.rank_adj_em, r.rank_adj_oe, r.rank_adj_de
        FROM teams t
        JOIN four_factors ff ON t.team_id = ff.team_id AND ff.season = t.season
        JOIN ratings r ON t.team_id = r.team_id AND r.season = t.season
        WHERE t.season = ?
    ''', (season,)).fetchall()
    
    if not current_teams:
        print(f"❌ No data for {season}. Run fetch_data.py first.")
        db.close()
        return
    
    results = []
    
    for team in current_teams:
        metrics_met = 0
        meets = {}
        ranks = {}
        
        # Check each threshold
        for metric_col, threshold in THRESHOLDS.items():
            rank = team[metric_col]
            ranks[metric_col] = rank
            
            if rank and rank <= threshold:
                meets[metric_col] = True
                metrics_met += 1
            else:
                meets[metric_col] = False
        
        # Determine tier (out of 6 metrics now)
        if metrics_met >= 5:
            tier = 'elite'
        elif metrics_met == 4:
            tier = 'strong'
        elif metrics_met >= 2:
            tier = 'flawed'
        else:
            tier = 'longshot'
        
        results.append({
            'team_id': team['team_id'],
            'team_name': team['name'],
            'metrics_met': metrics_met,
            'tier': tier,
            'meets': meets,
            'ranks': ranks,
        })
        
        # Update database
        cursor.execute('''
            INSERT OR REPLACE INTO contender_scores (
                team_id, season, team_name,
                meets_adj_oe, meets_adj_de, meets_efg_pct, 
                meets_defg_pct, meets_or_pct,
                metrics_met, tier,
                rank_adj_oe, rank_adj_de, rank_efg_pct,
                rank_defg_pct, rank_or_pct
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            team['team_id'], season, team['name'],
            1 if meets.get('rank_adj_oe') else 0,
            1 if meets.get('rank_adj_de') else 0,
            1 if meets.get('rank_efg_pct') else 0,
            1 if meets.get('rank_defg_pct') else 0,
            1 if meets.get('rank_or_pct') else 0,
            metrics_met, tier,
            ranks.get('rank_adj_oe'),
            ranks.get('rank_adj_de'),
            ranks.get('rank_efg_pct'),
            ranks.get('rank_defg_pct'),
            ranks.get('rank_or_pct'),
        ))
    
    db.commit()
    db.close()
    
    # Sort by metrics met, then by AdjEM rank
    results.sort(key=lambda x: (-x['metrics_met'], x['ranks'].get('rank_adj_em', 999)))
    
    # Print results by tier
    print("🏆 ELITE CONTENDERS (5-6 metrics)")
    print("-"*60)
    elite = [r for r in results if r['tier'] == 'elite']
    for r in elite:
        missing = [METRIC_NAMES[k] for k, v in r['meets'].items() if not v]
        missing_str = f" (missing: {', '.join(missing)})" if missing else " ✓ FULL PROFILE"
        print(f"  {r['team_name']}: {r['metrics_met']}/6{missing_str}")
    if not elite:
        print("  (none)")
    
    print(f"\n🎯 STRONG CONTENDERS (4 metrics)")
    print("-"*60)
    strong = [r for r in results if r['tier'] == 'strong']
    for r in strong[:15]:
        missing = [METRIC_NAMES[k] for k, v in r['meets'].items() if not v]
        print(f"  {r['team_name']}: {r['metrics_met']}/6 (missing: {', '.join(missing)})")
    if len(strong) > 15:
        print(f"  ... and {len(strong) - 15} more")
    if not strong:
        print("  (none)")
    
    print(f"\n⚠️  FLAWED CONTENDERS (2-3 metrics) - Top 15")
    print("-"*60)
    flawed = [r for r in results if r['tier'] == 'flawed']
    for r in flawed[:15]:
        has = [METRIC_NAMES[k] for k, v in r['meets'].items() if v]
        print(f"  {r['team_name']}: {r['metrics_met']}/6 (has: {', '.join(has)})")
    
    print(f"\n📊 Summary:")
    print(f"  🏆 Elite: {len(elite)} teams")
    print(f"  🎯 Strong: {len(strong)} teams")
    print(f"  ⚠️  Flawed: {len(flawed)} teams")
    print(f"  ❌ Long Shot: {len([r for r in results if r['tier'] == 'longshot'])} teams")
    
    return results


def show_stats():
    """Show database statistics"""
    db = get_db()
    cursor = db.cursor()
    
    print("\n" + "="*60)
    print("Historical Four Factors Database Stats")
    print("="*60)
    
    # Count records
    total = cursor.execute('SELECT COUNT(*) FROM historical_four_factors').fetchone()[0]
    seasons = cursor.execute('SELECT COUNT(DISTINCT season) FROM historical_four_factors').fetchone()[0]
    
    print(f"\n  Total records: {total}")
    print(f"  Seasons: {seasons}")
    
    # Season breakdown
    print("\n  Records per season:")
    rows = cursor.execute('''
        SELECT season, COUNT(*) as cnt, efficiency_source
        FROM historical_four_factors 
        GROUP BY season 
        ORDER BY season DESC
        LIMIT 10
    ''').fetchall()
    
    for row in rows:
        source_icon = "📅" if row['efficiency_source'] and row['efficiency_source'] != 'end-of-season' else "📆"
        print(f"    {row['season']}: {row['cnt']} teams {source_icon}")
    
    print("\n  📅 = pre-tournament efficiency | 📆 = end-of-season only")
    
    # Check Final Four coverage
    print("\n  Final Four coverage:")
    total_f4 = 0
    found_f4 = 0
    
    for year, teams in FINAL_FOUR_TEAMS.items():
        if year == 2020:
            continue
        for team_name, seed in teams:
            total_f4 += 1
            normalized = normalize_team_name(team_name)
            row = cursor.execute('''
                SELECT COUNT(*) FROM historical_four_factors
                WHERE season = ? AND (team_name = ? OR team_name = ?)
            ''', (year, team_name, normalized)).fetchone()
            if row[0] > 0:
                found_f4 += 1
    
    print(f"    Found: {found_f4}/{total_f4} Final Four teams ({found_f4/total_f4*100:.1f}%)")
    
    # Analysis results
    analysis = cursor.execute('SELECT COUNT(*) FROM final_four_analysis').fetchone()[0]
    print(f"\n  Analysis results: {analysis} metrics analyzed")
    
    # Contender scores
    contenders = cursor.execute('SELECT COUNT(*) FROM contender_scores WHERE season = 2026').fetchone()[0]
    print(f"  Current contender scores: {contenders} teams")
    
    db.close()
    print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Historical Four Factors & Championship Contender Analysis')
    parser.add_argument('--year', type=int, help='Fetch specific year only')
    parser.add_argument('--analyze', action='store_true', help='Run Final Four threshold analysis')
    parser.add_argument('--contenders', action='store_true', help='Calculate current contender scores')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--all', action='store_true', help='Run full pipeline: fetch, analyze, score')
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
    elif args.year:
        create_tables()
        print(f"Fetching {args.year}...")
        result = fetch_four_factors_for_year(args.year)
        if isinstance(result, tuple):
            inserted, has_archive = result
        else:
            inserted, has_archive = result, False
        archive_note = " (with pre-tournament efficiency)" if has_archive else " (end-of-season only)"
        print(f"✓ {inserted} teams inserted{archive_note}")
    elif args.analyze:
        analyze_final_four_thresholds()
    elif args.contenders:
        calculate_current_contenders()
    elif args.all:
        fetch_all_historical_data()
        analyze_final_four_thresholds()
        calculate_current_contenders()
    else:
        # Default: fetch all historical data
        fetch_all_historical_data()