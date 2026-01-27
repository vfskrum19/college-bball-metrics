"""
Check why specific teams are missing from momentum cache
"""
import sqlite3
from pathlib import Path

DATABASE = Path(__file__).parent / 'database' / 'kenpom.db'

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

missing_teams = ['San Jose St.', 'Appalachian St.', 'Southeastern Louisiana']

print("\n" + "="*60)
print("Diagnosing Missing Teams")
print("="*60)

for team_name in missing_teams:
    print(f"\n{team_name}:")
    
    # Get team_id
    cursor.execute("SELECT team_id FROM teams WHERE name = ? AND season = 2026", (team_name,))
    result = cursor.fetchone()
    
    if not result:
        print(f"  ❌ Team not found in teams table!")
        continue
    
    team_id = result[0]
    print(f"  Team ID: {team_id}")
    
    # Check games
    cursor.execute("""
        SELECT COUNT(*) FROM games 
        WHERE (home_team_id = ? OR away_team_id = ?)
    """, (team_id, team_id))
    total_games = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM games 
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND home_score IS NOT NULL
    """, (team_id, team_id))
    games_with_scores = cursor.fetchone()[0]
    
    print(f"  Total games in DB: {total_games}")
    print(f"  Games with scores: {games_with_scores}")
    
    # Check momentum_ratings
    cursor.execute("""
        SELECT COUNT(*) FROM momentum_ratings WHERE team_id = ?
    """, (team_id,))
    rating_snapshots = cursor.fetchone()[0]
    print(f"  Rating snapshots: {rating_snapshots}")
    
    # Check momentum_cache
    cursor.execute("""
        SELECT * FROM momentum_cache WHERE team_id = ?
    """, (team_id,))
    cache = cursor.fetchone()
    print(f"  In momentum_cache: {'Yes' if cache else 'No'}")

conn.close()
