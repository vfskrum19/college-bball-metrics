#!/usr/bin/env python3
"""
Verify database contents after rebuild
"""
import os
from pathlib import Path
import sqlite3

# Get project root (parent of this file's directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

def verify_database():
    """Check what's in the database"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    print("="*70)
    print("DATABASE VERIFICATION")
    print("="*70)
    
    # Check teams
    team_count = db.execute("SELECT COUNT(*) as count FROM teams WHERE season = 2026").fetchone()['count']
    print(f"\n✓ Teams (2026 season): {team_count}")
    
    # Check ratings
    rating_count = db.execute("SELECT COUNT(*) as count FROM ratings WHERE season = 2026").fetchone()['count']
    print(f"✓ Ratings (2026 season): {rating_count}")
    
    # Check quad records
    quad_count = db.execute("SELECT COUNT(*) as count FROM resume_metrics WHERE season = 2026").fetchone()['count']
    print(f"✓ Resume metrics (2026 season): {quad_count}")
    
    # Check four factors
    ff_count = db.execute("SELECT COUNT(*) as count FROM four_factors WHERE season = 2026").fetchone()['count']
    print(f"✓ Four factors (2026 season): {ff_count}")
    
    # Check bracket
    bracket_count = db.execute("SELECT COUNT(*) as count FROM bracket WHERE season = 2026").fetchone()['count']
    print(f"✓ Bracket teams (2026 season): {bracket_count}")
    
    # Check matchups
    matchup_count = db.execute("SELECT COUNT(*) as count FROM matchups WHERE season = 2026").fetchone()['count']
    first_round_count = db.execute("SELECT COUNT(*) as count FROM matchups WHERE season = 2026 AND round = 1").fetchone()['count']
    play_in_count = db.execute("SELECT COUNT(*) as count FROM matchups WHERE season = 2026 AND round = 0").fetchone()['count']
    print(f"✓ First round matchups (2026 season): {first_round_count}")
    print(f"✓ Play-in games (2026 season): {play_in_count}")
    print(f"✓ Total matchups: {matchup_count}")
    
    print("\n" + "="*70)
    print("1 SEEDS")
    print("="*70)
    
    one_seeds = db.execute("""
        SELECT t.name, b.seed, b.region 
        FROM bracket b 
        JOIN teams t ON b.team_id = t.team_id 
        WHERE b.season = 2026 AND b.seed = 1
        ORDER BY b.region
    """).fetchall()
    
    if one_seeds:
        for team in one_seeds:
            print(f"  {team['region']:15s} - {team['name']}")
    else:
        print("  No 1 seeds found!")
    
    print("\n" + "="*70)
    print("SAMPLE FIRST ROUND MATCHUPS")
    print("="*70)
    
    matchups = db.execute("""
        SELECT 
            m.region,
            m.matchup_name,
            t1.name as high_seed_team,
            t2.name as low_seed_team
        FROM matchups m
        JOIN teams t1 ON m.high_seed_team_id = t1.team_id
        JOIN teams t2 ON m.low_seed_team_id = t2.team_id
        WHERE m.season = 2026
        ORDER BY m.region, m.game_number
        LIMIT 8
    """).fetchall()
    
    if matchups:
        for m in matchups:
            print(f"  {m['region']:15s} - {m['matchup_name']:10s}: {m['high_seed_team']:25s} vs {m['low_seed_team']}")
    else:
        print("  No matchups found!")
    
    print("\n" + "="*70)
    print("PLAY-IN GAMES (FIRST FOUR)")
    print("="*70)
    
    play_ins = db.execute("""
        SELECT 
            m.region,
            m.matchup_name,
            t1.name as team1,
            t2.name as team2
        FROM matchups m
        JOIN teams t1 ON m.high_seed_team_id = t1.team_id
        JOIN teams t2 ON m.low_seed_team_id = t2.team_id
        WHERE m.season = 2026 AND m.round = 0
        ORDER BY m.region, m.game_number
    """).fetchall()
    
    if play_ins:
        for p in play_ins:
            print(f"  {p['region']:15s} - {p['matchup_name']:20s}: {p['team1']:25s} vs {p['team2']}")
    else:
        print("  No play-in games found!")
    
    print("\n" + "="*70)
    print("TEAMS BY REGION")
    print("="*70)
    
    regions = db.execute("""
        SELECT region, COUNT(*) as count
        FROM bracket
        WHERE season = 2026
        GROUP BY region
        ORDER BY region
    """).fetchall()
    
    if regions:
        for r in regions:
            print(f"  {r['region']:15s}: {r['count']} teams")
    else:
        print("  No regional assignments found!")
    
    print("\n" + "="*70)
    print("UNMATCHED TEAMS (if any)")
    print("="*70)
    
    # Check if there are teams in JSON that didn't match
    expected = 68
    actual = bracket_count
    if actual < expected:
        print(f"  ⚠ Only {actual}/{expected} teams matched from Bracket Matrix")
        print(f"  ({expected - actual} teams did not match to database)")
    else:
        print(f"  ✓ All {actual} teams matched successfully!")
    
    db.close()
    
    print("\n" + "="*70)
    print("VERIFICATION COMPLETE")
    print("="*70)

if __name__ == '__main__':
    verify_database()