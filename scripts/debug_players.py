import sqlite3

db = sqlite3.connect('database/kenpom.db')
db.row_factory = sqlite3.Row

# Check Alabama (team_id 4)
players = db.execute('''
    SELECT p.name, ps.minutes_pct, ps.ppg 
    FROM players p 
    JOIN player_stats ps ON p.player_id = ps.player_id 
    WHERE p.team_id = 4 AND p.season = 2026 
    ORDER BY ps.minutes_pct DESC
''').fetchall()

print(f"{len(players)} players on Alabama:")
for p in players:
    print(f"  {p['name']}: {p['minutes_pct']} min, {p['ppg']} ppg")

db.close()
