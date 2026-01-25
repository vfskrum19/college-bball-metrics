"""
Migration script to add jersey_number, height, weight columns to players table
Run from project root: python database/add_player_columns.py
"""

import sqlite3
from pathlib import Path

# Find database
script_dir = Path(__file__).parent
db_path = script_dir / 'kenpom.db'

if not db_path.exists():
    # Try from project root
    db_path = Path('database/kenpom.db')

if not db_path.exists():
    print("ERROR: Could not find kenpom.db")
    print("Run this script from the project root or database folder")
    exit(1)

print(f"Using database: {db_path}")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Columns to add to players table
player_columns = [
    ('jersey_number', 'TEXT'),
    ('height', 'TEXT'),
    ('weight', 'INTEGER'),
]

print("\n=== Adding columns to players table ===")
for col_name, col_type in player_columns:
    try:
        cursor.execute(f'ALTER TABLE players ADD COLUMN {col_name} {col_type}')
        print(f"  ✓ Added {col_name} ({col_type})")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print(f"  - {col_name} already exists, skipping")
        else:
            print(f"  ✗ Error adding {col_name}: {e}")

conn.commit()

# Verify columns exist
print("\n=== Verifying players table structure ===")
cursor.execute("PRAGMA table_info(players)")
columns = cursor.fetchall()
print("Current columns in players table:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

conn.close()

print("\n✓ Migration complete!")
print("\nNext step: Re-run the player scraper to populate the new columns:")
print("  python scrapers/fetch_players_sportsref.py")
