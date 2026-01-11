import os
from pathlib import Path
import sqlite3
from datetime import datetime
from typing import List, Dict, Tuple
import json

# Get project root (parent of this file's directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = 2026

# Conference automatic qualifiers (you'll need to update this with actual tournament winners)
# For now, we'll use a placeholder - in production, you'd scrape this or maintain it
AUTO_QUALIFIERS = {}  # Format: {'ACC': 'Duke', 'Big Ten': 'Purdue', ...}

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def get_all_teams_with_resumes(season=CURRENT_SEASON):
    """Get all teams with their complete resume data"""
    db = get_db()
    
    query = '''
        SELECT 
            t.team_id,
            t.name,
            t.conference,
            r.wins,
            r.losses,
            r.adj_em,
            r.rank_adj_em,
            rm.net_rank,
            COALESCE(rm.quad1_wins, 0) as quad1_wins,
            COALESCE(rm.quad1_losses, 0) as quad1_losses,
            COALESCE(rm.quad2_wins, 0) as quad2_wins,
            COALESCE(rm.quad2_losses, 0) as quad2_losses,
            COALESCE(rm.quad3_wins, 0) as quad3_wins,
            COALESCE(rm.quad3_losses, 0) as quad3_losses,
            COALESCE(rm.quad4_wins, 0) as quad4_wins,
            COALESCE(rm.quad4_losses, 0) as quad4_losses
        FROM teams t
        LEFT JOIN ratings r ON t.team_id = r.team_id AND r.season = ?
        LEFT JOIN resume_metrics rm ON t.team_id = rm.team_id AND rm.season = ?
        WHERE t.season = ?
        ORDER BY rm.net_rank
    '''
    
    teams = db.execute(query, (season, season, season)).fetchall()
    db.close()
    
    return [dict(team) for team in teams]

def calculate_resume_score(team: Dict) -> float:
    """
    Calculate a resume score that mirrors NCAA committee priorities
    Higher score = better resume
    """
    score = 0.0
    
    # Handle teams without resume data
    if not team.get('net_rank'):
        return -1000  # Very low score for teams without data
    
    # ========== TIER 1: MOST IMPORTANT ==========
    
    # NET Ranking (inverse - lower is better)
    # Scale: #1 NET = +500 points, #100 NET = +50 points, #200 NET = -50 points
    net_score = max(0, 550 - (team['net_rank'] * 2.5))
    score += net_score
    
    # Quadrant 1 Wins (HEAVILY weighted - most important resume component)
    # Each Q1 win worth 100 points
    q1_wins = team.get('quad1_wins') or 0
    score += q1_wins * 100
    
    # Q1 Win Percentage (bonus for high success rate in Q1)
    q1_losses = team.get('quad1_losses') or 0
    q1_total = q1_wins + q1_losses
    if q1_total > 0:
        q1_pct = q1_wins / q1_total
        score += q1_pct * 50  # Up to +50 for perfect Q1 record
    
    # ========== TIER 2: IMPORTANT ==========
    
    # Quadrant 2 Wins (moderate weight)
    # Each Q2 win worth 40 points
    q2_wins = team.get('quad2_wins') or 0
    score += q2_wins * 40
    
    # Overall Record (winning percentage matters)
    wins = team.get('wins', 0)
    losses = team.get('losses', 0)
    if wins + losses > 0:
        win_pct = wins / (wins + losses)
        score += win_pct * 100  # Up to +100 for undefeated
    
    # ========== TIER 3: PENALTIES (Bad Losses) ==========
    
    # Q3 Losses (yellow flag - penalize but not fatal)
    # Each Q3 loss: -75 points
    q3_losses = team.get('quad3_losses') or 0
    score -= q3_losses * 75
    
    # Q4 Losses (SEVERE penalty - committee hates these)
    # Each Q4 loss: -200 points (often disqualifying)
    q4_losses = team.get('quad4_losses') or 0
    score -= q4_losses * 200
    
    # ========== TIER 4: BONUS FACTORS ==========
    
    # KenPom Adjusted Efficiency Margin (predictive power)
    # Top teams get small bonus
    if team.get('rank_adj_em') and team['rank_adj_em'] <= 25:
        score += (26 - team['rank_adj_em']) * 5
    
    return round(score, 2)

