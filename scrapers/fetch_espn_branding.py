import os
from pathlib import Path
import requests
import sqlite3
import json
from difflib import SequenceMatcher

# Get project root (parent of this file's directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
ESPN_API_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams"

# Manual mappings for teams that don't match well
MANUAL_MAPPINGS = {
    # KenPom name: ESPN abbreviation or name to search for
    'Albany': 'ALB',
    'American': 'AMER',
    'Appalachian St.': 'APP',
    'Arkansas St.': 'ARST',
    'Arkansas Pine Bluff': 'UAPB',
    'Army West Point': 'ARMY',
    'Ball St.': 'BALL',
    'Bethune Cookman': 'BCU',
    'Boise St.': 'BSU',
    'Bowling Green': 'BGSU',
    'BYU': 'BYU',
    'Cal Baptist': 'CBU',
    'Cal Poly': 'CP',
    'Cal St. Bakersfield': 'CSUB',
    'Cal St. Fullerton': 'CSUF',
    'Cal St. Northridge': 'CSUN',
    'Central Arkansas': 'UCA',
    'Central Connecticut': 'CCSU',
    'Central Michigan': 'CMU',
    'Charleston Southern': 'CHSO',
    'Chicago St.': 'CSU',
    'Coastal Carolina': 'CCU',
    'Col. of Charleston': 'CHSN',
    'Colorado St.': 'CSU',
    'CSUN': 'CSUN',
    'Eastern Illinois': 'EIU',
    'Eastern Kentucky': 'EKU',
    'Eastern Michigan': 'EMU',
    'Eastern Washington': 'EWU',
    'Fairleigh Dickinson': 'FDU',
    'Florida Atlantic': 'FAU',
    'Florida Gulf Coast': 'FGCU',
    'Florida International': 'FIU',
    'Florida St.': 'FSU',
    'Fresno St.': 'FRES',
    'Ga. Southern': 'GASO',
    'Georgia St.': 'GAST',
    'Georgia Tech': 'GT',
    'Grambling St.': 'GRAM',
    'Grand Canyon': 'GCU',
    'Green Bay': 'GB',
    'Illinois St.': 'ILS',
    'Illinois Chicago': 'UIC',
    'Indiana St.': 'INST',
    'Iowa St.': 'ISU',
    'Jackson St.': 'JKST',
    'Jacksonville St.': 'JSU',
    'Kansas St.': 'KSU',
    'Kennesaw St.': 'KENN',
    'Kent St.': 'KENT',
    'Lindenwood': 'LIN',
    'LIU': 'LIU',
    'Long Beach St.': 'LBSU',
    'Long Island University': 'LIU',
    'Louisiana Lafayette': 'ULL',
    'Louisiana Monroe': 'ULM',
    'Louisiana Tech': 'LT',
    'Loyola Chicago': 'LUC',
    'Loyola Marymount': 'LMU',
    'Loyola MD': 'LOY',
    'Maine': 'UME',
    'Massachusetts': 'MASS',
    'McNeese St.': 'MCNS',
    'Miami FL': 'MIA',
    'Miami OH': 'M-OH',
    'Michigan St.': 'MSU',
    'Middle Tennessee': 'MTSU',
    'Mississippi': 'MISS',
    'Mississippi St.': 'MSST',
    'Mississippi Valley St.': 'MVSU',
    'Missouri St.': 'MOST',
    'Monmouth': 'MONM',
    'Montana St.': 'MTST',
    'Morehead St.': 'MORE',
    'Morgan St.': 'MORG',
    'Mount St. Mary\'s': 'MSMU',
    'Murray St.': 'MUR',
    'New Mexico St.': 'NMSU',
    'Nicholls St.': 'NICH',
    'Nebraska Omaha': 'UNO',
    'Norfolk St.': 'NORF',
    'North Carolina A&T': 'NCAT',
    'North Carolina Central': 'NCCU',
    'North Carolina St.': 'NCST',
    'North Dakota St.': 'NDSU',
    'North Texas': 'UNT',
    'Northeastern': 'NEU',
    'Northern Arizona': 'NAU',
    'Northern Colorado': 'UNCO',
    'Northern Illinois': 'NIU',
    'Northern Iowa': 'UNI',
    'Northern Kentucky': 'NKU',
    'Northwestern St.': 'NWST',
    'Notre Dame': 'ND',
    'Ohio St.': 'OSU',
    'Oklahoma St.': 'OKST',
    'Old Dominion': 'ODU',
    'Oral Roberts': 'ORU',
    'Oregon St.': 'ORST',
    'Penn St.': 'PSU',
    'Pepperdine': 'PEPP',
    'Pittsburgh': 'PITT',
    'Portland St.': 'PRST',
    'Prairie View A&M': 'PVAM',
    'Presbyterian': 'PC',
    'Queens': 'QUC',
    'Sacramento St.': 'SAC',
    'Saint Francis PA': 'SFU',
    'Saint Joseph\'s': 'SJU',
    'Saint Louis': 'SLU',
    'Saint Mary\'s': 'SMC',
    'Saint Peter\'s': 'SPU',
    'Sam Houston St.': 'SHSU',
    'San Diego St.': 'SDSU',
    'San Francisco': 'USF',
    'San Jose St.': 'SJSU',
    'Santa Clara': 'SCU',
    'Seattle': 'SEAT',
    'Seton Hall': 'HALL',
    'SIU Edwardsville': 'SIUE',
    'South Alabama': 'USA',
    'South Carolina St.': 'SCST',
    'South Carolina Upstate': 'USC',
    'South Dakota St.': 'SDST',
    'South Florida': 'USF',
    'Southeast Missouri St.': 'SEMO',
    'Southeastern Louisiana': 'SELA',
    'Southern': 'SOU',
    'Southern Illinois': 'SIU',
    'Southern Indiana': 'USI',
    'Southern Miss': 'USM',
    'Southern Utah': 'SUU',
    'St. Bonaventure': 'BONA',
    'St. Francis NY': 'SFB',
    'St. John\'s': 'SJU',
    'St. Thomas': 'STMN',
    'Stephen F. Austin': 'SFA',
    'Stony Brook': 'STON',
    'TCU': 'TCU',
    'Tennessee St.': 'TNST',
    'Tennessee Tech': 'TTU',
    'Texas A&M': 'TAMU',
    'Texas A&M Commerce': 'TAMC',
    'Texas A&M Corpus Chris': 'AMCC',
    'Texas Southern': 'TXSO',
    'Texas St.': 'TXST',
    'Texas Tech': 'TTU',
    'UT Arlington': 'UTA',
    'UT Martin': 'UTM',
    'UT Rio Grande Valley': 'UTRGV',
    'UTEP': 'UTEP',
    'UTSA': 'UTSA',
    'UC Davis': 'UCD',
    'UC Irvine': 'UCI',
    'UC Riverside': 'UCR',
    'UC San Diego': 'UCSD',
    'UC Santa Barbara': 'UCSB',
    'UCF': 'UCF',
    'Connecticut': 'CONN',
    'UMass Lowell': 'UML',
    'UMBC': 'UMBC',
    'UMKC': 'UMKC',
    'UNC Asheville': 'UNCA',
    'UNC Greensboro': 'UNCG',
    'UNC Wilmington': 'UNCW',
    'USC': 'USC',
    'UT San Antonio': 'UTSA',
    'Utah St.': 'USU',
    'Utah Tech': 'UTEP',
    'VCU': 'VCU',
    'VMI': 'VMI',
    'Washington St.': 'WSU',
    'West Virginia': 'WVU',
    'Western Carolina': 'WCU',
    'Western Illinois': 'WIU',
    'Western Kentucky': 'WKU',
    'Western Michigan': 'WMU',
    'Wichita St.': 'WICH',
    'Winthrop': 'WIN',
    'Wofford': 'WOF',
    'Wright St.': 'WRST',
    'Youngstown St.': 'YSU',
}

