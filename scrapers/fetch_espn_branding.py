"""
Fetch ESPN team branding (logos, colors) and update teams table.

Run from project root:
    python scrapers/fetch_espn_branding.py
    python scrapers/fetch_espn_branding.py --details   # Show all matched teams
"""

import sys
from pathlib import Path
import requests
from difflib import SequenceMatcher
import argparse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from utils.db import get_db, close_db, execute, commit, db_type

ESPN_API_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams"
CURRENT_SEASON = 2026

MANUAL_MAPPINGS = {
    'Albany': 'ALB', 'American': 'AMER', 'Appalachian St.': 'APP',
    'Arkansas St.': 'ARST', 'Arkansas Pine Bluff': 'UAPB',
    'Army West Point': 'ARMY', 'Ball St.': 'BALL', 'Bethune Cookman': 'BCU',
    'Boise St.': 'BSU', 'Bowling Green': 'BGSU', 'BYU': 'BYU',
    'Cal Baptist': 'CBU', 'Cal Poly': 'CP', 'Cal St. Bakersfield': 'CSUB',
    'Cal St. Fullerton': 'CSUF', 'Cal St. Northridge': 'CSUN',
    'Central Arkansas': 'UCA', 'Central Connecticut': 'CCSU',
    'Central Michigan': 'CMU', 'Charleston Southern': 'CHSO',
    'Chicago St.': 'CSU', 'Coastal Carolina': 'CCU',
    'Col. of Charleston': 'CHSN', 'Colorado St.': 'CSU', 'CSUN': 'CSUN',
    'Eastern Illinois': 'EIU', 'Eastern Kentucky': 'EKU',
    'Eastern Michigan': 'EMU', 'Eastern Washington': 'EWU',
    'Fairleigh Dickinson': 'FDU', 'Florida Atlantic': 'FAU',
    'Florida Gulf Coast': 'FGCU', 'Florida International': 'FIU',
    'Florida St.': 'FSU', 'Fresno St.': 'FRES', 'Ga. Southern': 'GASO',
    'Georgia St.': 'GAST', 'Georgia Tech': 'GT', 'Grambling St.': 'GRAM',
    'Grand Canyon': 'GCU', 'Green Bay': 'GB', 'Illinois St.': 'ILS',
    'Illinois Chicago': 'UIC', 'Indiana St.': 'INST', 'Iowa St.': 'ISU',
    'Jackson St.': 'JKST', 'Jacksonville St.': 'JSU', 'Kansas St.': 'KSU',
    'Kennesaw St.': 'KENN', 'Kent St.': 'KENT', 'Lindenwood': 'LIN',
    'LIU': 'LIU', 'Long Beach St.': 'LBSU', 'Louisiana Lafayette': 'ULL',
    'Louisiana Monroe': 'ULM', 'Louisiana Tech': 'LT',
    'Loyola Chicago': 'LUC', 'Loyola Marymount': 'LMU', 'Loyola MD': 'LOY',
    'Maine': 'UME', 'Massachusetts': 'MASS', 'McNeese St.': 'MCNS',
    'Miami FL': 'MIA', 'Miami OH': 'M-OH', 'Michigan St.': 'MSU',
    'Middle Tennessee': 'MTSU', 'Mississippi': 'MISS',
    'Mississippi St.': 'MSST', 'Mississippi Valley St.': 'MVSU',
    'Missouri St.': 'MOST', 'Monmouth': 'MONM', 'Montana St.': 'MTST',
    'Morehead St.': 'MORE', 'Morgan St.': 'MORG',
    "Mount St. Mary's": 'MSMU', 'Murray St.': 'MUR',
    'New Mexico St.': 'NMSU', 'Nicholls St.': 'NICH',
    'Nebraska Omaha': 'UNO', 'Norfolk St.': 'NORF',
    'North Carolina A&T': 'NCAT', 'North Carolina Central': 'NCCU',
    'North Carolina St.': 'NCST', 'North Dakota St.': 'NDSU',
    'North Texas': 'UNT', 'Northeastern': 'NEU', 'Northern Arizona': 'NAU',
    'Northern Colorado': 'UNCO', 'Northern Illinois': 'NIU',
    'Northern Iowa': 'UNI', 'Northern Kentucky': 'NKU',
    'Northwestern St.': 'NWST', 'Notre Dame': 'ND', 'Ohio St.': 'OSU',
    'Oklahoma St.': 'OKST', 'Old Dominion': 'ODU', 'Oral Roberts': 'ORU',
    'Oregon St.': 'ORST', 'Penn St.': 'PSU', 'Pepperdine': 'PEPP',
    'Pittsburgh': 'PITT', 'Portland St.': 'PRST',
    'Prairie View A&M': 'PVAM', 'Presbyterian': 'PC', 'Queens': 'QUC',
    'Sacramento St.': 'SAC', 'Saint Francis PA': 'SFU',
    "Saint Joseph's": 'SJU', 'Saint Louis': 'SLU', "Saint Mary's": 'SMC',
    "Saint Peter's": 'SPU', 'Sam Houston St.': 'SHSU',
    'San Diego St.': 'SDSU', 'San Francisco': 'USF', 'San Jose St.': 'SJSU',
    'Santa Clara': 'SCU', 'Seattle': 'SEAT', 'Seton Hall': 'HALL',
    'SIU Edwardsville': 'SIUE', 'South Alabama': 'USA',
    'South Carolina St.': 'SCST', 'South Carolina Upstate': 'USC',
    'South Dakota St.': 'SDST', 'South Florida': 'USF',
    'Southeast Missouri St.': 'SEMO', 'Southeastern Louisiana': 'SELA',
    'Southern': 'SOU', 'Southern Illinois': 'SIU',
    'Southern Indiana': 'USI', 'Southern Miss': 'USM',
    'Southern Utah': 'SUU', 'St. Bonaventure': 'BONA',
    'St. Francis NY': 'SFB', "St. John's": 'SJU', 'St. Thomas': 'STMN',
    'Stephen F. Austin': 'SFA', 'Stony Brook': 'STON', 'TCU': 'TCU',
    'Tennessee St.': 'TNST', 'Tennessee Tech': 'TTU',
    'Texas A&M': 'TAMU', 'Texas A&M Commerce': 'TAMC',
    'Texas A&M Corpus Chris': 'AMCC', 'Texas Southern': 'TXSO',
    'Texas St.': 'TXST', 'Texas Tech': 'TTU', 'UT Arlington': 'UTA',
    'UT Martin': 'UTM', 'UT Rio Grande Valley': 'UTRGV',
    'UTEP': 'UTEP', 'UTSA': 'UTSA', 'UC Davis': 'UCD', 'UC Irvine': 'UCI',
    'UC Riverside': 'UCR', 'UC San Diego': 'UCSD',
    'UC Santa Barbara': 'UCSB', 'UCF': 'UCF', 'Connecticut': 'CONN',
    'UMass Lowell': 'UML', 'UMBC': 'UMBC', 'UMKC': 'UMKC',
    'UNC Asheville': 'UNCA', 'UNC Greensboro': 'UNCG',
    'UNC Wilmington': 'UNCW', 'USC': 'USC', 'Utah St.': 'USU',
    'VCU': 'VCU', 'VMI': 'VMI', 'Washington St.': 'WSU',
    'West Virginia': 'WVU', 'Western Carolina': 'WCU',
    'Western Illinois': 'WIU', 'Western Kentucky': 'WKU',
    'Western Michigan': 'WMU', 'Wichita St.': 'WICH',
    'Winthrop': 'WIN', 'Wofford': 'WOF', 'Wright St.': 'WRST',
    'Youngstown St.': 'YSU',
}