def select_at_large_teams(teams: List[Dict], auto_bids: List[str], num_at_large=36) -> List[Dict]:
    """
    Select at-large teams using committee-style resume evaluation
    
    Returns: List of at-large selections sorted by resume score
    """
    # Filter out automatic qualifiers
    eligible = [t for t in teams if t['name'] not in auto_bids]
    
    # Calculate resume score for each team
    for team in eligible:
        team['resume_score'] = calculate_resume_score(team)
        
        # Calculate combined record for display
        total_wins = team.get('wins', 0)
        total_losses = team.get('losses', 0)
        team['record'] = f"{total_wins}-{total_losses}"
        
        # Calculate Q1+Q2 combined record (important metric)
        q12_wins = (team.get('quad1_wins') or 0) + (team.get('quad2_wins') or 0)
        q12_losses = (team.get('quad1_losses') or 0) + (team.get('quad2_losses') or 0)
        team['q12_record'] = f"{q12_wins}-{q12_losses}"
    
    # Sort by resume score (highest first)
    eligible.sort(key=lambda x: x['resume_score'], reverse=True)
    
    # Select top teams
    at_large = eligible[:num_at_large]
    bubble = {
        'last_four_byes': eligible[32:36],  # Teams 33-36
        'last_four_in': eligible[36:40],    # Teams 37-40 (First Four)
        'first_four_out': eligible[40:44],  # Teams 41-44
        'next_four_out': eligible[44:48]    # Teams 45-48
    }
    
    return at_large, bubble

