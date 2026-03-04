"""
Import NCAA resume data (NET rank, quad records) from CSV file.

The NCAA_Statistics.csv must be downloaded manually from NCAA.com
and placed in the project root before running.

Run from project root:
    python scrapers/import_ncaa_data.py NCAA_Statistics.csv
    python scrapers/import_ncaa_data.py NCAA_Statistics.csv 2026
"""

import sys
import csv
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from utils.db import get_db, close_db, execute, commit, db_type

CURRENT_SEASON = 2026

NCAA_TO_KENPOM_MAPPINGS = {
    'UConn': 'Connecticut', 'Southern California': 'USC',
    'UNI': 'Northern Iowa', 'Ole Miss': 'Mississippi',
    'SFA': 'Stephen F. Austin', 'UNCW': 'UNC Wilmington',
    'LMU (CA)': 'Loyola Marymount', 'ETSU': 'East Tennessee St.',
    'Western Ky.': 'Western Kentucky', 'UT Martin': 'Tennessee Martin',
    'UMass': 'Massachusetts', 'SIUE': 'SIU Edwardsville',
    'UIC': 'Illinois Chicago', 'UMBC': 'Maryland Baltimore County',
    'UTRGV': 'UT Rio Grande Valley', 'UTA': 'UT Arlington',
    'UTSA': 'UT San Antonio', 'FIU': 'Florida International',
    'FAU': 'Florida Atlantic', 'FGCU': 'Florida Gulf Coast',
    'LIU': 'Long Island University', 'NJIT': 'New Jersey Tech',
    'UMKC': 'Missouri Kansas City', 'UAB': 'Alabama Birmingham',
    'UCF': 'Central Florida', 'VCU': 'Virginia Commonwealth',
    'VMI': 'Virginia Military Institute', 'UNLV': 'Nevada Las Vegas',
    'USC Upstate': 'South Carolina Upstate',
    'Green Bay': 'Wisconsin Green Bay',
    'Albany (NY)': 'Albany', 'UNC Asheville': 'North Carolina Asheville',
    'UNC Greensboro': 'North Carolina Greensboro',
    'UNCG': 'North Carolina Greensboro',
    'Miami (FL)': 'Miami FL', 'Miami (OH)': 'Miami OH',
    "Saint Joseph's": "St. Joseph's", 'Saint Louis': 'St. Louis',
    "Saint Mary's": "St. Mary's", "Saint Peter's": "St. Peter's",
    'Saint Bonaventure': 'St. Bonaventure',
    "St. John's (NY)": "St. John's",
    'Col. of Charleston': 'Charleston', 'Cal Baptist': 'Cal Baptist',
    'California Baptist': 'Cal Baptist', 'Omaha': 'Nebraska Omaha',
    'Seattle U': 'Seattle University', 'UIW': 'Incarnate Word',
    'A&M-Corpus Christi': 'Texas A&M Corpus Chris',
    'Southeast Mo. St.': 'Southeast Missouri',
    'App State': 'Appalachian St.',
    'Central Conn. St.': 'Central Connecticut',
    'Queens (NC)': 'Queens', 'Eastern Ky.': 'Eastern Kentucky',
    'West Ga.': 'West Georgia', 'Army West Point': 'Army',
    'NIU': 'Northern Illinois', 'UMES': 'Maryland Eastern Shore',
    'Alcorn': 'Alcorn St.', 'N.C. Central': 'North Carolina Central',
    'FDU': 'Fairleigh Dickinson', 'ULM': 'Louisiana Monroe',
}


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_name(name):
    name = name.lower().strip()
    for old, new in [('state', 'st.'), ('saint', 'st. '), ('university', ''), ('college', '')]:
        name = name.replace(old, new)
    return ' '.join(name.split())


def parse_quad_record(record_str):
    if not record_str or str(record_str).strip() in ('', '-'):
        return 0, 0
    try:
        parts = str(record_str).strip().split('-')
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return 0, 0


