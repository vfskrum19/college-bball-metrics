import sqlite3
db = sqlite3.connect('kenpom.db')
cursor = db.cursor()

# Check teams table columns
teams_cols = cursor.execute("PRAGMA table_info(teams)").fetchall()
print("TEAMS TABLE:")
for col in teams_cols:
    print(f"  {col[1]} ({col[2]})")

# Check a sample team
sample = cursor.execute("SELECT team_id, name, season FROM teams WHERE season = 2026 LIMIT 3").fetchall()
print("\nSAMPLE TEAMS:")
for team in sample:
    print(f"  ID: {team[0]}, Name: {team[1]}, Season: {team[2]}")

db.close()