COLOR_OVERRIDES = {
    'San Diego':       {'primary': '#002147', 'secondary': '#2f99d4'},
    'Wright St.':      {'primary': '#005F3A', 'secondary': '#cba052'},
    'Lindenwood':      {'primary': '#101820', 'secondary': '#B5A36A'},
    'Queens':          {'primary': '#192C66', 'secondary': '#857040'},
    'Southern Indiana':{'primary': '#CF102D', 'secondary': '#002D5D'},
}


def add_branding_columns():
    """Add branding columns to teams table if they don't exist yet."""
    db = get_db()
    for col in ['primary_color', 'secondary_color', 'logo_url']:
        try:
            execute(db, f"ALTER TABLE teams ADD COLUMN {col} TEXT")
            print(f"Added {col} column")
        except Exception:
            pass  # Column already exists
    commit(db)
    close_db(db)


def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_name(name):
    normalized = name.lower()
    for old, new in [('state', 'st.'), ('saint', 'st.'), ('university', ''), ('college', '')]:
        normalized = normalized.replace(old, new)
    return ' '.join(normalized.split())


def fetch_espn_teams():
    print("Fetching teams from ESPN API...")
    try:
        response = requests.get(ESPN_API_URL, params={'limit': 1000})
        response.raise_for_status()
        data = response.json()

        espn_teams = {}
        for team in data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', []):
            td = team.get('team', {})
            abbr = td.get('abbreviation', '')
            espn_teams[abbr] = {
                'name': td.get('displayName', ''),
                'short_name': td.get('shortDisplayName', ''),
                'abbreviation': abbr,
                'normalized_name': normalize_name(td.get('displayName', '')),
                'primary_color': '#' + td.get('color', '000000'),
                'secondary_color': '#' + td.get('alternateColor', 'FFFFFF'),
                'logo': td.get('logos', [{}])[0].get('href', '') if td.get('logos') else ''
            }

        print(f"✓ Fetched {len(espn_teams)} teams from ESPN")
        return espn_teams

    except requests.exceptions.RequestException as e:
        print(f"Error fetching ESPN data: {e}")
        return {}


