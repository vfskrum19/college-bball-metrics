"""
Manual bracket entry script for Selection Sunday.

Enter teams in the order they appear in each region (seed order):
1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15

For play-in games, enter both teams for that seed line.

Run from project root:
    python scrapers/enter_bracket.py
"""

import sys
import json
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

# Seed order as teams appear in the bracket left-to-right, top-to-bottom
SEED_ORDER = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]

REGIONS = ['East', 'West', 'South', 'Midwest']


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def load_kenpom_teams(season=CURRENT_SEASON):
    db = get_db()
    rows = execute(db, 'SELECT team_id, name FROM teams WHERE season = ?', (season,)).fetchall()
    close_db(db)
    return {row['name']: row['team_id'] for row in rows}


def fuzzy_match(name, kenpom_teams):
    """Find the best matching KenPom team name."""
    # Exact match first
    if name in kenpom_teams:
        return name, 1.0

    # Case-insensitive
    for kp_name in kenpom_teams:
        if kp_name.lower() == name.lower():
            return kp_name, 1.0

    # Common shorthand mappings
    mappings = {
        'uconn': 'Connecticut', 'connecticut': 'Connecticut',
        'nc state': 'N.C. State', 'ncstate': 'N.C. State',
        'ole miss': 'Mississippi',
        "st. john's": "St. John's", "saint john's": "St. John's",
        "saint mary's": "Saint Mary's", "st. mary's": "Saint Mary's",
        'pitt': 'Pittsburgh', 'pittsburgh': 'Pittsburgh',
        'lsu': 'LSU', 'byu': 'BYU', 'vcu': 'VCU', 'smu': 'SMU',
        'tcu': 'TCU', 'unlv': 'UNLV', 'usc': 'USC', 'ucf': 'UCF',
        'ucla': 'UCLA', 'uab': 'UAB', 'utep': 'UTEP',
        'umass': 'Massachusetts', 'liu': 'LIU',
        'mcneese': 'McNeese', 'mcneese state': 'McNeese',
        'ut martin': 'UT Martin', 'tennessee-martin': 'UT Martin',
        'miami': 'Miami FL', 'miami fl': 'Miami FL', 'miami oh': 'Miami OH',
        'southern': 'Southern', 'southern u': 'Southern',
        'ca baptist': 'California Baptist', 'cal baptist': 'California Baptist',
        'northern iowa': 'Northern Iowa',
        'north dakota state': 'North Dakota St.',
        'south florida': 'South Florida',
    }

    lower = name.lower().strip()
    if lower in mappings:
        mapped = mappings[lower]
        if mapped in kenpom_teams:
            return mapped, 0.99

    # Fuzzy match
    best_score = 0
    best_name = None
    for kp_name in kenpom_teams:
        score = similarity(name, kp_name)
        if score > best_score:
            best_score = score
            best_name = kp_name

    return best_name, best_score


def parse_team_input(raw_input, region, seed, kenpom_teams):
    """Parse and validate a team name input."""
    name = raw_input.strip()
    if not name:
        return None, None, "Empty input"

    matched_name, score = fuzzy_match(name, kenpom_teams)

    if score == 1.0:
        return matched_name, kenpom_teams[matched_name], None
    elif score >= 0.75:
        return matched_name, kenpom_teams[matched_name], f"fuzzy ({score:.0%})"
    else:
        return None, None, f"No match found (best: '{matched_name}' at {score:.0%})"


def enter_region(region_name, play_in_seeds, kenpom_teams):
    """Interactively enter teams for one region."""
    print(f"\n{'='*60}")
    print(f"  {region_name.upper()} REGION")
    print(f"{'='*60}")
    print(f"Enter 16 teams in bracket order (seed order: {SEED_ORDER})")
    print(f"Play-in seeds for this region: {play_in_seeds if play_in_seeds else 'None'}")
    print(f"For play-in seeds, enter both teams separated by a comma.")
    print(f"Type 'restart' to redo this region.\n")

    teams = []
    seed_idx = 0

    while seed_idx < len(SEED_ORDER):
        seed = SEED_ORDER[seed_idx]
        is_playin = seed in play_in_seeds

        if is_playin:
            prompt = f"  Seed {seed:2d} (play-in, enter 2 teams): "
        else:
            prompt = f"  Seed {seed:2d}: "

        raw = input(prompt).strip()

        if raw.lower() == 'restart':
            print(f"\nRestarting {region_name} region...\n")
            return enter_region(region_name, play_in_seeds, kenpom_teams)

        if is_playin:
            # Expect two teams separated by comma
            parts = [p.strip() for p in raw.split(',')]
            if len(parts) != 2:
                print(f"    ⚠ Play-in needs 2 teams separated by comma. Try again.")
                continue

            valid = True
            pair = []
            for part in parts:
                matched, team_id, err = parse_team_input(part, region_name, seed, kenpom_teams)
                if err and not matched:
                    print(f"    ✗ '{part}': {err}")
                    valid = False
                    break
                if err:
                    print(f"    ~ '{part}' → '{matched}' {err}")
                else:
                    print(f"    ✓ '{part}' → '{matched}'")
                pair.append({'name': matched, 'team_id': team_id, 'seed': seed, 'region': region_name})

            if not valid:
                continue

            teams.extend(pair)
        else:
            matched, team_id, err = parse_team_input(raw, region_name, seed, kenpom_teams)

            if err and not matched:
                print(f"    ✗ {err}. Try again.")
                continue
            elif err:
                print(f"    ~ '{raw}' → '{matched}' {err} — accept? (y/n): ", end='')
                confirm = input().strip().lower()
                if confirm != 'y':
                    continue
            else:
                print(f"    ✓ '{matched}'")

            teams.append({'name': matched, 'team_id': team_id, 'seed': seed, 'region': region_name})

        seed_idx += 1

    return teams


