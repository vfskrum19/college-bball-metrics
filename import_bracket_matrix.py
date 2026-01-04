import requests
from bs4 import BeautifulSoup
import sqlite3
import os
import json
from difflib import SequenceMatcher
from datetime import datetime
import urllib3

# Suppress SSL warnings since Bracket Matrix doesn't have valid cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATABASE = 'kenpom.db'
BRACKET_MATRIX_URL = "https://www.bracketmatrix.com"
CURRENT_SEASON = 2026

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def similarity(a, b):
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_name(name):
    """Normalize team names for better matching"""
    # Handle specific known mappings first (before lowercasing)
    exact_mappings = {
        'USC': 'USC',  # Keep USC as-is
        'Central Florida': 'UCF',
        'Tennessee-Martin': 'UT Martin',
        'Long Island': 'LIU',
        'Miami (FLA.)': 'Miami FL',
        'Miami (FL)': 'Miami FL',
        'St. Mary\'s (CA)': 'Saint Mary\'s',
        'St. Mary\'s': 'Saint Mary\'s',
        'St. John\'s': 'St. John\'s',
    }
    
    # Check exact mappings first
    if name in exact_mappings:
        return exact_mappings[name]
    
    # Now do general normalization
    name = name.lower().strip()
    
    replacements = {
        'state': 'st.',
        'saint': 'st.',
        'st ': 'st. ',
        'university': '',
        'college': '',
        ' the ': ' ',
    }
    
    for old, new in replacements.items():
        name = name.replace(old, new)
    
    name = ' '.join(name.split())
    return name

