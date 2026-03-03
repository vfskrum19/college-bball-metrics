#!/usr/bin/env python3
"""
Complete setup script - run this to initialize everything

Usage:
    python setup.py           # Full setup (first time)
    python setup.py --update  # Daily data refresh only
"""
import subprocess
import sys
import argparse

def run(cmd, optional=False):
    """Run a command, exit on failure unless optional"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        if optional:
            print(f"⚠ Optional step failed: {cmd}")
            return False
        else:
            print(f"❌ Error running: {cmd}")
            sys.exit(1)
    return True

def full_setup():
    """Complete first-time setup"""
    print("="*70)
    print("NCAA Bracket Generator - Complete Setup")
    print("="*70)

    # Step 1: Initialize database
    print("\n📦 Step 1: Initializing database...")
    run("python database/init_db.py")

    # Step 2: Add player tables
    print("\n📦 Step 2: Adding player tables...")
    run("python database/add_player_tables.py")

    # Step 3: Add momentum tables
    print("\n📦 Step 3: Adding momentum tables...")
    run("python database/add_momentum_tables.py")

    # Step 4: Fetch KenPom data (ratings, four factors, teams)
    print("\n📊 Step 4: Fetching KenPom data...")
    run("python scrapers/fetch_data.py")

    # Step 5: Fetch ESPN branding (logos, colors)
    print("\n🎨 Step 5: Fetching ESPN branding...")
    run("python scrapers/fetch_espn_branding.py")

    # Step 6: Import NCAA data (if CSV exists)
    print("\n📋 Step 6: Importing NCAA data...")
    run("python scrapers/import_ncaa_data.py NCAA_Statistics.csv", optional=True)

    # Step 7: Import Bracket Matrix
    print("\n🏀 Step 7: Importing Bracket Matrix...")
    run("python scrapers/import_bracket_matrix.py", optional=True)

    # Step 8: Fetch game predictions from KenPom Fanmatch
    print("\n📅 Step 8: Fetching game predictions (last 45 days)...")
    run("python scrapers/fetch_games.py --days 45")

    # Step 9: Fetch momentum rating snapshots (last 30 days)
    print("\n📈 Step 9: Fetching momentum rating snapshots...")
    run("python scrapers/fetch_momentum_ratings.py --days 30")

    # Step 10: Fetch game scores from ESPN
    print("\n🎯 Step 10: Fetching game scores from ESPN...")
    run("python scrapers/fetch_game_scores_espn.py")

    # Step 11: Calculate momentum scores
    print("\n🔥 Step 11: Calculating momentum scores...")
    run("python scrapers/calculate_momentum.py")

    # Step 12: Fetch historical four factors (for Championship Contender)
    print("\n🏆 Step 12: Fetching historical four factors data...")
    run("python scrapers/fetch_historical_four_factors.py --all", optional=True)

    # Step 13: Verify
    print("\n✅ Step 13: Verifying database...")
    run("python utils/verify_database.py", optional=True)

    print("\n" + "="*70)
    print("✅ SETUP COMPLETE!")
    print("="*70)

    print_post_setup_instructions()


def daily_update():
    """Daily data refresh - run this to update existing data"""
    print("="*70)
    print("NCAA Bracket Generator - Daily Data Update")
    print("="*70)
    print("\n⚠️  Note: Using YESTERDAY's data (today's games may be incomplete)\n")

    # Step 1: Fetch latest KenPom data
    print("\n📊 Step 1: Fetching latest KenPom data...")
    run("python scrapers/fetch_data.py")

    # Step 2: Fetch game predictions from KenPom Fanmatch
    print("\n📅 Step 2: Fetching game predictions...")
    run("python scrapers/fetch_games.py")

    # Step 3: Import NCAA data (if CSV exists)
    print("\n📋 Step 6: Importing NCAA data...")
    run("python scrapers/import_ncaa_data.py NCAA_Statistics.csv")

    # Step 4: Import Bracket Matrix
    print("\n🏀 Step 7: Importing Bracket Matrix...")
    run("python scrapers/import_bracket_matrix.py")

    # Step 5: Fetch rating snapshot (for trajectory)
    print("\n📈 Step 3: Fetching rating snapshot...")
    run("python scrapers/fetch_momentum_ratings.py")

    # Step 6: Fetch game scores from ESPN
    print("\n🎯 Step 4: Fetching game scores from ESPN...")
    run("python scrapers/fetch_game_scores_espn.py")

    # Step 7: Calculate momentum scores
    print("\n🔥 Step 5: Calculating momentum scores...")
    run("python scrapers/calculate_momentum.py")

    # Step 8: Update championship contender scores
    print("\n🏆 Step 6: Updating championship contender scores...")
    run("python scrapers/fetch_historical_four_factors.py --contenders", optional=True)

    print("\n" + "="*70)
    print("✅ DAILY UPDATE COMPLETE!")
    print("="*70)
    print("\nYour momentum tracker data is now up to date.")
    print("Run the backend and frontend to see the latest data:")
    print("  cd backend && python app.py")
    print("  cd frontend && npm run dev")


def print_post_setup_instructions():
    """Print instructions for optional additional setup"""
    print("\n" + "-"*70)
    print("OPTIONAL: Player Data (run once, takes ~15-20 min)")
    print("-"*70)
    print("""
These scrapers populate player stats and headshots. They only need to
be run ONCE unless you wipe the database.

1. Fetch player stats from Sports Reference (~12-15 min):
    python scrapers/fetch_players_sportsref.py

2. Fetch player headshots from ESPN (~5 min):
    python scrapers/fetch_headshots.py

To refresh player stats weekly (optional):
    python scrapers/fetch_players_sportsref.py

To re-assign roles without re-scraping:
    python scrapers/fetch_players_sportsref.py roles
""")

    print("-"*70)
    print("DAILY UPDATES")
    print("-"*70)
    print("""
To refresh data daily, run:

    python setup.py --update

Or manually run these in order:

    python scrapers/fetch_data.py              # KenPom ratings
    python scrapers/fetch_games.py             # Game predictions (Fanmatch)
    python scrapers/fetch_momentum_ratings.py  # Rating snapshots
    python scrapers/fetch_game_scores_espn.py  # Game scores
    python scrapers/calculate_momentum.py      # Momentum scores

See README.md for complete documentation.
""")

    print("-"*70)
    print("START THE APP")
    print("-"*70)
    print("""
Terminal 1 (Backend):
    cd backend
    python app.py

Terminal 2 (Frontend):
    cd frontend
    npm run dev

Then visit: http://localhost:5173
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NCAA Bracket Generator Setup Script"
    )
    parser.add_argument(
        "--update", 
        action="store_true", 
        help="Run daily data update only (skip database init)"
    )
    
    args = parser.parse_args()
    
    if args.update:
        daily_update()
    else:
        full_setup()