# Manual color overrides for teams with incorrect/missing ESPN data
# Format: 'KenPom Name': {'primary': '#HEX', 'secondary': '#HEX'}
COLOR_OVERRIDES = {
    # Teams with duplicate colors in ESPN API
    'San Diego': {'primary': '#002147', 'secondary': '#2f99d4'},       # Navy / Light Blue
    'Wright St.': {'primary': '#005F3A', 'secondary': '#cba052'},      # Hunter Green / Gold
    
    # Teams not in ESPN API (new D1 programs)
    'Lindenwood': {'primary': '#101820', 'secondary': '#B5A36A'},      # Black / Gold
    'Queens': {'primary': '#192C66', 'secondary': '#857040'},          # Navy Blue / Vegas Gold
    'Southern Indiana': {'primary': '#CF102D', 'secondary': '#002D5D'}, # Red / Navy
}

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def add_branding_columns():
    """Add columns for team branding if they don't exist"""
    db = get_db()
    cursor = db.cursor()
    
    # Check if columns exist, add if not
    try:
        cursor.execute("ALTER TABLE teams ADD COLUMN primary_color TEXT")
        print("Added primary_color column")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE teams ADD COLUMN secondary_color TEXT")
        print("Added secondary_color column")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE teams ADD COLUMN logo_url TEXT")
        print("Added logo_url column")
    except sqlite3.OperationalError:
        pass
    
    db.commit()
    db.close()

