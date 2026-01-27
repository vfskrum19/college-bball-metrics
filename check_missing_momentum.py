"""
Check which teams are missing from the momentum cache
Run from project root: python check_missing_momentum.py
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

# Get teams missing momentum data
cursor.execute('''
    SELECT t.name, t.conference 
    FROM teams t 
    LEFT JOIN momentum_cache mc ON t.team_id = mc.team_id 
    WHERE mc.team_id IS NULL AND t.season = 2026 
    ORDER BY t.conference, t.name
''')

missing = cursor.fetchall()

print(f"\n{'='*60}")
print(f"Teams Missing Momentum Data: {len(missing)}")
print(f"{'='*60}\n")

# Group by conference
by_conf = {}
for name, conf in missing:
    if conf not in by_conf:
        by_conf[conf] = []
    by_conf[conf].append(name)

for conf in sorted(by_conf.keys()):
    teams = by_conf[conf]
    print(f"{conf} ({len(teams)} teams):")
    for team in teams:
        print(f"  - {team}")
    print()

# Also check tournament teams specifically
print(f"{'='*60}")
print("Tournament Teams Missing Momentum Data:")
print(f"{'='*60}\n")

cursor.execute('''
    SELECT t.name, b.seed, b.region
    FROM bracket b
    JOIN teams t ON b.team_id = t.team_id
    LEFT JOIN momentum_cache mc ON b.team_id = mc.team_id
    WHERE mc.team_id IS NULL
    ORDER BY b.seed
''')

tourney_missing = cursor.fetchall()

if tourney_missing:
    for name, seed, region in tourney_missing:
        print(f"  ({seed}) {name} - {region}")
else:
    print("  ✓ All tournament teams have momentum data!")

conn.close()
