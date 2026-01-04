#!/usr/bin/env python3
"""
Comprehensive verification before committing to version control
Tests all critical functionality
"""
import sqlite3
import os
import sys
import json

DATABASE = 'kenpom.db'
REQUIRED_FILES = [
    'init_db.py',
    'fetch_data.py', 
    'fetch_espn_branding.py',
    'import_ncaa_data.py',
    'generate_bracket.py',
    'import_bracket_matrix.py',
    'bracket_matrix_teams.json',
    'clear_bracket.py',
    'verify_database.py',
    'show_schema.py',
]

def check_files():
    """Verify all required files exist"""
    print("="*70)
    print("1. CHECKING REQUIRED FILES")
    print("="*70)
    
    missing = []
    for filename in REQUIRED_FILES:
        if os.path.exists(filename):
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename} - MISSING")
            missing.append(filename)
    
    if missing:
        print(f"\n⚠ WARNING: {len(missing)} files missing!")
        return False
    else:
        print(f"\n✓ All required files present")
        return True

def check_database():
    """Verify database exists and has required tables"""
    print("\n" + "="*70)
    print("2. CHECKING DATABASE")
    print("="*70)
    
    if not os.path.exists(DATABASE):
        print(f"  ✗ {DATABASE} does not exist!")
        return False
    
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    
    # Check tables
    required_tables = [
        'teams', 'ratings', 'four_factors', 'resume_metrics',
        'bracket', 'matchups'
    ]
    
    existing_tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    existing_tables = [t[0] for t in existing_tables]
    
    all_good = True
    for table in required_tables:
        if table in existing_tables:
            count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  ✓ {table:20s} ({count} rows)")
        else:
            print(f"  ✗ {table:20s} - MISSING")
            all_good = False
    
    db.close()
    return all_good

def check_data_integrity():
    """Verify data integrity"""
    print("\n" + "="*70)
    print("3. CHECKING DATA INTEGRITY")
    print("="*70)
    
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    issues = []
    
    # Check season 2026 data
    team_count = db.execute("SELECT COUNT(*) FROM teams WHERE season = 2026").fetchone()[0]
    if team_count != 365:
        issues.append(f"Expected 365 teams for 2026, found {team_count}")
        print(f"  ⚠ Teams: {team_count} (expected 365)")
    else:
        print(f"  ✓ Teams: {team_count}")
    
    # Check ratings match teams
    rating_count = db.execute("SELECT COUNT(*) FROM ratings WHERE season = 2026").fetchone()[0]
    if rating_count != team_count:
        issues.append(f"Ratings count ({rating_count}) doesn't match teams ({team_count})")
        print(f"  ⚠ Ratings: {rating_count} (should match teams)")
    else:
        print(f"  ✓ Ratings: {rating_count}")
    
    # Check resume metrics
    resume_count = db.execute("SELECT COUNT(*) FROM resume_metrics WHERE season = 2026").fetchone()[0]
    if resume_count != team_count:
        issues.append(f"Resume metrics count ({resume_count}) doesn't match teams ({team_count})")
        print(f"  ⚠ Resume metrics: {resume_count} (should match teams)")
    else:
        print(f"  ✓ Resume metrics: {resume_count}")
    
    # Check bracket
    bracket_count = db.execute("SELECT COUNT(*) FROM bracket WHERE season = 2026").fetchone()[0]
    if bracket_count != 68:
        issues.append(f"Expected 68 bracket teams, found {bracket_count}")
        print(f"  ⚠ Bracket teams: {bracket_count} (expected 68)")
    else:
        print(f"  ✓ Bracket teams: {bracket_count}")
    
    # Check matchups
    matchup_count = db.execute("SELECT COUNT(*) FROM matchups WHERE season = 2026").fetchone()[0]
    play_in_count = db.execute("SELECT COUNT(*) FROM matchups WHERE season = 2026 AND round = 0").fetchone()[0]
    first_round_count = db.execute("SELECT COUNT(*) FROM matchups WHERE season = 2026 AND round = 1").fetchone()[0]
    
    if matchup_count != 36:
        issues.append(f"Expected 36 total matchups, found {matchup_count}")
        print(f"  ⚠ Total matchups: {matchup_count} (expected 36)")
    else:
        print(f"  ✓ Total matchups: {matchup_count}")
    
    if play_in_count != 4:
        issues.append(f"Expected 4 play-in games, found {play_in_count}")
        print(f"  ⚠ Play-in games: {play_in_count} (expected 4)")
    else:
        print(f"  ✓ Play-in games: {play_in_count}")
    
    if first_round_count != 32:
        issues.append(f"Expected 32 first-round matchups, found {first_round_count}")
        print(f"  ⚠ First-round matchups: {first_round_count} (expected 32)")
    else:
        print(f"  ✓ First-round matchups: {first_round_count}")
    
    db.close()
    
    return len(issues) == 0, issues

