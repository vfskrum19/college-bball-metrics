#!/usr/bin/env python3
"""
Complete setup script - run this to initialize everything
"""
import subprocess
import sys

def run(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"Error running: {cmd}")
        sys.exit(1)

print("="*70)
print("NCAA Bracket Generator - Complete Setup")
print("="*70)

# Step 1: Initialize database
print("\n1. Initializing database...")
run("python database/init_db.py")

# Step 2: Add player tables
print("\n2. Adding player tables...")
run("python database/add_player_tables.py")

# Step 3: Fetch KenPom data
print("\n3. Fetching KenPom data...")
run("python scrapers/fetch_data.py")

# Step 4: Fetch ESPN branding
print("\n4. Fetching ESPN branding...")
run("python scrapers/fetch_espn_branding.py")

# Step 5: Import NCAA data
print("\n5. Importing NCAA data...")
run("python scrapers/import_ncaa_data.py NCAA_Statistics.csv")

# Step 6: Import Bracket Matrix
print("\n6. Importing Bracket Matrix...")
run("python scrapers/import_bracket_matrix.py")

# Step 7: Verify
print("\n7. Verifying database...")
run("python utils/verify_database.py")

print("\n" + "="*70)
print("SETUP COMPLETE!")
print("="*70)

print("\n" + "-"*70)
print("FIRST TIME SETUP: Run these scrapers once to populate player data")
print("-"*70)
print("""
1. Fetch player stats from Sports Reference (~12-15 min):

    python scrapers/fetch_players_sportsref.py

2. Fetch player headshots from ESPN (~5 min):

    python scrapers/fetch_headshots.py

These only need to be run ONCE unless you wipe the database.

To refresh player stats weekly (optional):

    python scrapers/fetch_players_sportsref.py

To re-assign roles without re-scraping:

    python scrapers/fetch_players_sportsref.py roles
""")