def confirm_region(region_name, teams):
    """Show region summary and ask for confirmation."""
    print(f"\n--- {region_name} Region Summary ---")
    for t in teams:
        print(f"  ({t['seed']:2d}) {t['name']}")

    print(f"\nConfirm {region_name} region? (y/n/restart): ", end='')
    resp = input().strip().lower()
    return resp


def save_bracket(all_teams, season=CURRENT_SEASON):
    """Save bracket to DB."""
    db = get_db()

    execute(db, 'DELETE FROM bracket WHERE season = ?', (season,))
    execute(db, 'DELETE FROM matchups WHERE season = ? AND round IN (0, 1)', (season,))

    timestamp = datetime.now().isoformat()
    pairings = [(1,16),(8,9),(5,12),(4,13),(6,11),(3,14),(7,10),(2,15)]

    # Insert bracket entries
    for team in all_teams:
        execute(db, '''
            INSERT INTO bracket (team_id, season, seed, region, source, generated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (team['team_id'], season, team['seed'], team['region'], 'Manual', timestamp))

    # Build matchups
    by_region_seed = {}
    for team in all_teams:
        key = (team['region'], team['seed'])
        by_region_seed.setdefault(key, []).append(team)

    game_num = 1
    regions = ['East', 'West', 'South', 'Midwest']

    for region in regions:
        for hi, lo in pairings:
            hi_teams = by_region_seed.get((region, hi), [])
            lo_teams = by_region_seed.get((region, lo), [])
            if hi_teams and lo_teams:
                # Play-in: if 2 teams on lo seed, create play-in game first
                if len(lo_teams) == 2:
                    execute(db, '''
                        INSERT INTO matchups (season, region, round, game_number,
                            high_seed_team_id, low_seed_team_id, matchup_name, generated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (season, region, 0, game_num,
                          lo_teams[0]['team_id'], lo_teams[1]['team_id'],
                          f"{lo} vs {lo} (Play-In)", timestamp))
                    game_num += 1

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
    print(f"\n✓ Saved {len(all_teams)} teams and {game_num-1} matchups to DB")


def main():
    print("\n" + "="*60)
    print("  NCAA BRACKET ENTRY — Selection Sunday 2026")
    print("="*60)
    print(f"\nDatabase: {db_type()}")

    kenpom_teams = load_kenpom_teams()
    print(f"Loaded {len(kenpom_teams)} KenPom teams\n")

    print("Play-in game configuration:")
    print("  Which regions have 16-seed play-ins? (e.g. 'South Midwest' or 'none'): ", end='')
    playin_16_input = input().strip().lower()
    playin_16_regions = []
    for r in REGIONS:
        if r.lower() in [x.strip() for x in playin_16_input.replace(',', ' ').split()]:
            playin_16_regions.append(r)

    print("  Which regions have 11-seed play-ins? (e.g. 'Midwest West' or 'none'): ", end='')
    playin_11_input = input().strip().lower()
    playin_11_regions = []
    for r in REGIONS:
        if r.lower() in playin_11_input:
            playin_11_regions.append(r)

    print(f"\n  16-seed play-ins: {playin_16_regions or 'None'}")
    print(f"  11-seed play-ins: {playin_11_regions or 'None'}")

    all_teams = []

    for region in REGIONS:
        play_in_seeds = []
        if region in playin_16_regions:
            play_in_seeds.append(16)
        if region in playin_11_regions:
            play_in_seeds.append(11)

        while True:
            teams = enter_region(region, play_in_seeds, kenpom_teams)
            resp = confirm_region(region, teams)
            if resp == 'y':
                all_teams.extend(teams)
                break
            elif resp == 'restart':
                continue
            else:
                print("Re-entering region...")

    # Final confirmation
    print(f"\n{'='*60}")
    print(f"FULL BRACKET SUMMARY — {len(all_teams)} teams")
    print(f"{'='*60}")
    for region in REGIONS:
        print(f"\n  {region}:")
        region_teams = [t for t in all_teams if t['region'] == region]
        for t in sorted(region_teams, key=lambda x: x['seed']):
            print(f"    ({t['seed']:2d}) {t['name']}")

    print(f"\nSave bracket to database? (y/n): ", end='')
    if input().strip().lower() == 'y':
        save_bracket(all_teams)
        print("\n✓ Bracket saved!")
        print("Next step: set BRACKET_FINALIZED=true in Railway environment variables")
        print("           to stop the cron from overwriting the real bracket.\n")
    else:
        print("\nBracket not saved. Run again when ready.\n")


if __name__ == '__main__':
    main()