def check_bracket_integrity():
    """Verify bracket structure"""
    print("\n" + "="*70)
    print("4. CHECKING BRACKET STRUCTURE")
    print("="*70)
    
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    issues = []
    
    # Check 1 seeds
    one_seeds = db.execute("""
        SELECT t.name, b.region 
        FROM bracket b 
        JOIN teams t ON b.team_id = t.team_id 
        WHERE b.season = 2026 AND b.seed = 1
        ORDER BY b.region
    """).fetchall()
    
    if len(one_seeds) != 4:
        issues.append(f"Expected 4 #1 seeds, found {len(one_seeds)}")
        print(f"  ⚠ 1 seeds: {len(one_seeds)} (expected 4)")
    else:
        print(f"  ✓ 1 seeds: {len(one_seeds)}")
        for seed in one_seeds:
            print(f"    - {seed['region']:15s}: {seed['name']}")
    
    # Check regional distribution
    regions = db.execute("""
        SELECT region, COUNT(*) as count
        FROM bracket
        WHERE season = 2026
        GROUP BY region
        ORDER BY region
    """).fetchall()
    
    print(f"\n  Regional distribution:")
    for r in regions:
        count = r['count']
        # Should be 16, 17, or 18 (due to play-ins)
        if count < 16 or count > 18:
            issues.append(f"Region {r['region']} has {count} teams (should be 16-18)")
            print(f"    ⚠ {r['region']:15s}: {count} teams (should be 16-18)")
        else:
            print(f"    ✓ {r['region']:15s}: {count} teams")
    
    # Check for orphaned matchups (teams in matchups but not in bracket)
    orphans = db.execute("""
        SELECT DISTINCT m.high_seed_team_id as team_id
        FROM matchups m
        WHERE m.season = 2026
        AND m.high_seed_team_id NOT IN (
            SELECT team_id FROM bracket WHERE season = 2026
        )
        UNION
        SELECT DISTINCT m.low_seed_team_id as team_id
        FROM matchups m
        WHERE m.season = 2026
        AND m.low_seed_team_id NOT IN (
            SELECT team_id FROM bracket WHERE season = 2026
        )
    """).fetchall()
    
    if orphans:
        issues.append(f"Found {len(orphans)} orphaned teams in matchups")
        print(f"\n  ⚠ Orphaned matchup teams: {len(orphans)}")
    else:
        print(f"\n  ✓ No orphaned matchup teams")
    
    db.close()
    
    return len(issues) == 0, issues

def check_json_integrity():
    """Verify JSON files are valid"""
    print("\n" + "="*70)
    print("5. CHECKING JSON FILES")
    print("="*70)
    
    if not os.path.exists('bracket_matrix_teams.json'):
        print("  ✗ bracket_matrix_teams.json missing")
        return False
    
    try:
        with open('bracket_matrix_teams.json', 'r') as f:
            data = json.load(f)
        
        if len(data) != 68:
            print(f"  ⚠ bracket_matrix_teams.json has {len(data)} teams (expected 68)")
            return False
        else:
            print(f"  ✓ bracket_matrix_teams.json: {len(data)} teams")
            return True
    except json.JSONDecodeError as e:
        print(f"  ✗ bracket_matrix_teams.json is invalid JSON: {e}")
        return False

def main():
    """Run all checks"""
    print("\n" + "="*70)
    print("PRE-COMMIT VERIFICATION")
    print("Checking system before version control snapshot")
    print("="*70 + "\n")
    
    all_passed = True
    all_issues = []
    
    # Run checks
    files_ok = check_files()
    db_ok = check_database()
    data_ok, data_issues = check_data_integrity()
    bracket_ok, bracket_issues = check_bracket_integrity()
    json_ok = check_json_integrity()
    
    all_passed = files_ok and db_ok and data_ok and bracket_ok and json_ok
    all_issues.extend(data_issues)
    all_issues.extend(bracket_issues)
    
    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    print(f"\n  Files:            {'✓ PASS' if files_ok else '✗ FAIL'}")
    print(f"  Database:         {'✓ PASS' if db_ok else '✗ FAIL'}")
    print(f"  Data Integrity:   {'✓ PASS' if data_ok else '✗ FAIL'}")
    print(f"  Bracket Structure:{'✓ PASS' if bracket_ok else '✗ FAIL'}")
    print(f"  JSON Files:       {'✓ PASS' if json_ok else '✗ FAIL'}")
    
    if all_passed:
        print("\n" + "="*70)
        print("✓ ALL CHECKS PASSED - READY FOR VERSION CONTROL")
        print("="*70)
        print("\nYou can now safely:")
        print("  1. Initialize git repository (git init)")
        print("  2. Create .gitignore")
        print("  3. Commit baseline (git add . && git commit -m 'Initial commit')")
        return 0
    else:
        print("\n" + "="*70)
        print("✗ SOME CHECKS FAILED - FIX ISSUES BEFORE COMMITTING")
        print("="*70)
        
        if all_issues:
            print("\nIssues found:")
            for issue in all_issues:
                print(f"  - {issue}")
        
        return 1

if __name__ == '__main__':
    sys.exit(main())
