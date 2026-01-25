import sqlite3
from pathlib import Path

db_path = Path('database/kenpom.db')

if not db_path.exists():
    print("ERROR: Could not find database/kenpom.db")
    print("Run this script from the project root folder")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=" * 60)
print("Teams with identical primary and secondary colors")
print("=" * 60)

cursor.execute("""
    SELECT name, primary_color, secondary_color 
    FROM teams 
    WHERE primary_color = secondary_color 
    AND season = 2026
    ORDER BY name
""")

results = cursor.fetchall()

if results:
    print(f"\nFound {len(results)} teams with duplicate colors:\n")
    for name, primary, secondary in results:
        print(f"  {name:30s} | {primary}")
else:
    print("\n✓ No teams found with duplicate colors!")

print("\n" + "=" * 60)
print("Teams with NULL or missing colors")
print("=" * 60)

cursor.execute("""
    SELECT name, primary_color, secondary_color 
    FROM teams 
    WHERE (primary_color IS NULL OR secondary_color IS NULL 
           OR primary_color = '' OR secondary_color = '')
    AND season = 2026
    ORDER BY name
""")

null_results = cursor.fetchall()

if null_results:
    print(f"\nFound {len(null_results)} teams with missing colors:\n")
    for name, primary, secondary in null_results:
        print(f"  {name:30s} | primary: {primary or 'NULL':10s} | secondary: {secondary or 'NULL'}")
else:
    print("\n✓ No teams found with missing colors!")

conn.close()
