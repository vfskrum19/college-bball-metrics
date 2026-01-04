#!/usr/bin/env python3
"""
Find unmatched teams from Bracket Matrix
"""
import json
import sqlite3
from difflib import SequenceMatcher

DATABASE = 'kenpom.db'
BRACKET_JSON = 'bracket_matrix_teams.json'

def normalize_name(name):
    """Normalize team names for matching"""
    # Remove common suffixes
    name = name.replace(' St.', ' State')
    name = name.replace(' St', ' State')
    
    # Handle special cases
    replacements = {
        'Miami (FLA.)': 'Miami FL',
        'Miami (FL)': 'Miami FL',
        'St. Mary\'s (CA)': 'Saint Mary\'s',
        'St. John\'s': 'St John\'s',
        'USC': 'Southern California',
        'Central Florida': 'UCF',
        'Tennessee-Martin': 'UT Martin',
        'Long Island': 'LIU',
    }
    
    return replacements.get(name, name)

def similarity(a, b):
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_unmatched():
    """Find which teams from Bracket Matrix didn't match"""
    
    # Load Bracket Matrix teams
    with open(BRACKET_JSON, 'r') as f:
        bm_teams = json.load(f)
    
    # Load database teams
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db_teams = db.execute("SELECT team_id, name FROM teams WHERE season = 2026").fetchall()
    db_teams_dict = {t['team_id']: t['name'] for t in db_teams}
    
    # Load matched teams
    matched_ids = set()
    matched = db.execute("SELECT team_id FROM bracket WHERE season = 2026").fetchall()
    for m in matched:
        matched_ids.add(m['team_id'])
    
    db.close()
    
    print("="*70)
    print("UNMATCHED TEAMS ANALYSIS")
    print("="*70)
    
    # Find unmatched teams
    unmatched = []
    for bm_team in bm_teams:
        bm_name = bm_team['team_name']
        bm_normalized = normalize_name(bm_name)
        
        # Try to find best match
        best_match = None
        best_score = 0
        best_id = None
        
        for team_id, db_name in db_teams_dict.items():
            score = similarity(bm_normalized, db_name)
            if score > best_score:
                best_score = score
                best_match = db_name
                best_id = team_id
        
        # Check if this team was matched
        if best_id not in matched_ids:
            unmatched.append({
                'bm_name': bm_name,
                'bm_normalized': bm_normalized,
                'best_db_match': best_match,
                'similarity': best_score,
                'seed': bm_team['seed']
            })
    
    if unmatched:
        print(f"\n⚠ Found {len(unmatched)} unmatched teams:\n")
        for u in unmatched:
            print(f"Seed {u['seed']:2d}: {u['bm_name']:30s}")
            print(f"         Best DB match: {u['best_db_match']:30s} (similarity: {u['similarity']:.2%})")
            print()
    else:
        print("\n✓ All teams matched successfully!")
    
    print("="*70)
    print("DATABASE TEAM NAMES (sample)")
    print("="*70)
    print("\nShowing teams that might be the unmatched ones:\n")
    
    # Show some database teams that might help identify the issue
    sample_keywords = ['Miami', 'Mary', 'John', 'Central', 'Tennessee', 'Long', 'USC']
    for keyword in sample_keywords:
        matching = [name for name in db_teams_dict.values() if keyword.lower() in name.lower()]
        if matching:
            print(f"{keyword}: {', '.join(matching[:3])}")

if __name__ == '__main__':
    find_unmatched()