def create_s_curve(auto_bids: List[Dict], at_large: List[Dict]) -> List[Dict]:
    """
    Combine all tournament teams and create S-curve ranking (1-68)
    """
    all_teams = auto_bids + at_large
    
    # Re-calculate scores for all teams
    for team in all_teams:
        if 'resume_score' not in team:
            team['resume_score'] = calculate_resume_score(team)
    
    # Sort by resume score (S-curve ranking)
    all_teams.sort(key=lambda x: x['resume_score'], reverse=True)
    
    # Assign overall seeds (1-68)
    for idx, team in enumerate(all_teams, 1):
        team['overall_seed'] = idx
        # Assign seed line (1-16, with duplicates)
        team['seed_line'] = ((idx - 1) // 4) + 1
    
    return all_teams

def assign_regions(s_curve_teams: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Distribute teams into 4 regions following NCAA bracketing principles
    """
    regions = {
        'East': [],
        'West': [],
        'South': [],
        'Midwest': []
    }
    
    region_names = list(regions.keys())
    
    # Distribute teams by seed line
    for seed_line in range(1, 17):
        # Get all teams on this seed line (should be 4 teams)
        seed_teams = [t for t in s_curve_teams if t['seed_line'] == seed_line]
        
        # For #1 seeds, assign to regions based on S-curve order
        # For other seeds, distribute to balance regions
        for idx, team in enumerate(seed_teams):
            if seed_line == 1:
                # #1 seeds go in order: East(1), West(2), South(3), Midwest(4)
                regions[region_names[idx]].append(team)
            else:
                # Balance distribution across regions
                # Serpentine pattern to balance strength
                region_idx = idx % 4
                regions[region_names[region_idx]].append(team)
    
    return regions

def create_first_round_matchups(regions: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Create first round matchups for each region
    Standard NCAA bracket matchups: 1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15
    """
    matchup_pairings = [
        (1, 16), (8, 9), (5, 12), (4, 13),
        (6, 11), (3, 14), (7, 10), (2, 15)
    ]
    
    bracket_with_matchups = {}
    
    for region_name, teams in regions.items():
        # Sort teams by seed within region
        teams_by_seed = {}
        for team in teams:
            seed = team['seed_line']
            if seed not in teams_by_seed:
                teams_by_seed[seed] = []
            teams_by_seed[seed].append(team)
        
        # Create matchups
        region_matchups = []
        for high_seed, low_seed in matchup_pairings:
            if high_seed in teams_by_seed and low_seed in teams_by_seed:
                matchup = {
                    'game_number': len(region_matchups) + 1,
                    'high_seed': teams_by_seed[high_seed][0],
                    'low_seed': teams_by_seed[low_seed][0],
                    'location': 'TBD'  # Would be determined by pod system
                }
                region_matchups.append(matchup)
        
        bracket_with_matchups[region_name] = region_matchups
    
    return bracket_with_matchups

def generate_bracket(season=CURRENT_SEASON, auto_qualifiers=None):
    """
    Main function to generate complete NCAA tournament bracket
    
    Returns: Complete bracket structure with all teams, seeds, and matchups
    """
    print(f"\n{'='*70}")
    print(f"Generating NCAA Tournament Bracket for {season} Season")
    print(f"{'='*70}\n")
    
    # Step 1: Get all teams with resumes
    print("Step 1: Loading team resume data...")
    all_teams = get_all_teams_with_resumes(season)
    print(f"✓ Loaded {len(all_teams)} teams")
    
    # Step 2: Identify automatic qualifiers
    # For now, we'll select top team from each major conference
    # In production, you'd track actual conference tournament winners
    print("\nStep 2: Identifying automatic qualifiers...")
    auto_bids_names = list(auto_qualifiers.values()) if auto_qualifiers else []
    auto_bid_teams = [t for t in all_teams if t['name'] in auto_bids_names]
    print(f"✓ {len(auto_bid_teams)} automatic qualifiers")
    
    # Step 3: Select at-large teams
    print("\nStep 3: Selecting at-large teams...")
    at_large, bubble = select_at_large_teams(all_teams, auto_bids_names)
    print(f"✓ Selected {len(at_large)} at-large teams")
    
    # Step 4: Create S-curve (rank all 68 teams)
    print("\nStep 4: Creating S-curve ranking...")
    s_curve = create_s_curve(auto_bid_teams, at_large)
    print(f"✓ Ranked all {len(s_curve)} tournament teams")
    
    # Step 5: Assign teams to regions
    print("\nStep 5: Assigning teams to regions...")
    regions = assign_regions(s_curve)
    for region, teams in regions.items():
        print(f"  {region}: {len(teams)} teams")
    
    # Step 6: Create first round matchups
    print("\nStep 6: Creating first round matchups...")
    matchups = create_first_round_matchups(regions)
    total_games = sum(len(games) for games in matchups.values())
    print(f"✓ Created {total_games} first round games")
    
    print(f"\n{'='*70}")
    print(f"Bracket generation complete!")
    print(f"{'='*70}\n")
    
    return {
        'season': season,
        'generated_at': datetime.now().isoformat(),
        'field_of_68': s_curve,
        'bubble': bubble,
        'regions': regions,
        'matchups': matchups,
        'selection_stats': {
            'auto_bids': len(auto_bid_teams),
            'at_large': len(at_large),
            'total': len(s_curve)
        }
    }

def save_bracket_to_database(bracket_data, season=CURRENT_SEASON):
    """Save generated bracket to database"""
    db = get_db()
    cursor = db.cursor()
    
    # Create bracket table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bracket (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            seed INTEGER,
            region TEXT,
            overall_rank INTEGER,
            resume_score REAL,
            is_auto_bid INTEGER,
            generated_at TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Clear existing bracket for this season
    cursor.execute('DELETE FROM bracket WHERE season = ?', (season,))
    
    # Insert bracket data
    for team in bracket_data['field_of_68']:
        # Find which region this team is in
        team_region = None
        for region, teams in bracket_data['regions'].items():
            if any(t['team_id'] == team['team_id'] for t in teams):
                team_region = region
                break
        
        cursor.execute('''
            INSERT INTO bracket (
                team_id, season, seed, region, overall_rank, 
                resume_score, generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            team['team_id'],
            season,
            team['seed_line'],
            team_region,
            team['overall_seed'],
            team.get('resume_score', 0),
            bracket_data['generated_at']
        ))
    
    db.commit()
    db.close()
    print("✓ Bracket saved to database")

def print_bracket_preview(bracket_data):
    """Print a preview of the bracket"""
    print("\n" + "="*70)
    print("BRACKET PREVIEW - TOP 16 SEEDS")
    print("="*70)
    
    for i in range(1, 5):
        seed_teams = [t for t in bracket_data['field_of_68'] if t['seed_line'] == i]
        print(f"\n{i}-SEEDS:")
        for team in seed_teams:
            q1_record = f"{team.get('quad1_wins', 0)}-{team.get('quad1_losses', 0)}"
            net_rank = team.get('net_rank', 'N/A')
            net_display = str(net_rank) if net_rank != 'N/A' else 'N/A'
            print(f"  #{team['overall_seed']:2d} {team['name']:30s} "
                  f"({team['record']:7s}, NET: {net_display:>3s}, "
                  f"Q1: {q1_record})")
    
    print("\n" + "="*70)
    print("BUBBLE TEAMS")
    print("="*70)
    
    categories = [
        ('LAST FOUR BYES', bracket_data['bubble']['last_four_byes']),
        ('LAST FOUR IN', bracket_data['bubble']['last_four_in']),
        ('FIRST FOUR OUT', bracket_data['bubble']['first_four_out']),
        ('NEXT FOUR OUT', bracket_data['bubble']['next_four_out'])
    ]
    
    for category_name, teams in categories:
        print(f"\n{category_name}:")
        for team in teams:
            q1_record = f"{team.get('quad1_wins', 0)}-{team.get('quad1_losses', 0)}"
            bad_losses = (team.get('quad3_losses') or 0) + (team.get('quad4_losses') or 0)
            net_rank = team.get('net_rank', 'N/A')
            net_display = str(net_rank) if net_rank != 'N/A' else 'N/A'
            print(f"  {team['name']:30s} ({team['record']:7s}, "
                  f"NET: {net_display:>3s}, Q1: {q1_record}, "
                  f"Bad L: {bad_losses})")

if __name__ == '__main__':
    # Generate bracket
    bracket = generate_bracket(CURRENT_SEASON)
    
    # Save to database
    save_bracket_to_database(bracket, CURRENT_SEASON)
    
    # Print preview
    print_bracket_preview(bracket)
    
    # Optionally save to JSON file
    with open('bracket.json', 'w') as f:
        # Convert to JSON-serializable format
        json_bracket = {
            'season': bracket['season'],
            'generated_at': bracket['generated_at'],
            'selection_stats': bracket['selection_stats'],
            'field_of_68': bracket['field_of_68'],
            'bubble': bracket['bubble']
        }
        json.dump(json_bracket, f, indent=2)
    print("\n✓ Bracket saved to bracket.json")