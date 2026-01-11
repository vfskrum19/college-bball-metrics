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

# Step 2: Fetch KenPom data
print("\n2. Fetching KenPom data...")
run("python scrapers/fetch_data.py")

# Step 3: Fetch ESPN branding
print("\n3. Fetching ESPN branding...")
run("python scrapers/fetch_espn_branding.py")

# Step 4: Import NCAA data
print("\n4. Importing NCAA data...")
run("python scrapers/import_ncaa_data.py NCAA_Statistics.csv")

# Step 5: Import Bracket Matrix
print("\n5. Importing Bracket Matrix...")
run("python scrapers/import_bracket_matrix.py")

# Step 6: Verify
print("\n6. Verifying database...")
run("python utils/verify_database.py")

print("\n" + "="*70)
print("SETUP COMPLETE!")
print("="*70)