def similarity(a, b):
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_name(name):
    """Normalize team name for better matching"""
    # Common replacements
    replacements = {
        'state': 'st.',
        'saint': 'st.',
        'university': '',
        'college': '',
        ' the ': ' ',
    }
    
    normalized = name.lower()
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    # Remove extra spaces
    normalized = ' '.join(normalized.split())
    return normalized

def fetch_espn_teams():
    """Fetch team data from ESPN API"""
    print("Fetching teams from ESPN API...")
    
    try:
        response = requests.get(ESPN_API_URL, params={'limit': 1000})
        response.raise_for_status()
        data = response.json()
        
        espn_teams = {}  # Use dict with abbreviation as key for easy lookup
        for team in data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', []):
            team_data = team.get('team', {})
            
            abbr = team_data.get('abbreviation', '')
            espn_teams[abbr] = {
                'name': team_data.get('displayName', ''),
                'short_name': team_data.get('shortDisplayName', ''),
                'abbreviation': abbr,
                'normalized_name': normalize_name(team_data.get('displayName', '')),
                'primary_color': '#' + team_data.get('color', '000000'),
                'secondary_color': '#' + team_data.get('alternateColor', 'FFFFFF'),
                'logo': team_data.get('logos', [{}])[0].get('href', '') if team_data.get('logos') else ''
            }
        
        print(f"✓ Fetched {len(espn_teams)} teams from ESPN")
        return espn_teams
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ESPN data: {e}")
        return {}

def match_teams(kenpom_teams, espn_teams_dict):
    """Match KenPom teams with ESPN teams using manual mappings + fuzzy matching"""
    matches = []
    unmatched = []
    
    # Convert dict to list for fuzzy matching
    espn_teams_list = list(espn_teams_dict.values())
    
    for kp_team in kenpom_teams:
        kp_name = kp_team['name']
        best_match = None
        match_method = None
        
        # Try manual mapping first
        if kp_name in MANUAL_MAPPINGS:
            abbr = MANUAL_MAPPINGS[kp_name]
            if abbr in espn_teams_dict:
                best_match = espn_teams_dict[abbr]
                match_method = 'manual'
        
        # If no manual match, try fuzzy matching
        if not best_match:
            best_score = 0
            kp_normalized = normalize_name(kp_name)
            
            for espn_team in espn_teams_list:
                # Try matching against different ESPN name fields
                scores = [
                    similarity(kp_name, espn_team['name']),
                    similarity(kp_name, espn_team['short_name']),
                    similarity(kp_normalized, espn_team['normalized_name']),
                ]
                
                max_score = max(scores)
                
                if max_score > best_score:
                    best_score = max_score
                    if max_score > 0.75:  # Lowered threshold
                        best_match = espn_team
                        match_method = f'fuzzy ({max_score:.2f})'
        
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
            unmatched.append({
                'kenpom_id': kp_team['team_id'],
                'kenpom_name': kp_name,
            })
    
    return matches, unmatched

