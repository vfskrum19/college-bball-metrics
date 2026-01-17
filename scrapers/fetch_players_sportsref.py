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
    "Wichita St.": "wichita-state",
    "Wright St.": "wright-state",
    "Youngstown St.": "youngstown-state",
    
    # Cal State schools
    "Cal St. Bakersfield": "cal-state-bakersfield",
    "Cal St. Fullerton": "cal-state-fullerton",
    "CSUN": "cal-state-northridge",
    
    # Other special cases
    "Albany": "albany-ny",
    "Boston University": "boston-university",
    "Bowling Green": "bowling-green-state",
    "Central Connecticut": "central-connecticut-state",
    "Charleston": "college-of-charleston",
    "East Tennessee St.": "east-tennessee-state",
    "Houston Christian": "houston-christian",
    "Little Rock": "arkansas-little-rock",
    "Louisiana": "louisiana-lafayette",
    "McNeese": "mcneese-state",
    "N.C. State": "north-carolina-state",
    "NC State": "north-carolina-state",
    "Nicholls": "nicholls-state",
    "Purdue Fort Wayne": "purdue-fort-wayne",
    "IU Indy": "iupui",
    
    # Existing overrides (keep these)
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
    "SIU Edwardsville": "southern-illinois-edwardsville",
    "UT Arlington": "texas-arlington",
    "UT Martin": "tennessee-martin",
    "UTSA": "texas-san-antonio",
    "UTRGV": "texas-rio-grande-valley",
    "UIC": "illinois-chicago",
    "UMBC": "maryland-baltimore-county",
    "UMKC": "missouri-kansas-city",
    "UNC Wilmington": "north-carolina-wilmington",
    "UNC Greensboro": "north-carolina-greensboro",
    "UNC Asheville": "north-carolina-asheville",
    "Loyola Chicago": "loyola-il",
    "Loyola MD": "loyola-md",
    "Loyola Marymount": "loyola-marymount",
    "Texas A&M": "texas-am",
    "Texas A&M-CC": "texas-am-corpus-christi",
    "Penn": "pennsylvania",
    "Army": "army",
    "Navy": "navy",
    "Air Force": "air-force",
}

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

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
    Uses players_per_game table for stats
    """
    url = f"{SR_BASE}/schools/{team_slug}/men/{season}.html"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 404:
            return None, "Team not found"
        
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        players = []
        
        # Use players_per_game table - has per-game stats
        stats_table = soup.find('table', {'id': 'players_per_game'})
        
        if not stats_table:
            return None, "No players_per_game table found"
        
        tbody = stats_table.find('tbody')
        if not tbody:
            return None, "No table body"
        
        rows = tbody.find_all('tr')
        
        for row in rows:
            # Skip header rows
            if row.get('class') and 'thead' in row.get('class'):
                continue
            
            player_data = {}
            
            for cell in row.find_all(['td', 'th']):
                stat = cell.get('data-stat')
                value = cell.get_text(strip=True)
                
                if stat and value:
                    player_data[stat] = value
            
            # Need at least a player name
            if player_data.get('name_display'):
                players.append(player_data)
        
        return players, None
        
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.RequestException as e:
        return None, str(e)

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

def parse_player_stats(raw):
    """Parse raw stats dict into our database format"""
    return {
        'name': raw.get('name_display', ''),
        'position': raw.get('pos', ''),
        'games_played': safe_int(raw.get('games')),
        'games_started': safe_int(raw.get('games_started')),
        'minutes_pct': safe_float(raw.get('mp_per_g')),
        'ppg': safe_float(raw.get('pts_per_g')),
        'rpg': safe_float(raw.get('trb_per_g')),
        'apg': safe_float(raw.get('ast_per_g')),
        'spg': safe_float(raw.get('stl_per_g')),
        'bpg': safe_float(raw.get('blk_per_g')),
        'fg_pct': safe_float(raw.get('fg_pct')),
        'three_pct': safe_float(raw.get('fg3_pct')),
        'ft_pct': safe_float(raw.get('ft_pct')),
        'efg_pct': safe_float(raw.get('efg_pct')),
        'orb_per_g': safe_float(raw.get('orb_per_g')),
        'drb_per_g': safe_float(raw.get('drb_per_g')),
        'tov_per_g': safe_float(raw.get('tov_per_g')),
    }

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
        
        # Fetch from Sports Reference
        players_raw, error = fetch_team_roster(team_slug, season)
        
        if error:
            print(f"✗ {error}")
            failed_teams.append((team_name, team_slug, error))
            time.sleep(1)
            continue
        
        if not players_raw:
            print("✗ No players")
            failed_teams.append((team_name, team_slug, "No players"))
            time.sleep(1)
            continue
        
        # Parse and filter by minutes threshold
        parsed_players = [parse_player_stats(p) for p in players_raw]
        parsed_players = [p for p in parsed_players if p['name']]
        
        # Filter: only players with 10%+ minutes (4+ min/game)
        rotation_players = [
            p for p in parsed_players 
            if (p.get('minutes_pct') or 0) >= MIN_MINUTES_PER_GAME
        ]
        
        # Sort by PPG for display order
        rotation_players.sort(
            key=lambda x: (x.get('ppg') or 0),
            reverse=True
        )
        
        # Insert into database
        inserted = 0
        for player in rotation_players:
            # Insert player
            cursor.execute('''
                INSERT INTO players (
                    player_id, team_id, name, position, season
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (
                player_id_counter, team_id, player['name'],
                player['position'], season
            ))
            
            # Insert stats
            cursor.execute('''
                INSERT INTO player_stats (
                    player_id, team_id, season, games_played,
                    minutes_pct, ppg, rpg, apg,
                    fg_pct, three_pct, ft_pct, efg_pct
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_id_counter, team_id, season,
                player['games_played'], player['minutes_pct'],
                player['ppg'], player['rpg'], player['apg'],
                player['fg_pct'], player['three_pct'], 
                player['ft_pct'], player['efg_pct']
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
            players, error = fetch_team_roster(team_slug)
            if error:
                print(f"Error: {error}")
            else:
                parsed = [parse_player_stats(p) for p in players]
                rotation = [p for p in parsed if (p.get('minutes_pct') or 0) >= MIN_MINUTES_PER_GAME]
                rotation.sort(key=lambda x: x.get('ppg') or 0, reverse=True)
                
                print(f"Found {len(players)} total players, {len(rotation)} in rotation:\n")
                for p in rotation:
                    print(f"  {p['name']}: {p['ppg']} PPG, {p['minutes_pct']} MIN, {p['three_pct']} 3PT%")
    else:
        full_sync()