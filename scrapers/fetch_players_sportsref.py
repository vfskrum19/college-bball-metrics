"""
Fetch player data from Sports Reference (College Basketball Reference)
Pulls full rosters with stats for all teams
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
import time
import re

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = 2026
MIN_MINUTES_PER_GAME = 4.0  # 10% of 40-minute game

# Sports Reference base URL
SR_BASE = "https://www.sports-reference.com/cbb"

# Request headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Team name mapping overrides
TEAM_SLUG_OVERRIDES = {
    # State schools (St. -> state)
    "Alabama St.": "alabama-state",
    "Alcorn St.": "alcorn-state",
    "Appalachian St.": "appalachian-state",
    "Arizona St.": "arizona-state",
    "Arkansas St.": "arkansas-state",
    "Ball St.": "ball-state",
    "Boise St.": "boise-state",
    "Chicago St.": "chicago-state",
    "Cleveland St.": "cleveland-state",
    "Colorado St.": "colorado-state",
    "Coppin St.": "coppin-state",
    "Delaware St.": "delaware-state",
    "Florida St.": "florida-state",
    "Fresno St.": "fresno-state",
    "Georgia St.": "georgia-state",
    "Grambling St.": "grambling",
    "Idaho St.": "idaho-state",
    "Illinois St.": "illinois-state",
    "Indiana St.": "indiana-state",
    "Iowa St.": "iowa-state",
    "Jackson St.": "jackson-state",
    "Jacksonville St.": "jacksonville-state",
    "Kansas St.": "kansas-state",
    "Kennesaw St.": "kennesaw-state",
    "Kent St.": "kent-state",
    "Long Beach St.": "long-beach-state",
    "Michigan St.": "michigan-state",
    "Mississippi St.": "mississippi-state",
    "Mississippi Valley St.": "mississippi-valley-state",
    "Missouri St.": "missouri-state",
    "Montana St.": "montana-state",
    "Morehead St.": "morehead-state",
    "Morgan St.": "morgan-state",
    "Murray St.": "murray-state",
    "New Mexico St.": "new-mexico-state",
    "Norfolk St.": "norfolk-state",
    "North Dakota St.": "north-dakota-state",
    "Northwestern St.": "northwestern-state",
    "Ohio St.": "ohio-state",
    "Oklahoma St.": "oklahoma-state",
    "Oregon St.": "oregon-state",
    "Penn St.": "penn-state",
    "Portland St.": "portland-state",
    "Sacramento St.": "sacramento-state",
    "Sam Houston St.": "sam-houston-state",
    "San Diego St.": "san-diego-state",
    "San Jose St.": "san-jose-state",
    "South Carolina St.": "south-carolina-state",
    "South Dakota St.": "south-dakota-state",
    "Tennessee St.": "tennessee-state",
    "Texas St.": "texas-state",
    "Utah St.": "utah-state",
    "Washington St.": "washington-state",
    "Weber St.": "weber-state",
    "Wichita St.": "wichita-state",
    "Wright St.": "wright-state",
    "Youngstown St.": "youngstown-state",
    "Tarleton St.": "tarleton-state",
    
    # Cal State schools
    "Cal St. Bakersfield": "cal-state-bakersfield",
    "Cal St. Fullerton": "cal-state-fullerton",
    "CSUN": "cal-state-northridge",
    
    # UC schools
    "UC Davis": "california-davis",
    "UC Irvine": "california-irvine",
    "UC Riverside": "california-riverside",
    "UC Santa Barbara": "california-santa-barbara",
    "UC San Diego": "california-san-diego",
    "Cal Baptist": "california-baptist",
    
    # Other special cases
    "Albany": "albany-ny",
    "Boston University": "boston-university",
    "Bowling Green": "bowling-green-state",
    "Central Connecticut": "central-connecticut-state",
    "Charleston": "college-of-charleston",
    "East Tennessee St.": "east-tennessee-state",
    "Houston Christian": "houston-baptist",
    "Little Rock": "arkansas-little-rock",
    "Louisiana": "louisiana-lafayette",
    "McNeese": "mcneese-state",
    "N.C. State": "north-carolina-state",
    "NC State": "north-carolina-state",
    "Nicholls": "nicholls-state",
    "Purdue Fort Wayne": "ipfw",
    "IU Indy": "iupui",
    "Prairie View A&M": "prairie-view",
    "SIUE": "southern-illinois-edwardsville",
    "SIU Edwardsville": "southern-illinois-edwardsville",
    "Southeast Missouri": "southeast-missouri-state",
    "Southern Miss": "southern-mississippi",
    "Saint Francis": "saint-francis-pa",
    "Texas A&M Corpus Chris": "texas-am-corpus-christi",
    "Texas A&M-CC": "texas-am-corpus-christi",
    "The Citadel": "citadel",
    "UMass Lowell": "massachusetts-lowell",
    "Kansas City": "missouri-kansas-city",
    "UMKC": "missouri-kansas-city",
    "USC Upstate": "south-carolina-upstate",
    "UT Rio Grande Valley": "texas-pan-american",
    "UTRGV": "texas-pan-american",
    "VMI": "virginia-military-institute",
    "Utah Tech": "dixie-state",
    "St. Thomas": "st-thomas-mn",
    "Queens": "queens-nc",
    "East Texas A&M": "texas-am-commerce",
    
    # Existing overrides
    "Connecticut": "connecticut",
    "UConn": "connecticut",
    "Miami FL": "miami-fl",
    "Miami OH": "miami-oh",
    "LSU": "louisiana-state",
    "USC": "southern-california",
    "UCF": "central-florida",
    "UNLV": "nevada-las-vegas",
    "VCU": "virginia-commonwealth",
    "SMU": "southern-methodist",
    "TCU": "texas-christian",
    "BYU": "brigham-young",
    "UTEP": "texas-el-paso",
    "UAB": "alabama-birmingham",
    "UNC": "north-carolina",
    "Ole Miss": "mississippi",
    "Pitt": "pittsburgh",
    "UMass": "massachusetts",
    "Saint Mary's": "saint-marys-ca",
    "St. John's": "st-johns-ny",
    "Saint Joseph's": "saint-josephs",
    "Saint Louis": "saint-louis",
    "Saint Peter's": "saint-peters",
    "LIU": "long-island-university",
    "ETSU": "east-tennessee-state",
    "MTSU": "middle-tennessee",
    "FIU": "florida-international",
    "FAU": "florida-atlantic",
    "UT Arlington": "texas-arlington",
    "UT Martin": "tennessee-martin",
    "UTSA": "texas-san-antonio",
    "UIC": "illinois-chicago",
    "UMBC": "maryland-baltimore-county",
    "UNC Wilmington": "north-carolina-wilmington",
    "UNC Greensboro": "north-carolina-greensboro",
    "UNC Asheville": "north-carolina-asheville",
    "Loyola Chicago": "loyola-il",
    "Loyola MD": "loyola-md",
    "Loyola Marymount": "loyola-marymount",
    "Texas A&M": "texas-am",
    "Penn": "pennsylvania",
    "Army": "army",
    "Navy": "navy",
    "Air Force": "air-force",
}

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def normalize_player_name(name):
    """
    Normalize player name by removing suffixes for matching purposes.
    Sports Reference roster table often lacks suffixes that stats table has.
    """
    if not name:
        return name
    
    # Common suffixes to strip (order matters - check longer ones first)
    suffixes = [' Jr.', ' Jr', ' Sr.', ' Sr', ' III', ' II', ' IV', ' V']
    
    normalized = name.strip()
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
            break
    
    return normalized

def team_name_to_slug(team_name):
    """Convert team name to Sports Reference URL slug"""
    if team_name in TEAM_SLUG_OVERRIDES:
        return TEAM_SLUG_OVERRIDES[team_name]
    
    slug = team_name.lower()
    slug = slug.replace("'", "")
    slug = slug.replace(".", "")
    slug = slug.replace("&", "")
    slug = slug.replace("(", "").replace(")", "")
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    
    return slug

def fetch_team_roster(team_slug, season=CURRENT_SEASON):
    """
    Fetch roster and stats from Sports Reference team page
    Scrapes both 'roster' table (physical info) and 'players_per_game' (stats)
    """
    url = f"{SR_BASE}/schools/{team_slug}/men/{season}.html"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 404:
            return None, None, None, "Team not found"
        
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ============================================
        # 1. Scrape ROSTER table (jersey, height, weight, class)
        # ============================================
        roster_data = {}
        roster_table = soup.find('table', {'id': 'roster'})
        
        if roster_table:
            tbody = roster_table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    if row.get('class') and 'thead' in row.get('class'):
                        continue
                    
                    player_info = {}
                    for cell in row.find_all(['td', 'th']):
                        stat = cell.get('data-stat')
                        value = cell.get_text(strip=True)
                        if stat and value:
                            player_info[stat] = value
                    
                    # Key by player name for merging later
                    player_name = player_info.get('player', '')
                    if player_name:
                        roster_data[player_name] = {
                            'jersey_number': player_info.get('number', ''),
                            'height': player_info.get('height', ''),
                            'weight': player_info.get('weight', ''),
                            'year': player_info.get('class', ''),
                        }
        
        # ============================================
        # 2. Scrape PLAYERS_PER_GAME table (stats)
        # ============================================
        stats_players = []
        stats_table = soup.find('table', {'id': 'players_per_game'})
        
        if not stats_table:
            return None, None, None, "No players_per_game table found"
        
        tbody = stats_table.find('tbody')
        if not tbody:
            return None, None, None, "No table body"
        
        for row in tbody.find_all('tr'):
            if row.get('class') and 'thead' in row.get('class'):
                continue
            
            player_data = {}
            for cell in row.find_all(['td', 'th']):
                stat = cell.get('data-stat')
                value = cell.get_text(strip=True)
                if stat and value:
                    player_data[stat] = value
            
            if player_data.get('name_display'):
                stats_players.append(player_data)
        
        # ============================================
        # 3. Scrape ADVANCED table (advanced stats)
        #    Note: Sports Reference hides this in HTML comments
        # ============================================
        advanced_data = {}
        
        # First try to find it directly
        advanced_table = soup.find('table', {'id': 'players_advanced'})
        
        # If not found, look in HTML comments
        if not advanced_table:
            from bs4 import Comment
            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            for comment in comments:
                if 'id="players_advanced"' in comment:
                    # Parse the comment as HTML
                    comment_soup = BeautifulSoup(comment, 'html.parser')
                    advanced_table = comment_soup.find('table', {'id': 'players_advanced'})
                    if advanced_table:
                        break
        
        if advanced_table:
            tbody = advanced_table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    if row.get('class') and 'thead' in row.get('class'):
                        continue
                    
                    player_adv = {}
                    for cell in row.find_all(['td', 'th']):
                        stat = cell.get('data-stat')
                        value = cell.get_text(strip=True)
                        if stat and value:
                            player_adv[stat] = value
                    
                    # Key by player name for merging
                    player_name = player_adv.get('name_display', '')
                    if player_name:
                        advanced_data[player_name] = player_adv
        
        return stats_players, roster_data, advanced_data, None
        
    except requests.exceptions.Timeout:
        return None, None, None, "Timeout"
    except requests.exceptions.RequestException as e:
        return None, None, None, str(e)

def safe_float(val):
    """Safely convert to float"""
    if not val or val == '':
        return None
    try:
        return float(val.replace('%', ''))
    except (ValueError, TypeError):
        return None

def safe_int(val):
    """Safely convert to int"""
    if not val or val == '':
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

def parse_player_stats(raw_stats, roster_info=None, advanced_info=None):
    """
    Parse raw stats dict into our database format
    Merges stats from players_per_game with roster info and advanced stats
    """
    player_name = raw_stats.get('name_display', '')
    
    # Get roster info if available (jersey, height, weight, year)
    roster = roster_info or {}
    
    # Get advanced stats if available
    adv = advanced_info or {}
    
    return {
        'name': player_name,
        'position': raw_stats.get('pos', ''),
        'jersey_number': roster.get('jersey_number', ''),
        'height': roster.get('height', ''),
        'weight': roster.get('weight', ''),
        'year': roster.get('year', ''),
        'games_played': safe_int(raw_stats.get('games')),
        'games_started': safe_int(raw_stats.get('games_started')),
        'minutes_pct': safe_float(raw_stats.get('mp_per_g')),
        'ppg': safe_float(raw_stats.get('pts_per_g')),
        'rpg': safe_float(raw_stats.get('trb_per_g')),
        'apg': safe_float(raw_stats.get('ast_per_g')),
        'spg': safe_float(raw_stats.get('stl_per_g')),
        'bpg': safe_float(raw_stats.get('blk_per_g')),
        'fg_pct': safe_float(raw_stats.get('fg_pct')),
        'three_pct': safe_float(raw_stats.get('fg3_pct')),
        'ft_pct': safe_float(raw_stats.get('ft_pct')),
        'efg_pct': safe_float(raw_stats.get('efg_pct')),
        'orb_per_g': safe_float(raw_stats.get('orb_per_g')),
        'drb_per_g': safe_float(raw_stats.get('drb_per_g')),
        'tov_per_g': safe_float(raw_stats.get('tov_per_g')),
        # Advanced stats
        'usage_pct': safe_float(adv.get('usg_pct')),
        'ortg': None,  # Not available in advanced table
        'drtg': None,  # Not available in advanced table
        'bpm': safe_float(adv.get('bpm')),
        'obpm': safe_float(adv.get('obpm')),
        'dbpm': safe_float(adv.get('dbpm')),
        'ws': safe_float(adv.get('ws')),
        'ws_40': safe_float(adv.get('ws_per_40')),
        'ast_pct': safe_float(adv.get('ast_pct')),
        'tov_pct': safe_float(adv.get('tov_pct')),
        'orb_pct': safe_float(adv.get('orb_pct')),
        'drb_pct': safe_float(adv.get('drb_pct')),
        'stl_pct': safe_float(adv.get('stl_pct')),
        'blk_pct': safe_float(adv.get('blk_pct')),
        'per': safe_float(adv.get('per')),
        'ts_pct': safe_float(adv.get('ts_pct')),
    }

def find_roster_info(player_name, roster_data):
    """
    Find roster info for a player, handling suffix mismatches.
    Sports Reference roster table often lacks suffixes (Jr., Sr., III, etc.)
    that the stats table includes.
    """
    if not roster_data:
        return {}
    
    # Try exact match first
    if player_name in roster_data:
        return roster_data[player_name]
    
    # Try normalized name (without suffix)
    normalized_name = normalize_player_name(player_name)
    if normalized_name in roster_data:
        return roster_data[normalized_name]
    
    # Try matching normalized versions of both names
    for roster_name, roster_vals in roster_data.items():
        if normalize_player_name(roster_name) == normalized_name:
            return roster_vals
    
    # No match found
    return {}

def fetch_all_players(season=CURRENT_SEASON):
    """Fetch player data for all teams in database"""
    print(f"\n{'='*60}")
    print(f"Sports Reference Player Sync - {season} Season")
    print(f"{'='*60}\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # Get all teams
    teams = cursor.execute('''
        SELECT team_id, name FROM teams WHERE season = ?
    ''', (season,)).fetchall()
    
    print(f"Found {len(teams)} teams in database\n")
    
    # Clear existing player data
    cursor.execute('DELETE FROM team_roles WHERE season = ?', (season,))
    cursor.execute('DELETE FROM player_stats WHERE season = ?', (season,))
    cursor.execute('DELETE FROM players WHERE season = ?', (season,))
    db.commit()
    
    total_players = 0
    successful_teams = 0
    failed_teams = []
    player_id_counter = 1
    
    for i, team in enumerate(teams):
        team_id = team['team_id']
        team_name = team['name']
        team_slug = team_name_to_slug(team_name)
        
        print(f"[{i+1}/{len(teams)}] {team_name}...", end=" ", flush=True)
        
        # Fetch from Sports Reference (now returns stats, roster, and advanced)
        stats_players, roster_data, advanced_data, error = fetch_team_roster(team_slug, season)
        
        if error:
            print(f"✗ {error}")
            failed_teams.append((team_name, team_slug, error))
            time.sleep(1)
            continue
        
        if not stats_players:
            print("✗ No players")
            failed_teams.append((team_name, team_slug, "No players"))
            time.sleep(1)
            continue
        
        # Parse and merge roster info + advanced stats with basic stats
        parsed_players = []
        for p in stats_players:
            player_name = p.get('name_display', '')
            
            # Find matching roster info (handles suffix mismatches)
            roster_info = find_roster_info(player_name, roster_data)
            
            # Try to find matching advanced stats
            adv_info = advanced_data.get(player_name, {}) if advanced_data else {}
            
            parsed_players.append(parse_player_stats(p, roster_info, adv_info))
        
        parsed_players = [p for p in parsed_players if p['name']]
        
        # Filter: only players with 10%+ minutes (4+ min/game)
        rotation_players = [
            p for p in parsed_players 
            if (p.get('minutes_pct') or 0) >= MIN_MINUTES_PER_GAME
        ]

        # Sort by minutes (primary rotation guys first)
        rotation_players.sort(
            key=lambda x: (x.get('minutes_pct') or 0),
            reverse=True
        )

        # Cap at 10 players max
        rotation_players = rotation_players[:10]
        
        # Insert into database
        inserted = 0
        for player in rotation_players:
            # Insert player (now includes jersey_number, height, year)
            cursor.execute('''
                INSERT INTO players (
                    player_id, team_id, name, position, 
                    jersey_number, height, year, season
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_id_counter, team_id, player['name'],
                player['position'], player['jersey_number'],
                player['height'], player['year'], season
            ))
            
            # Insert stats (now includes advanced stats)
            cursor.execute('''
                INSERT INTO player_stats (
                    player_id, team_id, season, games_played,
                    minutes_pct, ppg, rpg, apg,
                    fg_pct, three_pct, ft_pct, efg_pct,
                    usage_pct, ortg, drtg, bpm, obpm, dbpm,
                    ws, ws_40, ast_pct, tov_pct, orb_pct, drb_pct,
                    stl_pct, blk_pct, per, ts_pct
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_id_counter, team_id, season,
                player['games_played'], player['minutes_pct'],
                player['ppg'], player['rpg'], player['apg'],
                player['fg_pct'], player['three_pct'], 
                player['ft_pct'], player['efg_pct'],
                player['usage_pct'], player['ortg'], player['drtg'],
                player['bpm'], player['obpm'], player['dbpm'],
                player['ws'], player['ws_40'],
                player['ast_pct'], player['tov_pct'],
                player['orb_pct'], player['drb_pct'],
                player['stl_pct'], player['blk_pct'],
                player['per'], player['ts_pct']
            ))
            
            player_id_counter += 1
            inserted += 1
        
        db.commit()
        total_players += inserted
        successful_teams += 1
        print(f"✓ {inserted} players")
        
        # Rate limit - be nice to Sports Reference
        time.sleep(2)
    
    db.close()
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Teams processed: {successful_teams}/{len(teams)}")
    print(f"  Players inserted: {total_players}")
    print(f"  Failed teams: {len(failed_teams)}")
    
    if failed_teams:
        print(f"\nFailed teams (may need slug override):")
        for name, slug, err in failed_teams[:20]:
            print(f"  {name} -> {slug}: {err}")
        if len(failed_teams) > 20:
            print(f"  ... and {len(failed_teams) - 20} more")
    
    print(f"{'='*60}\n")
    
    return total_players

def calculate_roles(season=CURRENT_SEASON):
    """Auto-calculate player roles based on stats"""
    print("Calculating player roles...")
    
    db = get_db()
    cursor = db.cursor()
    
    # Clear existing roles first
    cursor.execute('DELETE FROM team_roles WHERE season = ?', (season,))
    db.commit()
    
    teams = cursor.execute('''
        SELECT DISTINCT team_id FROM players WHERE season = ?
    ''', (season,)).fetchall()
    
    roles_assigned = 0
    
    for team in teams:
        team_id = team['team_id']
        
        # Get players ordered by PPG
        players = cursor.execute('''
            SELECT 
                p.player_id, p.name,
                ps.ppg, ps.minutes_pct, ps.three_pct
            FROM players p
            JOIN player_stats ps ON p.player_id = ps.player_id AND p.season = ps.season
            WHERE p.team_id = ? AND p.season = ?
            ORDER BY ps.ppg DESC NULLS LAST
        ''', (team_id, season)).fetchall()
        
        if not players:
            continue
        
        star_assigned = False
        xfactor_assigned = False
        display_order = 1
        
        for player in players:
            role = 'contributor'
            role_reason = None
            
            ppg = player['ppg'] or 0
            three_pct = player['three_pct'] or 0
            
            # Star: Top scorer
            if not star_assigned:
                role = 'star'
                role_reason = f"{ppg:.1f} PPG"
                star_assigned = True
            
            # X-Factor: Good shooter or secondary scorer
            elif not xfactor_assigned:
                if three_pct and three_pct >= 0.35:
                    role = 'x_factor'
                    role_reason = f"{three_pct*100:.1f}% 3PT"
                    xfactor_assigned = True
                elif ppg >= 8:
                    role = 'x_factor'
                    role_reason = f"{ppg:.1f} PPG"
                    xfactor_assigned = True
            
            cursor.execute('''
                INSERT INTO team_roles (team_id, player_id, season, role, role_reason, display_order)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (team_id, player['player_id'], season, role, role_reason, display_order))
            
            roles_assigned += 1
            display_order += 1
        
        # If no x_factor, make second player x_factor
        if not xfactor_assigned and len(players) > 1:
            cursor.execute('''
                UPDATE team_roles 
                SET role = 'x_factor', role_reason = 'Secondary option'
                WHERE player_id = ? AND team_id = ? AND season = ?
            ''', (players[1]['player_id'], team_id, season))
    
    db.commit()
    db.close()
    
    print(f"✓ Assigned {roles_assigned} player roles\n")

def full_sync(season=CURRENT_SEASON):
    """Full sync: fetch all players and calculate roles"""
    fetch_all_players(season)
    calculate_roles(season)
    print(f"Player sync complete! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'roles':
            calculate_roles()
        elif sys.argv[1] == 'test':
            team_slug = sys.argv[2] if len(sys.argv) > 2 else 'arizona'
            print(f"Testing with {team_slug}...")
            print(f"Minutes threshold: {MIN_MINUTES_PER_GAME}+ min/game (10%+)\n")
            stats_players, roster_data, advanced_data, error = fetch_team_roster(team_slug)
            if error:
                print(f"Error: {error}")
            else:
                # Merge and parse
                parsed = []
                for p in stats_players:
                    name = p.get('name_display', '')
                    roster_info = find_roster_info(name, roster_data)
                    adv_info = advanced_data.get(name, {}) if advanced_data else {}
                    parsed.append(parse_player_stats(p, roster_info, adv_info))
                
                rotation = [p for p in parsed if (p.get('minutes_pct') or 0) >= MIN_MINUTES_PER_GAME]
                rotation.sort(key=lambda x: x.get('minutes_pct') or 0, reverse=True)
                rotation = rotation[:10]
                
                print(f"Found {len(stats_players)} total players, {len(rotation)} in rotation:\n")
                print(f"{'#':4s} {'Name':25s} {'Ht/Wt':15s} {'PPG':6s} {'USG%':6s} {'PER':5s} {'BPM':5s} {'WS':4s}")
                print("-" * 75)
                for p in rotation:
                    jersey = f"#{p['jersey_number']}" if p['jersey_number'] else ""
                    height = p['height'] or ""
                    weight = f"{p['weight']} lbs" if p['weight'] else ""
                    physical = f"{height} {weight}".strip()
                    ppg = f"{p['ppg']:.1f}" if p['ppg'] else "-"
                    usg = f"{p['usage_pct']:.1f}" if p['usage_pct'] else "-"
                    per = f"{p['per']:.1f}" if p['per'] else "-"
                    bpm = f"{p['bpm']:.1f}" if p['bpm'] else "-"
                    ws = f"{p['ws']:.1f}" if p['ws'] else "-"
                    print(f"{jersey:4s} {p['name']:25s} {physical:15s} {ppg:6s} {usg:6s} {per:5s} {bpm:5s} {ws:4s}")
    else:
        full_sync()