def update_team_branding(matches):
    """Update KenPom teams with ESPN branding"""
    db = get_db()
    cursor = db.cursor()
    
    for match in matches:
        cursor.execute('''
            UPDATE teams 
            SET primary_color = ?, secondary_color = ?, logo_url = ?
            WHERE team_id = ?
        ''', (
            match['primary_color'],
            match['secondary_color'],
            match['logo_url'],
            match['kenpom_id']
        ))
    
    db.commit()
    db.close()
    print(f"✓ Updated {len(matches)} teams with branding")

def apply_color_overrides(season=2026):
    """Apply manual color overrides for teams with bad/missing ESPN data"""
    db = get_db()
    cursor = db.cursor()
    
    override_count = 0
    for team_name, colors in COLOR_OVERRIDES.items():
        cursor.execute('''
            UPDATE teams 
            SET primary_color = ?, secondary_color = ?
            WHERE name = ? AND season = ?
        ''', (
            colors['primary'],
            colors['secondary'],
            team_name,
            season
        ))
        
        if cursor.rowcount > 0:
            override_count += 1
    
    db.commit()
    db.close()
    
    if override_count > 0:
        print(f"✓ Applied {override_count} color overrides")
    
    return override_count

def sync_espn_branding(season=2026, show_details=False):
    """Main function to sync ESPN branding with KenPom teams"""
    print(f"\n{'='*60}")
    print(f"Syncing ESPN Team Branding")
    print(f"{'='*60}\n")
    
    # Step 1: Add columns if needed
    add_branding_columns()
    
    # Step 2: Get KenPom teams from database
    db = get_db()
    kenpom_teams = db.execute(
        'SELECT team_id, name FROM teams WHERE season = ?',
        (season,)
    ).fetchall()
    kenpom_teams = [dict(team) for team in kenpom_teams]
    db.close()
    
    print(f"Found {len(kenpom_teams)} KenPom teams for season {season}")
    
    # Step 3: Fetch ESPN teams
    espn_teams = fetch_espn_teams()
    
    if not espn_teams:
        print("Failed to fetch ESPN teams")
        return
    
    # Step 4: Match teams
    print("\nMatching teams...")
    matches, unmatched = match_teams(kenpom_teams, espn_teams)
    
    manual_count = sum(1 for m in matches if m['method'] == 'manual')
    fuzzy_count = len(matches) - manual_count
    
    print(f"✓ Matched {len(matches)} teams ({len(matches)/len(kenpom_teams)*100:.1f}%)")
    print(f"  - {manual_count} via manual mapping")
    print(f"  - {fuzzy_count} via fuzzy matching")
    
    # Show match details if requested
    if show_details:
        print("\nMatched teams:")
        for match in matches[:10]:
            print(f"  ✓ {match['kenpom_name']} → {match['espn_name']} ({match['method']})")
        if len(matches) > 10:
            print(f"  ... and {len(matches) - 10} more")
    
    # Step 5: Update database
    update_team_branding(matches)
    
    # Step 6: Apply color overrides (fixes bad ESPN data + fills in missing)
    print("\nApplying color overrides...")
    apply_color_overrides(season)
    
    # Step 7: Report unmatched teams (excluding those with overrides)
    unmatched_without_overrides = [t for t in unmatched if t['kenpom_name'] not in COLOR_OVERRIDES]
    
    if unmatched_without_overrides:
        print(f"\n⚠️  {len(unmatched_without_overrides)} teams not matched:")
        for team in unmatched_without_overrides:
            print(f"  - {team['kenpom_name']} (ID: {team['kenpom_id']})")
        
        print("\n💡 To manually add branding for these teams:")
        print("   1. Find the team on ESPN's website")
        print("   2. Add to MANUAL_MAPPINGS in fetch_espn_branding.py")
        print("   3. Run this script again")
    
    print(f"\n{'='*60}")
    print(f"ESPN branding sync complete!")
    print(f"{'='*60}\n")
    
    return len(unmatched_without_overrides)

if __name__ == '__main__':
    import sys
    show_details = '--details' in sys.argv
    unmatched_count = sync_espn_branding(show_details=show_details)
    
    if unmatched_count and unmatched_count > 0:
        print(f"\nRun with --details flag to see all matched teams")