def match_teams(kenpom_teams, espn_teams_dict):
    espn_list = list(espn_teams_dict.values())
    matches = []
    unmatched = []

    for kp_team in kenpom_teams:
        kp_name = kp_team['name']
        best_match = None
        match_method = None

        if kp_name in MANUAL_MAPPINGS:
            abbr = MANUAL_MAPPINGS[kp_name]
            if abbr in espn_teams_dict:
                best_match = espn_teams_dict[abbr]
                match_method = 'manual'

        if not best_match:
            best_score = 0
            kp_normalized = normalize_name(kp_name)
            for espn_team in espn_list:
                score = max(
                    similarity(kp_name, espn_team['name']),
                    similarity(kp_name, espn_team['short_name']),
                    similarity(kp_normalized, espn_team['normalized_name']),
                )
                if score > best_score:
                    best_score = score
                    if score > 0.75:
                        best_match = espn_team
                        match_method = f'fuzzy ({score:.2f})'

        if best_match:
            matches.append({
                'kenpom_id': kp_team['team_id'],
                'kenpom_name': kp_name,
                'espn_name': best_match['name'],
                'primary_color': best_match['primary_color'],
                'secondary_color': best_match['secondary_color'],
                'logo_url': best_match['logo'],
                'method': match_method
            })
        else:
            unmatched.append({'kenpom_id': kp_team['team_id'], 'kenpom_name': kp_name})

    return matches, unmatched


def update_team_branding(matches):
    db = get_db()
    for match in matches:
        execute(db, '''
            UPDATE teams SET primary_color = ?, secondary_color = ?, logo_url = ?
            WHERE team_id = ?
        ''', (match['primary_color'], match['secondary_color'],
              match['logo_url'], match['kenpom_id']))
    commit(db)
    close_db(db)
    print(f"✓ Updated {len(matches)} teams with branding")


def apply_color_overrides(season=CURRENT_SEASON):
    db = get_db()
    count = 0
    for team_name, colors in COLOR_OVERRIDES.items():
        execute(db, '''
            UPDATE teams SET primary_color = ?, secondary_color = ?
            WHERE name = ? AND season = ?
        ''', (colors['primary'], colors['secondary'], team_name, season))
        count += 1
    commit(db)
    close_db(db)
    if count:
        print(f"✓ Applied {count} color overrides")


def sync_espn_branding(season=CURRENT_SEASON, show_details=False):
    print(f"\n{'='*60}")
    print(f"Syncing ESPN Team Branding [{db_type()}]")
    print(f"{'='*60}\n")

    add_branding_columns()

    db = get_db()
    kenpom_teams = [dict(t) for t in execute(db,
        'SELECT team_id, name FROM teams WHERE season = ?', (season,)
    ).fetchall()]
    close_db(db)

    print(f"Found {len(kenpom_teams)} KenPom teams for {season}")

    espn_teams = fetch_espn_teams()
    if not espn_teams:
        print("Failed to fetch ESPN teams")
        return

    print("\nMatching teams...")
    matches, unmatched = match_teams(kenpom_teams, espn_teams)

    manual = sum(1 for m in matches if m['method'] == 'manual')
    print(f"✓ Matched {len(matches)}/{len(kenpom_teams)} teams "
          f"({manual} manual, {len(matches)-manual} fuzzy)")

    if show_details:
        for m in matches[:10]:
            print(f"  ✓ {m['kenpom_name']} → {m['espn_name']} ({m['method']})")

    update_team_branding(matches)
    apply_color_overrides(season)

    unmatched_no_override = [t for t in unmatched if t['kenpom_name'] not in COLOR_OVERRIDES]
    if unmatched_no_override:
        print(f"\n⚠️  {len(unmatched_no_override)} teams unmatched:")
        for t in unmatched_no_override:
            print(f"  - {t['kenpom_name']}")
        print("\n💡 Add missing teams to MANUAL_MAPPINGS in fetch_espn_branding.py")

    print(f"\n{'='*60}")
    print("ESPN branding sync complete!")
    print(f"{'='*60}\n")
    return len(unmatched_no_override)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sync ESPN team branding')
    parser.add_argument('--details', action='store_true', help='Show matched team details')
    args = parser.parse_args()
    sync_espn_branding(show_details=args.details)