"""
Fetch actual game scores from ESPN API
Updates games table with real scores to compare against KenPom predictions

Run from project root:
    python scrapers/fetch_game_scores_espn.py              # Update all missing scores
    python scrapers/fetch_game_scores_espn.py --stats      # Show statistics
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
import sqlite3
from datetime import datetime, timedelta
import time
import argparse
import json

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = 2026

# ESPN API endpoints
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

# KenPom to ESPN name mappings for teams that don't match automatically
# Values are lowercase for matching against normalized ESPN names
KENPOM_TO_ESPN = {
    # Around line 29, add these to the existing dictionary:
    'Albany': 'ualbany',
    'American': 'american university',
    'Gardner-Webb': 'gardner-webb runnin',  # You already have this one, keep it
    'Seattle': 'seattle u',
    'Central Connecticut': 'central connecticut',  # or try 'central connecticut state'
    'Southeast Missouri': 'southeast missouri state',
    'Middle Tennessee': 'middle tennessee blue',
    'Stony Brook': 'stony brook',  # Should already work, but verify
    'UC Davis': 'uc davis',
    'Seattle': 'seattle u',
    'American': 'american university',
    'Tarleton St.': 'tarleton state',  # You already have 'Tarleton' mapped
    'UMass Lowell': 'umass lowell',

    # ACC
    'Florida St.': 'florida state',
    'N.C. State': 'nc state',
    
    # Big Ten
    'Michigan St.': 'michigan state',
    'Ohio St.': 'ohio state',
    'Penn St.': 'penn state',
    
    # Big 12
    'Arizona St.': 'arizona state',
    'Iowa St.': 'iowa state',
    'Kansas St.': 'kansas state',
    'Oklahoma St.': 'oklahoma state',
    
    # Big East
    'Connecticut': 'uconn',
    
    # SEC
    'Mississippi': 'ole miss',
    'Mississippi St.': 'mississippi state',
    'South Carolina St.': 'south carolina state',
    
    # ACC / Pac-12 / other major
    'Miami FL': 'miami',
    'USC': 'usc',
    'Central Connecticut': 'central connecticut',
    
    # Mountain West
    'Boise St.': 'boise state',
    'Colorado St.': 'colorado state',
    'Fresno St.': 'fresno state',
    'San Diego St.': 'san diego state',
    'San Jose St.': 'san jose state',
    'Utah St.': 'utah state',
    
    # MAC
    'Miami OH': 'miami (oh)',
    'Ball St.': 'ball state',
    'Kent St.': 'kent state',
    
    # Big Sky
    'Idaho St.': 'idaho state',
    'Montana St.': 'montana state',
    'Portland St.': 'portland state',
    'Sacramento St.': 'sacramento state',
    'Weber St.': 'weber state',
    
    # Big West
    'CSUN': 'cal state northridge',
    'Cal St. Bakersfield': 'cal state bakersfield',
    'Cal St. Fullerton': 'cal state fullerton',
    'Long Beach St.': 'long beach state',
    'Hawaii': "hawai'i",
    
    # Conference USA
    'FIU': 'florida international',
    'Jacksonville St.': 'jacksonville state',
    'Kennesaw St.': 'kennesaw state',
    'Missouri St.': 'missouri state',
    'New Mexico St.': 'new mexico state',
    'Sam Houston St.': 'sam houston',
    'Sam Houston': 'sam houston',
    
    # Horizon
    'Cleveland St.': 'cleveland state',
    'IU Indy': 'iu indianapolis',
    'Wright St.': 'wright state',
    'Youngstown St.': 'youngstown state',
    
    # MEAC
    'Coppin St.': 'coppin state',
    'Delaware St.': 'delaware state',
    'Morgan St.': 'morgan state',
    'Norfolk St.': 'norfolk state',
    
    # MVC
    'Illinois Chicago': 'uic',
    'Illinois St.': 'illinois state',
    'Indiana St.': 'indiana state',
    'Murray St.': 'murray state',
    'Wichita St.': 'wichita state',
    
    # NEC
    'Chicago St.': 'chicago state',
    'LIU': 'long island university',
    
    # Ivy League
    'Penn': 'pennsylvania',
    
    # OVC
    'Morehead St.': 'morehead state',
    'SIUE': 'siu edwardsville',
    'Tennessee Martin': 'ut martin',
    'Tennessee St.': 'tennessee state',
    
    # Patriot League
    'Loyola MD': 'loyola maryland',
    
    # Sun Belt
    'Appalachian St.': 'app state',
    'Arkansas St.': 'arkansas state',
    'Georgia St.': 'georgia state',
    'Louisiana Monroe': 'ul monroe',
    'Louisiana': 'louisiana',
    'Texas St.': 'texas state',
    'Coastal Carolina': 'coastal carolina',
    
    # Southern
    'East Tennessee St.': 'east tennessee state',
    
    # SWAC
    'Alabama St.': 'alabama state',
    'Alcorn St.': 'alcorn state',
    'Arkansas Pine Bluff': 'arkansas-pine bluff',
    'Bethune Cookman': 'bethune-cookman',
    'Jackson St.': 'jackson state',
    'Grambling St.': 'grambling',
    'Mississippi Valley St.': 'mississippi valley state',
    
    # Southland
    'Northwestern St.': 'northwestern state',
    'Southeastern Louisiana': 'se louisiana',
    'Texas A&M Corpus Chris': 'texas a&m-corpus christi',
    'Nicholls St.': 'nicholls',
    
    # Summit
    'Nebraska Omaha': 'omaha',
    'North Dakota St.': 'north dakota state',
    'South Dakota St.': 'south dakota state',
    'St. Thomas': 'st. thomas-minnesota',
    
    # WAC
    'Cal Baptist': 'california baptist',
    'Tarleton St.': 'tarleton state',
    'Tarleton': 'tarleton state',
    'UT Rio Grande Valley': 'ut rio grande valley',
    
    # WCC
    'Oregon St.': 'oregon state',
    'Washington St.': 'washington state',
    
    # Other
    'Gardner Webb': 'gardner-webb',
    'USC Upstate': 'south carolina upstate',
    'Queens': 'queens university',
}

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def fetch_espn_scores_for_date(date_str):
    """
    Fetch all game scores from ESPN for a specific date
    Returns dict of {(team1, team2): {home_score, away_score, home_team, away_team}}
    """
    try:
        # ESPN uses YYYYMMDD format
        espn_date = date_str.replace('-', '')
        
        params = {
            'dates': espn_date,
            'groups': 50,    # Get all Division I games
            'limit': 400     # Ensure we get all games for the day
        }
        
        response = requests.get(ESPN_SCOREBOARD_URL, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        games = {}
        
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            
            # Get competitors
            competitors = competition.get('competitors', [])
            if len(competitors) != 2:
                continue
            
            # Check if game is completed
            status = event.get('status', {}).get('type', {}).get('completed', False)
            if not status:
                continue
            
            home_team = None
            away_team = None
            home_score = None
            away_score = None
            
            for comp in competitors:
                team_name = comp.get('team', {}).get('displayName', '')
                score = comp.get('score')
                is_home = comp.get('homeAway') == 'home'
                
                if score:
                    score = int(score)
                
                if is_home:
                    home_team = team_name
                    home_score = score
                else:
                    away_team = team_name
                    away_score = score
            
            if home_team and away_team and home_score is not None and away_score is not None:
                # Store with both orderings for easier lookup
                games[(home_team.lower(), away_team.lower())] = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': home_score,
                    'away_score': away_score
                }
        
        return games
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ESPN data for {date_str}: {e}")
        return {}

def normalize_team_name(name):
    """Basic normalization: lowercase, strip, handle special chars"""
    name = name.lower().strip()
    name = name.replace('\u00e9', 'e').replace('\u00f1', 'n').replace('\u2019', "'")
    return name


def strip_mascot(name):
    """
    Strip mascot from an ESPN display name.
    ESPN format is always: "School Name Mascot(s)"
    Strategy: try known multi-word mascots first, then strip last word.
    """
    # Multi-word mascots (last word alone would leave a partial name)
    multi_word_mascots = [
        " ragin' cajuns", ' blue devils', ' tar heels', ' crimson tide',
        ' yellow jackets', ' demon deacons', ' fighting irish', ' golden gophers',
        ' red raiders', ' horned frogs', ' sun devils', ' wolf pack',
        ' running rebels', ' rainbow warriors', ' mean green', ' red wolves',
        ' golden lions', ' black knights', ' fighting camels', ' golden griffins',
        ' blue hens', ' fighting illini', ' golden flashes', ' mountain hawks',
        ' black bears', ' red foxes', ' golden eagles', ' great danes',
        ' river hawks', ' purple eagles', ' fighting hawks', ' blue hose',
        ' big red', ' big green', ' golden hurricane', ' red storm',
        ' golden grizzlies', ' green wave', ' thundering herd', ' blue demons',
        ' nittany lions', ' delta devils', ' golden suns', ' red flash',
        ' scarlet knights', ' golden bears', ' screaming eagles',
        ' purple aces', " runnin' bulldogs",
    ]
    
    for mascot in multi_word_mascots:
        if name.endswith(mascot):
            return name[:-len(mascot)].strip()
    
    # Single-word mascots: just strip the last word
    # This handles ALL single-word mascots (bulldogs, zips, monarchs, billikens, etc.)
    parts = name.rsplit(' ', 1)
    if len(parts) == 2 and len(parts[0]) >= 2:
        return parts[0].strip()
    
    return name


def names_match(kenpom_name, espn_raw_name):
    """
    Check if a KenPom name matches an ESPN raw lowercased display name.
    VERY STRICT matching - NO fuzzy logic to prevent catastrophic mismatches.
    """
    kp = normalize_team_name(kenpom_name)
    espn = normalize_team_name(espn_raw_name)
    
    # Strategy 1: Exact match
    if kp == espn:
        return True
    
    # Strategy 2: Match after stripping mascot from ESPN name  
    espn_stripped = strip_mascot(espn)
    if kp == espn_stripped:
        return True
    
    # Strategy 3: REMOVED - fuzzy matching causes too many false positives
    # If a team doesn't match above, it should fail rather than match wrong team
    
    return False


def update_scores_from_espn():
    """
    Update games table with actual scores from ESPN
    """
    print(f"\n{'='*60}")
    print("Fetching Actual Game Scores from ESPN")
    print(f"{'='*60}\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # Get all dates with games missing scores
    dates = cursor.execute('''
        SELECT DISTINCT game_date 
        FROM games 
        WHERE home_score IS NULL 
          AND game_date < date('now')
        ORDER BY game_date
    ''').fetchall()
    
    print(f"Found {len(dates)} dates with games needing scores\n")
    
    total_updated = 0
    dates_processed = 0
    
    # Build team name lookup
    teams = cursor.execute('SELECT team_id, name FROM teams WHERE season = ?', (CURRENT_SEASON,)).fetchall()
    team_name_to_id = {t['name'].lower(): t['team_id'] for t in teams}
    team_id_to_name = {t['team_id']: t['name'] for t in teams}
    
    for date_row in dates:
        game_date = date_row['game_date']
        dates_processed += 1
        
        print(f"  [{dates_processed}/{len(dates)}] {game_date}...", end=" ", flush=True)
        
        # Fetch ESPN scores for this date
        espn_games = fetch_espn_scores_for_date(game_date)
        
        if not espn_games:
            print("no ESPN data")
            time.sleep(0.3)
            continue
        
        # Get our games for this date that need scores
        our_games = cursor.execute('''
            SELECT g.id, g.game_id, g.home_team_id, g.away_team_id,
                   ht.name as home_name, at.name as away_name
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            WHERE g.game_date = ?
              AND g.home_score IS NULL
        ''', (game_date,)).fetchall()
        
        games_updated = 0
        
        for game in our_games:
            home_name = game['home_name']
            away_name = game['away_name']
            
            # Convert KenPom names to ESPN format using mapping
            home_mapped = KENPOM_TO_ESPN.get(home_name, home_name)
            away_mapped = KENPOM_TO_ESPN.get(away_name, away_name)
            
            matched = None
            
            for (espn_home, espn_away), scores in espn_games.items():
                # Try normal order
                if names_match(home_mapped, espn_home) and names_match(away_mapped, espn_away):
                    matched = scores
                    break
                
                # Try swapped home/away
                if names_match(home_mapped, espn_away) and names_match(away_mapped, espn_home):
                    matched = {
                        'home_score': scores['away_score'],
                        'away_score': scores['home_score']
                    }
                    break
            
            if matched:
                cursor.execute('''
                    UPDATE games 
                    SET home_score = ?, away_score = ?
                    WHERE id = ?
                ''', (matched['home_score'], matched['away_score'], game['id']))
                games_updated += 1
        
        db.commit()
        
        if games_updated > 0 and games_updated == len(our_games):
            print(f"✓ {games_updated} games updated")
        elif games_updated > 0:
            print(f"✓ {games_updated}/{len(our_games)} games updated")
            # Show what failed
            for game in our_games:
                h_mapped = KENPOM_TO_ESPN.get(game['home_name'], game['home_name'])
                a_mapped = KENPOM_TO_ESPN.get(game['away_name'], game['away_name'])
                # Check if this one matched by seeing if it still has NULL score
                check = cursor.execute('SELECT home_score FROM games WHERE id = ?', (game['id'],)).fetchone()
                if check['home_score'] is None:
                    print(f"    MISS: '{game['home_name']}'->'{normalize_team_name(h_mapped)}' vs '{game['away_name']}'->'{normalize_team_name(a_mapped)}'")
        else:
            print(f"0 matched (had {len(our_games)} games, ESPN had {len(espn_games)})")
            # Show what failed to match for debugging
            for game in our_games[:3]:
                h_mapped = KENPOM_TO_ESPN.get(game['home_name'], game['home_name'])
                a_mapped = KENPOM_TO_ESPN.get(game['away_name'], game['away_name'])
                h_norm = normalize_team_name(h_mapped)
                a_norm = normalize_team_name(a_mapped)
                print(f"    MISS: '{game['home_name']}'->'{h_norm}' vs '{game['away_name']}'->'{a_norm}'")
                # Show closest ESPN matches
                for (eh, ea), s in espn_games.items():
                    ehn = strip_mascot(normalize_team_name(eh))
                    ean = strip_mascot(normalize_team_name(ea))
                    if h_norm in ehn or ehn in h_norm or a_norm in ean or ean in a_norm:
                        print(f"      ESPN has: '{eh}'->'{ehn}' vs '{ea}'->'{ean}'")
        
        total_updated += games_updated
        
        # Small delay to be nice to ESPN
        time.sleep(0.3)
    
    db.close()
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Dates processed: {dates_processed}")
    print(f"  Games updated with scores: {total_updated}")
    print(f"{'='*60}\n")
    
    return total_updated

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
    
    # Sample of games with scores
    sample = cursor.execute('''
        SELECT g.game_date, ht.name as home, at.name as away,
               g.home_score, g.away_score, g.home_pred, g.away_pred
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        WHERE g.home_score IS NOT NULL
        ORDER BY g.game_date DESC
        LIMIT 5
    ''').fetchall()
    
    db.close()
    
    print(f"\n{'='*60}")
    print("Games Table Statistics")
    print(f"{'='*60}")
    print(f"  Total games: {total}")
    print(f"  With scores: {with_scores}")
    print(f"  Missing scores (past games): {missing_scores}")
    if date_range[0]:
        print(f"  Date range: {date_range[0]} to {date_range[1]}")
    
    if sample:
        print(f"\nRecent games with scores:")
        for g in sample:
            actual = f"{g['home_score']}-{g['away_score']}"
            pred = f"{g['home_pred']:.0f}-{g['away_pred']:.0f}" if g['home_pred'] else "N/A"
            margin_actual = g['home_score'] - g['away_score']
            margin_pred = g['home_pred'] - g['away_pred'] if g['home_pred'] else 0
            vs_spread = margin_actual - margin_pred
            diff = f" (vs exp: {vs_spread:+.1f})" if g['home_pred'] else ""
            print(f"    {g['game_date']}: {g['home']} vs {g['away']}: {actual} (pred: {pred}){diff}")
    
    print(f"{'='*60}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch actual game scores from ESPN')
    parser.add_argument('--stats', action='store_true', help='Show games table statistics')
    parser.add_argument('--date', type=str, help='Fetch specific date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
    elif args.date:
        print(f"Fetching scores for {args.date}...")
        scores = fetch_espn_scores_for_date(args.date)
        print(f"Found {len(scores)} completed games:")
        for (home, away), data in list(scores.items())[:10]:
            print(f"  {data['home_team']} {data['home_score']} - {data['away_score']} {data['away_team']}")
    else:
        update_scores_from_espn()
        show_stats()