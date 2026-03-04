"""
Import bracket data from Bracket Matrix (consensus bracket seeds).

Scrapes bracketmatrix.com or loads from a local JSON file if available.

Run from project root:
    python scrapers/import_bracket_matrix.py
"""

import sys
import json
import os
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from utils.db import get_db, close_db, execute, commit, db_type

BRACKET_MATRIX_URL = "https://www.bracketmatrix.com"
CURRENT_SEASON = 2026

EXACT_TEAM_MAPPINGS = {
    'NC State': 'N.C. State', 'N.C. State': 'N.C. State',
    'North Carolina State': 'N.C. State',
    'North Carolina A&T': 'North Carolina A&T', 'NC A&T': 'North Carolina A&T',
    'USC': 'USC', 'UCF': 'UCF', 'Central Florida': 'UCF',
    'UConn': 'Connecticut', 'Connecticut': 'Connecticut',
    'Miami (FL)': 'Miami FL', 'Miami (FLA.)': 'Miami FL',
    'Miami Florida': 'Miami FL', 'Miami (OH)': 'Miami OH',
    'Miami Ohio': 'Miami OH', 'Ole Miss': 'Mississippi',
    "St. John's": "St. John's", "Saint John's": "St. John's",
    "St. Mary's": "Saint Mary's", "Saint Mary's (CA)": "Saint Mary's",
    "St. Mary's (CA)": "Saint Mary's",
    'LSU': 'LSU', 'Louisiana State': 'LSU', 'BYU': 'BYU',
    'Brigham Young': 'BYU', 'VCU': 'VCU',
    'Virginia Commonwealth': 'VCU', 'SMU': 'SMU',
    'Southern Methodist': 'SMU', 'TCU': 'TCU',
    'Texas Christian': 'TCU', 'UNLV': 'UNLV',
    'Nevada-Las Vegas': 'UNLV', 'Pitt': 'Pittsburgh',
    'Pittsburgh': 'Pittsburgh', 'UMass': 'Massachusetts',
    'Massachusetts': 'Massachusetts', 'Long Island': 'LIU', 'LIU': 'LIU',
    'Tennessee-Martin': 'UT Martin', 'UT Martin': 'UT Martin',
    'McNeese State': 'McNeese',
}


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_name(name):
    if name in EXACT_TEAM_MAPPINGS:
        return EXACT_TEAM_MAPPINGS[name]
    normalized = name.lower().strip()
    for old, new in [('university', ''), ('college', ''), (' the ', ' ')]:
        normalized = normalized.replace(old, new)
    return ' '.join(normalized.split())


