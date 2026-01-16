"""
Fetch player headshots from ESPN
Run AFTER fetch_players.py to add headshot URLs
"""

import sqlite3
import requests
from pathlib import Path
import time
import re

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = 2025

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def normalize_name(name):
    """Normalize player name for matching"""
    if not name:
        return ""
    # Remove suffixes
    name = re.sub(r'\s+(Jr\.?|Sr\.?|III|II|IV)$', '', name, flags=re.IGNORECASE)
    return name.lower().strip()

def get_espn_team_id(logo_url):
    """Extract ESPN team ID from logo URL"""
    if not logo_url:
        return None
    match = re.search(r'/(\d+)\.png', logo_url)
    return match.group(1) if match else None

def fetch_espn_roster(espn_team_id):
    """Fetch roster from ESPN API"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{espn_team_id}/roster"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        athletes = {}
        for athlete in data.get('athletes', []):
            name = normalize_name(athlete.get('displayName', ''))
            headshot = athlete.get('headshot', {}).get('href', '')
            if name and headshot:
                athletes[name] = headshot
        return athletes
    except Exception as e:
        return {}

def fetch_all_headshots(season=CURRENT_SEASON):
    """Fetch headshots for all players"""
    print(f"\n{'='*50}")
    print("Fetching player headshots from ESPN")
    print(f"{'='*50}\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # Get teams with players and their ESPN IDs
    teams = cursor.execute('''
        SELECT DISTINCT t.team_id, t.name, t.logo_url
        FROM teams t
        JOIN players p ON t.team_id = p.team_id AND t.season = p.season
        WHERE t.season = ?
    ''', (season,)).fetchall()
    
    print(f"Found {len(teams)} teams with players\n")
    
    total_matched = 0
    
    for team in teams:
        team_id = team['team_id']
        team_name = team['name']
        espn_id = get_espn_team_id(team['logo_url'])
        
        if not espn_id:
            print(f"{team_name}: No ESPN ID")
            continue
        
        print(f"{team_name}...", end=" ")
        
        # Get ESPN roster with headshots
        espn_roster = fetch_espn_roster(espn_id)
        
        if not espn_roster:
            print("✗ No roster data")
            time.sleep(0.3)
            continue
        
        # Get our players
        our_players = cursor.execute('''
            SELECT player_id, name FROM players
            WHERE team_id = ? AND season = ?
        ''', (team_id, season)).fetchall()
        
        matched = 0
        for player in our_players:
            normalized = normalize_name(player['name'])
            
            # Try exact match
            if normalized in espn_roster:
                cursor.execute('''
                    UPDATE players SET headshot_url = ?
                    WHERE player_id = ? AND season = ?
                ''', (espn_roster[normalized], player['player_id'], season))
                matched += 1
            else:
                # Try last name match
                last_name = normalized.split()[-1] if normalized else ""
                for espn_name, headshot in espn_roster.items():
                    if last_name and espn_name.endswith(last_name):
                        cursor.execute('''
                            UPDATE players SET headshot_url = ?
                            WHERE player_id = ? AND season = ?
                        ''', (headshot, player['player_id'], season))
                        matched += 1
                        break
        
        db.commit()
        total_matched += matched
        print(f"✓ {matched}/{len(our_players)}")
        
        time.sleep(0.3)
    
    db.close()
    print(f"\n✓ Matched {total_matched} headshots total")

if __name__ == '__main__':
    fetch_all_headshots()
