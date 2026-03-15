"""
Import real NCAA bracket from ESPN API.

Run AFTER Selection Sunday bracket is announced:
    python scrapers/import_espn_bracket.py --test     # See raw API response
    python scrapers/import_espn_bracket.py            # Import to DB

After successful import:
    Set BRACKET_FINALIZED=true in Railway environment variables.
    This stops cron.py from overwriting the real bracket daily.
"""

import sys
import json
import os
import requests
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from utils.db import get_db, close_db, execute, commit, db_type

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CURRENT_SEASON = 2026

# ESPN endpoints to try in order — bracket API shape changes year to year
ESPN_ENDPOINTS = [
    "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/tournament/bracket",
    "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/tournaments/22/seasons/2026/bracketology",
    "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/bracketology",
    "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?groups=100&limit=200",
    "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/tournaments/22/seasons/2026",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# Same name mappings as bracket matrix importer
TEAM_MAPPINGS = {
    'NC State': 'N.C. State', 'North Carolina State': 'N.C. State',
    'UConn': 'Connecticut', 'Connecticut': 'Connecticut',
    'Miami': 'Miami FL', 'Miami (FL)': 'Miami FL',
    'Ole Miss': 'Mississippi', 'Mississippi': 'Mississippi',
    "St. John's": "St. John's", "Saint John's": "St. John's",
    "Saint Mary's": "Saint Mary's", "St. Mary's": "Saint Mary's",
    'LSU': 'LSU', 'BYU': 'BYU', 'VCU': 'VCU', 'SMU': 'SMU',
    'TCU': 'TCU', 'UNLV': 'UNLV', 'Pitt': 'Pittsburgh',
    'UMass': 'Massachusetts', 'LIU': 'LIU',
    'McNeese State': 'McNeese', 'McNeese St.': 'McNeese',
    'Tennessee-Martin': 'UT Martin',
}


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_team_name(espn_name, kenpom_teams):
    """Match an ESPN team name to a KenPom team."""
    # Try exact mapping first
    mapped = TEAM_MAPPINGS.get(espn_name)
    if mapped and mapped in kenpom_teams:
        return kenpom_teams[mapped]

    # Try direct match
    if espn_name in kenpom_teams:
        return kenpom_teams[espn_name]

    # Try case-insensitive
    lower = {k.lower(): v for k, v in kenpom_teams.items()}
    if espn_name.lower() in lower:
        return lower[espn_name.lower()]

    # Fuzzy match
    best_score = 0
    best_team = None
    for name, team in kenpom_teams.items():
        score = similarity(espn_name, name)
        if score > best_score and score > 0.75:
            best_score = score
            best_team = team

    return best_team


def fetch_bracket_json():
    """Try each ESPN endpoint until one returns bracket data."""
    for url in ESPN_ENDPOINTS:
        print(f"  Trying: {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ Got response ({len(str(data))} chars)")
                return data, url
            else:
                print(f"  ✗ Status {response.status_code}")
        except Exception as e:
            print(f"  ✗ Error: {e}")

    return None, None


def test_mode():
    """Fetch and print raw API response so we can inspect the shape."""
    print("\n" + "="*60)
    print("ESPN BRACKET API — TEST MODE")
    print("="*60)
    print("\nTrying ESPN endpoints...\n")

    data, url = fetch_bracket_json()

    if not data:
        print("\n❌ No endpoint returned data.")
        print("\nThe bracket may not be live yet, or ESPN changed their API.")
        print("Try again after the bracket is announced (~6pm ET).")
        return

    print(f"\n✓ Working endpoint: {url}")
    print("\n--- RAW JSON STRUCTURE (first 3000 chars) ---\n")
    raw = json.dumps(data, indent=2)
    print(raw[:3000])
    if len(raw) > 3000:
        print(f"\n... ({len(raw) - 3000} more chars)")

    print("\n--- TOP-LEVEL KEYS ---")
    if isinstance(data, dict):
        for key in data.keys():
            val = data[key]
            if isinstance(val, list):
                print(f"  {key}: list of {len(val)}")
            elif isinstance(val, dict):
                print(f"  {key}: dict with keys {list(val.keys())[:5]}")
            else:
                print(f"  {key}: {val}")
    elif isinstance(data, list):
        print(f"  Root is a list of {len(data)} items")
        if data:
            print(f"  First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")

    print("\nPaste this output so we can write the parser.")


def import_bracket(season=CURRENT_SEASON):
    """Import the real NCAA bracket from ESPN into the DB."""
    print("\n" + "="*60)
    print(f"Importing ESPN Bracket [{db_type()}]")
    print("="*60 + "\n")

    # Fetch bracket data
    print("Fetching bracket from ESPN...")
    data, url = fetch_bracket_json()
    if not data:
        print("❌ Could not fetch bracket data. Run --test to diagnose.")
        return False

    # Load KenPom teams for matching
    db = get_db()
    rows = execute(db, 'SELECT team_id, name FROM teams WHERE season = ?', (season,)).fetchall()
    kenpom_teams = {row['name']: {'team_id': row['team_id'], 'name': row['name']} for row in rows}
    close_db(db)
    print(f"  Loaded {len(kenpom_teams)} KenPom teams for matching\n")

    # Parse bracket — this will need updating once we see the actual JSON shape
    # Run --test first to inspect the structure, then update parse_espn_bracket()
    teams = parse_espn_bracket(data)
    if not teams:
        print("❌ Could not parse bracket data.")
        print("Run --test to inspect the JSON shape, then update parse_espn_bracket().")
        return False

    # Match ESPN names to KenPom teams
    matched = []
    unmatched = []
    for t in teams:
        kp = match_team_name(t['name'], kenpom_teams)
        if kp:
            matched.append({
                'team_id': kp['team_id'],
                'team_name': kp['name'],
                'espn_name': t['name'],
                'seed': t['seed'],
                'region': t['region'],
            })
        else:
            unmatched.append(t)

    print(f"Matched: {len(matched)}/{len(teams)} teams")
    if unmatched:
        print(f"⚠ Unmatched ({len(unmatched)}):")
        for t in unmatched:
            print(f"  ({t['seed']}) {t['name']} — {t['region']}")

    if len(matched) < 60:
        print(f"\n❌ Only matched {len(matched)} teams — something is wrong.")
        print("Check unmatched teams above and add mappings to TEAM_MAPPINGS.")
        return False

    # Save to DB using same schema as import_bracket_matrix.py
    save_bracket(matched, season)
    print(f"\n✓ Bracket imported successfully from ESPN")
    print(f"  Remember to set BRACKET_FINALIZED=true in Railway env vars!")
    return True


def parse_espn_bracket(data):
    """
    Parse ESPN bracket JSON into a flat list of teams with seed/region.

    THIS FUNCTION NEEDS TO BE UPDATED after running --test to see
    the actual JSON shape. The structure below is a placeholder.

    Expected output format:
        [{'name': 'Duke', 'seed': 1, 'region': 'East'}, ...]
    """
    teams = []

    # TODO: update this parser once we see the real JSON shape
    # Common patterns to try:

    # Pattern 1: bracket.regions[].teams[]
    if 'bracket' in data:
        bracket = data['bracket']
        if 'regions' in bracket:
            for region in bracket['regions']:
                region_name = region.get('name', region.get('displayName', ''))
                for team in region.get('teams', []):
                    teams.append({
                        'name': team.get('name') or team.get('displayName', ''),
                        'seed': int(team.get('seed', 0)),
                        'region': region_name,
                    })

    # Pattern 2: regions[] at root
    if not teams and 'regions' in data:
        for region in data['regions']:
            region_name = region.get('name', region.get('displayName', ''))
            for team in region.get('teams', []):
                name = (team.get('team', {}).get('displayName') or
                        team.get('displayName') or
                        team.get('name', ''))
                seed = team.get('seed', 0)
                if name and seed:
                    teams.append({'name': name, 'seed': int(seed), 'region': region_name})

    # Pattern 3: games/matchups structure
    if not teams and ('games' in data or 'matchups' in data):
        games = data.get('games', data.get('matchups', []))
        seen = set()
        for game in games:
            if game.get('round', 1) != 1:
                continue
            region = game.get('region', game.get('venue', {}).get('region', ''))
            for side in ['home', 'away', 'top', 'bottom']:
                t = game.get(side, {})
                name = t.get('team', {}).get('displayName') or t.get('displayName', '')
                seed = t.get('seed', 0)
                if name and seed and name not in seen:
                    teams.append({'name': name, 'seed': int(seed), 'region': region})
                    seen.add(name)

    return teams


def save_bracket(matched_teams, season=CURRENT_SEASON):
    """Save bracket to DB — same schema as import_bracket_matrix.py."""
    db = get_db()

    execute(db, 'DELETE FROM bracket WHERE season = ?', (season,))
    execute(db, 'DELETE FROM matchups WHERE season = ? AND round IN (0, 1)', (season,))

    timestamp = datetime.now().isoformat()

    # Insert bracket entries
    for team in matched_teams:
        execute(db, '''
            INSERT INTO bracket (team_id, season, seed, region, source, generated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (team['team_id'], season, team['seed'], team['region'], 'ESPN', timestamp))

    # Build matchups from seeds
    pairings = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]
    by_region_seed = {}
    for team in matched_teams:
        key = (team['region'], team['seed'])
        by_region_seed.setdefault(key, []).append(team)

    regions = set(t['region'] for t in matched_teams)
    game_num = 1

    for region in sorted(regions):
        for hi, lo in pairings:
            hi_teams = by_region_seed.get((region, hi), [])
            lo_teams = by_region_seed.get((region, lo), [])
            if hi_teams and lo_teams:
                execute(db, '''
                    INSERT INTO matchups (season, region, round, game_number,
                        high_seed_team_id, low_seed_team_id, matchup_name, generated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (season, region, 1, game_num,
                      hi_teams[0]['team_id'], lo_teams[0]['team_id'],
                      f"{hi} vs {lo}", timestamp))
                game_num += 1

    commit(db)
    close_db(db)
    print(f"  Saved {len(matched_teams)} teams and {game_num-1} matchups to DB")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true',
                        help='Fetch and print raw ESPN API response without importing')
    args = parser.parse_args()

    if args.test:
        test_mode()
    else:
        success = import_bracket(CURRENT_SEASON)
        sys.exit(0 if success else 1)