def scrape_bracket_matrix():
    """Scrape Bracket Matrix for consensus seeds, or load from local JSON."""
    print("Fetching bracket from Bracket Matrix...")

    json_file = PROJECT_ROOT / 'bracket_matrix_teams.json'
    if json_file.exists():
        print(f"Found local bracket data: {json_file}")
        try:
            with open(json_file, 'r') as f:
                teams = json.load(f)
            print(f"✓ Loaded {len(teams)} teams from local file")
            return teams
        except Exception as e:
            print(f"Warning: Could not load JSON file: {e}")

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(BRACKET_MATRIX_URL, headers=headers, timeout=30, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables on page")

        bracket_teams = []
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 4:
                continue
            for row in rows[3:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    try:
                        seed = int(cells[0].get_text(strip=True))
                        team = cells[1].get_text(strip=True)
                        conf = cells[2].get_text(strip=True)
                        if 1 <= seed <= 16 and team and len(team) > 2:
                            bracket_teams.append({
                                'team_name': team, 'seed': seed,
                                'conference': conf, 'region': None
                            })
                    except (ValueError, TypeError):
                        continue

        print(f"✓ Scraped {len(bracket_teams)} teams")
        return bracket_teams

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching Bracket Matrix: {e}")
        print("\nTip: Save bracket_matrix_teams.json to project root and re-run.")
        return []


def match_bracket_teams(bracket_teams, season=CURRENT_SEASON):
    db = get_db()
    kenpom_teams = [{'team_id': t['team_id'], 'name': t['name']}
                    for t in execute(db, 'SELECT team_id, name FROM teams WHERE season = ?',
                                     (season,)).fetchall()]
    close_db(db)

    kenpom_by_name = {t['name']: t for t in kenpom_teams}
    kenpom_by_lower = {t['name'].lower(): t for t in kenpom_teams}

    matches = []
    unmatched = []

    for team in bracket_teams:
        bm_name = team['team_name']
        kp_team = None

        if bm_name in EXACT_TEAM_MAPPINGS:
            mapped = EXACT_TEAM_MAPPINGS[bm_name]
            kp_team = kenpom_by_name.get(mapped)

        if not kp_team:
            kp_team = kenpom_by_lower.get(bm_name.lower())

        if not kp_team:
            best_score = 0
            bm_norm = normalize_name(bm_name)
            for kt in kenpom_teams:
                score = max(similarity(bm_name, kt['name']),
                            similarity(bm_norm, normalize_name(kt['name'])))
                if score > best_score:
                    best_score = score
                    if score > 0.75:
                        kp_team = kt

        if kp_team:
            matches.append({
                'team_id': kp_team['team_id'],
                'team_name': kp_team['name'],
                'bracket_matrix_name': bm_name,
                'seed': team['seed'],
                'region': team['region'],
            })
        else:
            unmatched.append({'bracket_matrix_name': bm_name, 'seed': team['seed']})

    print(f"✓ Matched {len(matches)}/{len(bracket_teams)} teams")
    if unmatched:
        print(f"⚠️  {len(unmatched)} unmatched:")
        for t in unmatched[:10]:
            print(f"  - ({t['seed']}) {t['bracket_matrix_name']}")
    return matches, unmatched


def assign_regions(seeded_teams):
    """Distribute teams across regions by seed line."""
    region_names = ['East', 'West', 'South', 'Midwest']
    teams_by_seed = {}
    for team in seeded_teams:
        teams_by_seed.setdefault(team['seed'], []).append(team)

    regions = {r: [] for r in region_names}
    for seed in range(1, 17):
        for idx, team in enumerate(sorted(teams_by_seed.get(seed, []),
                                          key=lambda x: x['team_name'])):
            region = region_names[idx % 4]
            team['region'] = region
            regions[region].append(team)

    return regions


def create_matchups(regions):
    """Create first-round matchups (1v16, 8v9, etc.)."""
    pairings = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]
    all_matchups = {}

    for region_name, teams in regions.items():
        by_seed = {}
        for team in teams:
            by_seed.setdefault(team['seed'], []).append(team)

        region_games = []
        game_num = 1

        # Play-in games for seeds with 2+ teams
        play_in_seeds = set()
        for seed, seed_teams in by_seed.items():
            if len(seed_teams) > 1:
                region_games.append({
                    'game_number': game_num, 'region': region_name,
                    'round': 0, 'matchup_name': f"{seed} vs {seed} (Play-In)",
                    'high_seed_team': seed_teams[0],
                    'low_seed_team': seed_teams[1],
                })
                play_in_seeds.add(seed)
                game_num += 1

        # First-round matchups
        for hi, lo in pairings:
            if hi in by_seed and lo in by_seed:
                region_games.append({
                    'game_number': game_num, 'region': region_name,
                    'round': 1, 'matchup_name': f"{hi} vs {lo}",
                    'high_seed_team': by_seed[hi][0],
                    'low_seed_team': by_seed[lo][0],
                })
                game_num += 1

        all_matchups[region_name] = region_games

    return all_matchups


def save_to_database(regions, matchups, season=CURRENT_SEASON):
    db = get_db()

    # Ensure tables exist
    execute(db, '''
        CREATE TABLE IF NOT EXISTS bracket (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER, season INTEGER,
            seed INTEGER, region TEXT, source TEXT,
            generated_at TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    execute(db, '''
        CREATE TABLE IF NOT EXISTS matchups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER, region TEXT,
            round INTEGER, game_number INTEGER,
            high_seed_team_id INTEGER, low_seed_team_id INTEGER,
            matchup_name TEXT, generated_at TIMESTAMP,
            FOREIGN KEY (high_seed_team_id) REFERENCES teams (team_id),
            FOREIGN KEY (low_seed_team_id) REFERENCES teams (team_id)
        )
    ''')

    execute(db, 'DELETE FROM bracket WHERE season = ?', (season,))
    execute(db, 'DELETE FROM matchups WHERE season = ? AND round IN (0, 1)', (season,))

    timestamp = datetime.now().isoformat()

    for region_name, teams in regions.items():
        for team in teams:
            execute(db, '''
                INSERT INTO bracket (team_id, season, seed, region, source, generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (team['team_id'], season, team['seed'], region_name,
                  'Bracket Matrix', timestamp))

    for region_name, games in matchups.items():
        for game in games:
            execute(db, '''
                INSERT INTO matchups (season, region, round, game_number,
                    high_seed_team_id, low_seed_team_id, matchup_name, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (season, region_name, game.get('round', 1), game['game_number'],
                  game['high_seed_team']['team_id'],
                  game['low_seed_team']['team_id'],
                  game['matchup_name'], timestamp))

    commit(db)
    close_db(db)
    print("✓ Bracket and matchups saved to database")


def generate_bracket(season=CURRENT_SEASON):
    print(f"\n{'='*60}")
    print(f"Generating Bracket from Bracket Matrix [{db_type()}]")
    print(f"{'='*60}\n")

    bracket_teams = scrape_bracket_matrix()
    if not bracket_teams:
        print("❌ No bracket data available")
        return None

    print("\nMatching teams to database...")
    matched, unmatched = match_bracket_teams(bracket_teams, season)

    print("\nAssigning regions...")
    regions = assign_regions(matched)
    for region, teams in regions.items():
        print(f"  {region}: {len(teams)} teams")

    print("\nCreating matchups...")
    matchups = create_matchups(regions)
    total = sum(len(g) for g in matchups.values())
    play_in = sum(1 for g in matchups.values() for m in g if m.get('round') == 0)
    print(f"✓ {play_in} play-in + {total - play_in} first-round = {total} total games")

    print("\nSaving to database...")
    save_to_database(regions, matchups, season)

    print(f"\n{'='*60}")
    print("Bracket generation complete!")
    print(f"{'='*60}\n")
    return {'regions': regions, 'matchups': matchups, 'unmatched': unmatched}


if __name__ == '__main__':
    generate_bracket(CURRENT_SEASON)