"""
Fetch player data from KenPom using kenpompy library
Pulls player stats and matches to teams, takes top 8 per team by minutes
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd

from kenpompy.utils import login
from kenpompy.summary import get_playerstats

# Configuration
KENPOM_EMAIL = "victorfshilling@gmail.com"  # Your KenPom login email
KENPOM_PASSWORD = "35Beech.road"  # Your KenPom password
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = "2025"  # kenpompy uses string for season
PLAYERS_PER_TEAM = 8

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def fetch_all_player_stats(browser, season=CURRENT_SEASON):
    """
    Fetch player stats for multiple metrics and combine them
    Returns a comprehensive dataframe with all player stats
    """
    print("Fetching player stats from KenPom...")
    
    # Fetch different metrics - each returns top players for that metric
    metrics_to_fetch = [
        ('Min', 'minutes'),      # Minutes % - primary for identifying rotation
        ('ORtg', 'ortg'),        # Offensive rating (returns multiple tables)
        ('eFG', 'efg'),          # Effective FG%
        ('Poss', 'usage'),       # Usage rate
        ('OR', 'or_pct'),        # Offensive rebound %
        ('DR', 'dr_pct'),        # Defensive rebound %
        ('TO', 'to_rate'),       # Turnover rate
        ('ARate', 'ast_rate'),   # Assist rate
        ('Blk', 'blk_rate'),     # Block rate
        ('Stl', 'stl_rate'),     # Steal rate
        ('TS', 'ts_pct'),        # True shooting %
        ('3P', 'three_pct'),     # 3PT %
        ('FT', 'ft_pct'),        # FT %
    ]
    
    all_players = {}  # Dictionary keyed by (player_name, team_name)
    
    for metric, col_name in metrics_to_fetch:
        print(f"  Fetching {metric}...", end=" ")
        try:
            df = get_playerstats(browser, season=season, metric=metric)
            
            # ORtg returns a list of dataframes, use the one with no possession restriction
            if isinstance(df, list):
                df = df[-1]  # Last one has no restriction
            
            if df is not None and not df.empty:
                # Standardize column names (kenpompy uses various formats)
                df.columns = [c.strip() for c in df.columns]
                
                for _, row in df.iterrows():
                    # Extract player name and team
                    player_name = row.get('Player', row.get('player', ''))
                    team_name = row.get('Team', row.get('team', ''))
                    
                    if not player_name or not team_name:
                        continue
                    
                    key = (player_name, team_name)
                    
                    if key not in all_players:
                        all_players[key] = {
                            'name': player_name,
                            'team': team_name,
                        }
                    
                    # Add the metric value
                    # Find the numeric column (usually the metric name or a percentage)
                    for col in df.columns:
                        if col not in ['Player', 'player', 'Team', 'team', 'Rk', 'rk', 'Rank']:
                            try:
                                val = float(str(row[col]).replace('%', ''))
                                all_players[key][col_name] = val
                                break
                            except (ValueError, TypeError):
                                continue
                
                print(f"✓ ({len(df)} players)")
            else:
                print("✗ No data")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print(f"\nTotal unique players found: {len(all_players)}")
    return all_players

def get_team_mapping(cursor, season):
    """Get mapping of team names to team_ids"""
    teams = cursor.execute('''
        SELECT team_id, name FROM teams WHERE season = ?
    ''', (int(season),)).fetchall()
    
    # Create flexible matching (handle slight name differences)
    team_map = {}
    for team in teams:
        team_map[team['name'].lower()] = team['team_id']
        # Also add without common suffixes
        simplified = team['name'].lower().replace(' st.', ' state').replace('state', 'st')
        team_map[simplified] = team['team_id']
    
    return team_map

def match_team(team_name, team_map):
    """Try to match a team name to our database"""
    name_lower = team_name.lower().strip()
    
    # Direct match
    if name_lower in team_map:
        return team_map[name_lower]
    
    # Try variations
    variations = [
        name_lower.replace(' st.', ' state'),
        name_lower.replace(' state', ' st.'),
        name_lower.replace('saint ', 'st. '),
        name_lower.replace('st. ', 'saint '),
    ]
    
    for var in variations:
        if var in team_map:
            return team_map[var]
    
    # Partial match (last resort)
    for db_name, team_id in team_map.items():
        if name_lower in db_name or db_name in name_lower:
            return team_id
    
    return None

def store_players(all_players, season=CURRENT_SEASON):
    """Store players in database, taking top 8 per team by minutes"""
    print("\nStoring players in database...")
    
    db = get_db()
    cursor = db.cursor()
    season_int = int(season)
    
    # Get team mapping
    team_map = get_team_mapping(cursor, season)
    print(f"Found {len(team_map) // 2} teams in database")
    
    # Clear existing player data for this season
    cursor.execute('DELETE FROM team_roles WHERE season = ?', (season_int,))
    cursor.execute('DELETE FROM player_stats WHERE season = ?', (season_int,))
    cursor.execute('DELETE FROM players WHERE season = ?', (season_int,))
    db.commit()
    
    # Group players by team
    players_by_team = {}
    unmatched_teams = set()
    
    for key, player_data in all_players.items():
        team_name = player_data['team']
        team_id = match_team(team_name, team_map)
        
        if team_id is None:
            unmatched_teams.add(team_name)
            continue
        
        if team_id not in players_by_team:
            players_by_team[team_id] = []
        
        players_by_team[team_id].append(player_data)
    
    if unmatched_teams:
        print(f"Warning: Could not match {len(unmatched_teams)} teams")
    
    # Insert top 8 players per team (by minutes)
    total_inserted = 0
    player_id_counter = 1  # Generate our own player IDs
    
    for team_id, players in players_by_team.items():
        # Sort by minutes (descending), take top 8
        players_sorted = sorted(
            players, 
            key=lambda x: x.get('minutes', 0) or 0, 
            reverse=True
        )[:PLAYERS_PER_TEAM]
        
        for player in players_sorted:
            # Insert into players table
            cursor.execute('''
                INSERT INTO players (player_id, team_id, name, season)
                VALUES (?, ?, ?, ?)
            ''', (player_id_counter, team_id, player['name'], season_int))
            
            # Insert into player_stats table
            cursor.execute('''
                INSERT INTO player_stats (
                    player_id, team_id, season,
                    minutes_pct, ortg, usage_rate, efg_pct, ts_pct,
                    or_pct, dr_pct, ast_rate, to_rate,
                    blk_rate, stl_rate, three_pct, ft_pct
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_id_counter,
                team_id,
                season_int,
                player.get('minutes'),
                player.get('ortg'),
                player.get('usage'),
                player.get('efg'),
                player.get('ts_pct'),
                player.get('or_pct'),
                player.get('dr_pct'),
                player.get('ast_rate'),
                player.get('to_rate'),
                player.get('blk_rate'),
                player.get('stl_rate'),
                player.get('three_pct'),
                player.get('ft_pct')
            ))
            
            player_id_counter += 1
            total_inserted += 1
        
        db.commit()
    
    db.close()
    print(f"✓ Inserted {total_inserted} players across {len(players_by_team)} teams")
    return total_inserted

def calculate_roles(season=CURRENT_SEASON):
    """
    Auto-calculate player roles based on stats
    
    Star: Highest minutes with good efficiency
    X-Factor: Best 3PT shooter or high usage secondary player
    Contributors: Remaining players
    """
    print("\nCalculating player roles...")
    
    db = get_db()
    cursor = db.cursor()
    season_int = int(season)
    
    # Get all teams with players
    teams = cursor.execute('''
        SELECT DISTINCT team_id FROM players WHERE season = ?
    ''', (season_int,)).fetchall()
    
    roles_assigned = 0
    
    for team in teams:
        team_id = team['team_id']
        
        # Get players with stats, ordered by minutes
        players = cursor.execute('''
            SELECT 
                p.player_id, p.name,
                ps.minutes_pct, ps.usage_rate, ps.three_pct,
                ps.ortg, ps.efg_pct, ps.ts_pct
            FROM players p
            JOIN player_stats ps ON p.player_id = ps.player_id AND p.season = ps.season
            WHERE p.team_id = ? AND p.season = ?
            ORDER BY ps.minutes_pct DESC NULLS LAST
        ''', (team_id, season_int)).fetchall()
        
        if not players:
            continue
        
        star_assigned = False
        xfactor_assigned = False
        display_order = 1
        
        for player in players:
            role = 'contributor'
            role_reason = None
            
            minutes = player['minutes_pct'] or 0
            usage = player['usage_rate'] or 0
            three_pct = player['three_pct'] or 0
            ortg = player['ortg'] or 0
            
            # Star: Highest minutes player (first in sorted list)
            if not star_assigned and minutes > 0:
                role = 'star'
                if ortg > 0:
                    role_reason = f"{ortg:.1f} ORtg, {minutes:.1f}% min"
                else:
                    role_reason = f"{minutes:.1f}% minutes"
                star_assigned = True
            
            # X-Factor: Best 3PT shooter or high usage secondary
            elif not xfactor_assigned and minutes > 0:
                if three_pct >= 35:
                    role = 'x_factor'
                    role_reason = f"Sharpshooter: {three_pct:.1f}% 3PT"
                    xfactor_assigned = True
                elif usage >= 20:
                    role = 'x_factor'
                    role_reason = f"Secondary option: {usage:.1f}% usage"
                    xfactor_assigned = True
            
            # Insert role
            cursor.execute('''
                INSERT INTO team_roles (team_id, player_id, season, role, role_reason, display_order)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (team_id, player['player_id'], season_int, role, role_reason, display_order))
            
            roles_assigned += 1
            display_order += 1
        
        # If no x_factor assigned, make second player the x_factor
        if not xfactor_assigned and len(players) > 1:
            cursor.execute('''
                UPDATE team_roles 
                SET role = 'x_factor', role_reason = 'Secondary option'
                WHERE player_id = ? AND team_id = ? AND season = ?
            ''', (players[1]['player_id'], team_id, season_int))
    
    db.commit()
    db.close()
    
    print(f"✓ Assigned {roles_assigned} player roles")

def full_player_sync(email=None, password=None, season=CURRENT_SEASON):
    """Full sync: login, fetch players, store, and calculate roles"""
    
    # Use provided credentials or fall back to constants
    email = email or KENPOM_EMAIL
    password = password or KENPOM_PASSWORD
    
    if not email or not password:
        print("⚠️  Please provide KenPom credentials")
        print("   Either set KENPOM_EMAIL and KENPOM_PASSWORD in this file")
        print("   Or pass them as arguments to full_player_sync()")
        return
    
    print(f"\n{'='*50}")
    print(f"KenPom Player Sync - {season} Season")
    print(f"{'='*50}\n")
    
    # Login to KenPom
    print("Logging in to KenPom...")
    try:
        browser = login(email, password)
        print("✓ Logged in successfully\n")
    except Exception as e:
        print(f"✗ Login failed: {e}")
        return
    
    # Fetch all player stats
    all_players = fetch_all_player_stats(browser, season)
    
    if not all_players:
        print("No player data retrieved")
        return
    
    # Store in database
    store_players(all_players, season)
    
    # Calculate roles
    calculate_roles(season)
    
    print(f"\n{'='*50}")
    print(f"Player sync complete! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) == 3:
        # Allow passing credentials via command line
        full_player_sync(email=sys.argv[1], password=sys.argv[2])
    elif KENPOM_EMAIL and KENPOM_PASSWORD:
        full_player_sync()
    else:
        print("Usage: python fetch_players.py <email> <password>")
        print("   Or: Set KENPOM_EMAIL and KENPOM_PASSWORD in the script")