def scrape_bracket_matrix():
    """
    Scrape Bracket Matrix for consensus bracket seeds
    Returns: List of teams with their seed and region
    """
    print(f"Fetching bracket from Bracket Matrix...")
    
    # First, try to load from JSON file if it exists
    json_file = '/home/claude/bracket_matrix_teams.json'
    if os.path.exists(json_file):
        print(f"Found local bracket data file: {json_file}")
        try:
            with open(json_file, 'r') as f:
                bracket_teams = json.load(f)
            print(f"✓ Loaded {len(bracket_teams)} teams from local file")
            return bracket_teams
        except Exception as e:
            print(f"Warning: Could not load from JSON file: {e}")
            print("Attempting web scrape...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # Bracket Matrix doesn't have valid SSL cert, so disable verification
        response = requests.get(BRACKET_MATRIX_URL, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Bracket Matrix typically has tables for each region
        # The structure may vary, so we'll need to inspect it
        # For now, let's find all tables and see what we get
        
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables on page")
        
        bracket_teams = []
        
        # Look for the main bracket table
        # Bracket Matrix table structure: [seed, team_name, conference, avg_seed, ...]
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 4:  # Need at least header rows + some data
                continue
            
            print(f"Processing table with {len(rows)} rows")
            
            # Parse all rows looking for valid team data
            # Skip first 3 rows (headers and empty row based on debug output)
            for row in rows[3:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    seed_text = cells[0].get_text(strip=True)
                    team_text = cells[1].get_text(strip=True)
                    conference_text = cells[2].get_text(strip=True)
                    
                    # Parse seed (must be integer 1-16)
                    try:
                        seed = int(seed_text)
                        # Valid team entry: has seed 1-16, team name, and looks legitimate
                        if 1 <= seed <= 16 and team_text and len(team_text) > 2:
                            bracket_teams.append({
                                'team_name': team_text,
                                'seed': seed,
                                'conference': conference_text,
                                'region': None  # Will assign later
                            })
                    except (ValueError, TypeError):
                        # Not a valid seed number, skip this row
                        continue
        
        print(f"✓ Scraped {len(bracket_teams)} teams from Bracket Matrix")
        return bracket_teams
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching Bracket Matrix: {e}")
        print(f"\nTo use offline data:")
        print(f"1. Run save_bracket_data.py on your local machine with the HTML file")
        print(f"2. Upload the generated bracket_matrix_teams.json file")
        print(f"3. Run this script again")
        return []

def match_bracket_teams_to_database(bracket_teams, season=CURRENT_SEASON):
    """Match Bracket Matrix team names to KenPom database"""
    db = get_db()
    
    kenpom_teams = db.execute(
        'SELECT team_id, name FROM teams WHERE season = ?',
        (season,)
    ).fetchall()
    
    kenpom_teams_list = [{'team_id': t['team_id'], 'name': t['name']} for t in kenpom_teams]
    
    matches = []
    unmatched = []
    
    for bracket_team in bracket_teams:
        bm_name = bracket_team['team_name']
        bm_normalized = normalize_name(bm_name)
        
        best_match = None
        best_score = 0
        
        for kp_team in kenpom_teams_list:
            kp_name = kp_team['name']
            kp_normalized = normalize_name(kp_name)
            
            scores = [
                similarity(bm_name, kp_name),
                similarity(bm_normalized, kp_normalized),
                similarity(bm_name.lower(), kp_name.lower())
            ]
            
            max_score = max(scores)
            
            if max_score > best_score:
                best_score = max_score
                best_match = kp_team
        
        if best_score > 0.75:
            matches.append({
                'team_id': best_match['team_id'],
                'team_name': best_match['name'],
                'bracket_matrix_name': bm_name,
                'seed': bracket_team['seed'],
                'region': bracket_team['region'],
                'confidence': best_score
            })
        else:
            unmatched.append({
                'bracket_matrix_name': bm_name,
                'seed': bracket_team['seed'],
                'best_match': best_match['name'] if best_match else 'None',
                'confidence': best_score
            })
    
    db.close()
    
    print(f"✓ Matched {len(matches)} teams ({len(matches)/len(bracket_teams)*100:.1f}%)")
    
    if unmatched:
        print(f"\n⚠️  {len(unmatched)} teams not matched:")
        for team in unmatched[:10]:
            print(f"  - {team['bracket_matrix_name']} (seed {team['seed']}, "
                  f"best: {team['best_match']}, {team['confidence']:.2f})")
        if len(unmatched) > 10:
            print(f"  ... and {len(unmatched) - 10} more")
    
    return matches, unmatched

def assign_regions_by_geography(seeded_teams):
    """
    Assign teams to regions following NCAA principles:
    1. Top 4 seeds (1-4) distributed to balance regions
    2. Other seeds distributed to maintain competitive balance
    3. Geographic preference when possible
    
    Regions: East, West, South, Midwest
    """
    regions = {
        'East': [],
        'West': [],
        'South': [],
        'Midwest': []
    }
    
    region_names = ['East', 'West', 'South', 'Midwest']
    
    # Group teams by seed line
    teams_by_seed = {}
    for team in seeded_teams:
        seed = team['seed']
        if seed not in teams_by_seed:
            teams_by_seed[seed] = []
        teams_by_seed[seed].append(team)
    
    # Assign teams to regions
    # For each seed line (1-16), distribute the 4 teams across regions
    for seed in range(1, 17):
        if seed not in teams_by_seed:
            continue
        
        seed_teams = teams_by_seed[seed]
        
        # Sort by some criteria (for now, alphabetically to be deterministic)
        seed_teams.sort(key=lambda x: x['team_name'])
        
        # Distribute across regions
        for idx, team in enumerate(seed_teams):
            region_idx = idx % 4
            team['region'] = region_names[region_idx]
            regions[region_names[region_idx]].append(team)
    
    return regions

def create_matchups_from_regions(regions):
    """
    Create first round matchups following NCAA bracket format
    Standard matchups: 1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15
    
    Also creates play-in games (First Four) when there are multiple teams
    on the same seed line in a region (typically 11 and 16 seeds)
    """
    matchup_pairings = [
        (1, 16), (8, 9), (5, 12), (4, 13),
        (6, 11), (3, 14), (7, 10), (2, 15)
    ]
    
    all_matchups = {}
    
    for region_name, teams in regions.items():
        # Group teams by seed
        teams_by_seed = {}
        for team in teams:
            seed = team['seed']
            if seed not in teams_by_seed:
                teams_by_seed[seed] = []
            teams_by_seed[seed].append(team)
        
        region_matchups = []
        game_num = 1
        
        # First, create play-in games for seeds with multiple teams
        play_in_seeds = {}
        for seed, seed_teams in teams_by_seed.items():
            if len(seed_teams) > 1:
                # Create play-in game
                play_in_matchup = {
                    'game_number': game_num,
                    'region': region_name,
                    'round': 0,  # Round 0 = play-in game
                    'matchup_name': f"{seed} vs {seed} (Play-In)",
                    'high_seed_team': seed_teams[0],
                    'low_seed_team': seed_teams[1],
                }
                region_matchups.append(play_in_matchup)
                game_num += 1
                
                # Store that this seed has a play-in
                # For first round, we'll use "TBD" or the first team as placeholder
                play_in_seeds[seed] = play_in_matchup
        
        # Create first round matchups
        for high_seed, low_seed in matchup_pairings:
            if high_seed in teams_by_seed and low_seed in teams_by_seed:
                # Determine the teams
                if high_seed in play_in_seeds:
                    # High seed has play-in game
                    high_team = teams_by_seed[high_seed][0]  # Use first as placeholder
                    high_team_note = " (Play-In Winner)"
                else:
                    high_team = teams_by_seed[high_seed][0] if teams_by_seed[high_seed] else None
                    high_team_note = ""
                
                if low_seed in play_in_seeds:
                    # Low seed has play-in game
                    low_team = teams_by_seed[low_seed][0]  # Use first as placeholder
                    low_team_note = " (Play-In Winner)"
                else:
                    low_team = teams_by_seed[low_seed][0] if teams_by_seed[low_seed] else None
                    low_team_note = ""
                
                if high_team and low_team:
                    matchup = {
                        'game_number': game_num,
                        'region': region_name,
                        'round': 1,  # Round 1 = first round
                        'matchup_name': f"{high_seed} vs {low_seed}",
                        'high_seed_team': high_team,
                        'low_seed_team': low_team,
                        'high_team_note': high_team_note,
                        'low_team_note': low_team_note,
                    }
                    region_matchups.append(matchup)
                    game_num += 1
        
        all_matchups[region_name] = region_matchups
    
    return all_matchups

def save_bracket_to_database(regions, matchups, season=CURRENT_SEASON):
    """Save bracket and matchups to database"""
    db = get_db()
    cursor = db.cursor()
    
    # Create bracket table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bracket (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            seed INTEGER,
            region TEXT,
            source TEXT,
            generated_at TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Create matchups table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matchups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER,
            region TEXT,
            round INTEGER,
            game_number INTEGER,
            high_seed_team_id INTEGER,
            low_seed_team_id INTEGER,
            matchup_name TEXT,
            generated_at TIMESTAMP,
            FOREIGN KEY (high_seed_team_id) REFERENCES teams (team_id),
            FOREIGN KEY (low_seed_team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Clear existing data
    cursor.execute('DELETE FROM bracket WHERE season = ?', (season,))
    cursor.execute('DELETE FROM matchups WHERE season = ? AND round IN (0, 1)', (season,))
    
    timestamp = datetime.now().isoformat()
    
    # Insert bracket data
    for region_name, teams in regions.items():
        for team in teams:
            cursor.execute('''
                INSERT INTO bracket (team_id, season, seed, region, source, generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                team['team_id'],
                season,
                team['seed'],
                region_name,
                'Bracket Matrix',
                timestamp
            ))
    
    # Insert matchup data
    for region_name, games in matchups.items():
        for game in games:
            cursor.execute('''
                INSERT INTO matchups (
                    season, region, round, game_number,
                    high_seed_team_id, low_seed_team_id, matchup_name, generated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                season,
                region_name,
                game.get('round', 1),  # Use round from game, default to 1 if not specified
                game['game_number'],
                game['high_seed_team']['team_id'],
                game['low_seed_team']['team_id'],
                game['matchup_name'],
                timestamp
            ))
    
    db.commit()
    db.close()
    
    print("✓ Bracket and matchups saved to database")

def generate_bracket_from_matrix(season=CURRENT_SEASON):
    """Main function to generate bracket from Bracket Matrix"""
    print(f"\n{'='*70}")
    print(f"Generating NCAA Tournament Bracket from Bracket Matrix")
    print(f"{'='*70}\n")
    
    # Step 1: Scrape Bracket Matrix
    bracket_teams = scrape_bracket_matrix()
    if not bracket_teams:
        print("❌ Failed to scrape Bracket Matrix")
        return None
    
    # Step 2: Match to database
    print("\nMatching teams to database...")
    matched_teams, unmatched = match_bracket_teams_to_database(bracket_teams, season)
    
    # Step 3: Assign to regions
    print("\nAssigning teams to regions...")
    regions = assign_regions_by_geography(matched_teams)
    for region, teams in regions.items():
        print(f"  {region}: {len(teams)} teams")
    
    # Step 4: Create matchups
    print("\nCreating matchups...")
    matchups = create_matchups_from_regions(regions)
    
    # Count play-in vs first-round
    total_games = sum(len(games) for games in matchups.values())
    play_in_count = sum(1 for games in matchups.values() for g in games if g.get('round', 1) == 0)
    first_round_count = total_games - play_in_count
    
    print(f"✓ Created {play_in_count} play-in games")
    print(f"✓ Created {first_round_count} first-round matchups")
    print(f"✓ Total: {total_games} games")
    
    # Step 5: Save to database
    print("\nSaving to database...")
    save_bracket_to_database(regions, matchups, season)
    
    print(f"\n{'='*70}")
    print(f"Bracket generation complete!")
    print(f"Source: Bracket Matrix consensus")
    print(f"{'='*70}\n")
    
    return {
        'regions': regions,
        'matchups': matchups,
        'unmatched': unmatched
    }

def print_bracket_summary(bracket_data):
    """Print a summary of the generated bracket"""
    
    # Separate play-in games from first-round matchups
    play_in_games = {}
    first_round_games = {}
    
    for region, games in bracket_data['matchups'].items():
        play_in_games[region] = [g for g in games if g.get('round', 1) == 0]
        first_round_games[region] = [g for g in games if g.get('round', 1) == 1]
    
    # Print play-in games
    total_play_ins = sum(len(games) for games in play_in_games.values())
    if total_play_ins > 0:
        print("\n" + "="*70)
        print("PLAY-IN GAMES (FIRST FOUR)")
        print("="*70)
        
        for region, games in play_in_games.items():
            if games:
                print(f"\n{region.upper()} REGION:")
                for game in games:
                    high = game['high_seed_team']
                    low = game['low_seed_team']
                    print(f"  ({high['seed']}) {high['team_name']:25s} vs "
                          f"({low['seed']}) {low['team_name']}")
    
    # Print first-round matchups
    print("\n" + "="*70)
    print("FIRST ROUND MATCHUPS BY REGION")
    print("="*70)
    
    for region, games in first_round_games.items():
        if games:
            print(f"\n{region.upper()} REGION:")
            for game in games:
                high = game['high_seed_team']
                low = game['low_seed_team']
                
                # Add note if team is from play-in
                high_note = game.get('high_team_note', '')
                low_note = game.get('low_team_note', '')
                
                print(f"  ({high['seed']}) {high['team_name']:25s}{high_note:20s} vs "
                      f"({low['seed']}) {low['team_name']}{low_note}")

if __name__ == '__main__':
    bracket = generate_bracket_from_matrix(CURRENT_SEASON)
    
    if bracket:
        print_bracket_summary(bracket)