def add_resume_table():
    db = get_db()
    execute(db, '''
        CREATE TABLE IF NOT EXISTS resume_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            net_rank INTEGER,
            quad1_wins INTEGER, quad1_losses INTEGER,
            quad2_wins INTEGER, quad2_losses INTEGER,
            quad3_wins INTEGER, quad3_losses INTEGER,
            quad4_wins INTEGER, quad4_losses INTEGER,
            sor_rank INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    commit(db)
    close_db(db)
    print("✓ Resume metrics table ready")


def load_ncaa_csv(filepath):
    print(f"Loading NCAA data from {filepath}...")
    resume_data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                q1w, q1l = parse_quad_record(row.get('Q1'))
                q2w, q2l = parse_quad_record(row.get('Q2'))
                q3w, q3l = parse_quad_record(row.get('Q3'))
                q4w, q4l = parse_quad_record(row.get('Q4'))
                net = row.get('NET Rank')
                resume_data.append({
                    'team_name': row['Team'],
                    'net_rank': int(net) if net else None,
                    'quad1_wins': q1w, 'quad1_losses': q1l,
                    'quad2_wins': q2w, 'quad2_losses': q2l,
                    'quad3_wins': q3w, 'quad3_losses': q3l,
                    'quad4_wins': q4w, 'quad4_losses': q4l,
                    'sor_rank': None,
                })
        print(f"✓ Loaded {len(resume_data)} teams from CSV")
        return resume_data
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return []


def match_teams_to_database(resume_data, season=CURRENT_SEASON):
    db = get_db()
    kenpom_teams = [{'team_id': t['team_id'], 'name': t['name']}
                    for t in execute(db, 'SELECT team_id, name FROM teams WHERE season = ?',
                                     (season,)).fetchall()]
    close_db(db)

    kenpom_by_name = {t['name']: t for t in kenpom_teams}
    matches = []
    unmatched = []

    for team in resume_data:
        ncaa_name = team['team_name']
        kenpom_name = NCAA_TO_KENPOM_MAPPINGS.get(ncaa_name)

        kp_team = None
        if kenpom_name:
            kp_team = kenpom_by_name.get(kenpom_name)

        if not kp_team:
            best_score = 0
            ncaa_norm = normalize_name(ncaa_name)
            for kt in kenpom_teams:
                score = max(similarity(ncaa_name, kt['name']),
                            similarity(ncaa_norm, normalize_name(kt['name'])))
                if score > best_score:
                    best_score = score
                    if score > 0.75:
                        kp_team = kt

        if kp_team:
            matches.append({**team, 'team_id': kp_team['team_id'],
                             'kenpom_name': kp_team['name']})
        else:
            unmatched.append({'ncaa_name': ncaa_name})

    print(f"✓ Matched {len(matches)}/{len(resume_data)} teams")
    if unmatched:
        print(f"⚠️  {len(unmatched)} unmatched:")
        for t in unmatched[:10]:
            print(f"  - {t['ncaa_name']}")
    return matches, unmatched


def update_resume_metrics(matches, season=CURRENT_SEASON):
    db = get_db()
    execute(db, 'DELETE FROM resume_metrics WHERE season = ?', (season,))
    for m in matches:
        execute(db, '''
            INSERT INTO resume_metrics (
                team_id, season, net_rank,
                quad1_wins, quad1_losses, quad2_wins, quad2_losses,
                quad3_wins, quad3_losses, quad4_wins, quad4_losses, sor_rank
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (m['team_id'], season, m['net_rank'],
              m['quad1_wins'], m['quad1_losses'],
              m['quad2_wins'], m['quad2_losses'],
              m['quad3_wins'], m['quad3_losses'],
              m['quad4_wins'], m['quad4_losses'],
              m['sor_rank']))
    commit(db)
    close_db(db)
    print(f"✓ Updated {len(matches)} teams with resume data")


def import_ncaa_data(csv_path, season=CURRENT_SEASON):
    print(f"\n{'='*60}")
    print(f"Importing NCAA Resume Data [{db_type()}]")
    print(f"{'='*60}\n")

    add_resume_table()
    resume_data = load_ncaa_csv(csv_path)
    if not resume_data:
        print("❌ No data loaded, aborting")
        return

    matches, unmatched = match_teams_to_database(resume_data, season)
    update_resume_metrics(matches, season)

    print(f"\n{'='*60}")
    print(f"Import complete — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    return len(unmatched)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scrapers/import_ncaa_data.py NCAA_Statistics.csv [season]")
        sys.exit(1)

    csv_path = sys.argv[1]
    season = int(sys.argv[2]) if len(sys.argv) > 2 else CURRENT_SEASON
    import_ncaa_data(csv_path, season)