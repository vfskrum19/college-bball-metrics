import csv
import sqlite3
from datetime import datetime
from difflib import SequenceMatcher
import sys

DATABASE = 'kenpom.db'
CURRENT_SEASON = 2026

# Manual mappings for NCAA names that don't match KenPom
NCAA_TO_KENPOM_MAPPINGS = {
    'UConn': 'Connecticut',
    'Southern California': 'USC',
    'UNI': 'Northern Iowa',
    'Ole Miss': 'Mississippi',
    'SFA': 'Stephen F. Austin',
    'UNCW': 'UNC Wilmington',
    'LMU (CA)': 'Loyola Marymount',
    'ETSU': 'East Tennessee St.',
    'Western Ky.': 'Western Kentucky',
    'UT Martin': 'Tennessee Martin',
    'UMass': 'Massachusetts',
    'SIUE': 'SIU Edwardsville',
    'UIC': 'Illinois Chicago',
    'UMBC': 'Maryland Baltimore County',
    'UTRGV': 'UT Rio Grande Valley',
    'UTA': 'UT Arlington',
    'UTSA': 'UT San Antonio',
    'FIU': 'Florida International',
    'FAU': 'Florida Atlantic',
    'FGCU': 'Florida Gulf Coast',
    'LIU': 'Long Island University',
    'NJIT': 'New Jersey Tech',
    'UMKC': 'Missouri Kansas City',
    'UAB': 'Alabama Birmingham',
    'UCF': 'Central Florida',
    'VCU': 'Virginia Commonwealth',
    'VMI': 'Virginia Military Institute',
    'UNLV': 'Nevada Las Vegas',
    'USC Upstate': 'South Carolina Upstate',
    'Green Bay': 'Wisconsin Green Bay',
    'Albany (NY)': 'Albany',
    'UNC Asheville': 'North Carolina Asheville',
    'UNC Greensboro': 'North Carolina Greensboro',
    'UNCG': 'North Carolina Greensboro',
    'Miami (FL)': 'Miami FL',
    'Miami (OH)': 'Miami OH',
    'Saint Joseph\'s': 'St. Joseph\'s',
    'Saint Louis': 'St. Louis',
    'Saint Mary\'s': 'St. Mary\'s',
    'Saint Peter\'s': 'St. Peter\'s',
    'Saint Bonaventure': 'St. Bonaventure',
    'St. John\'s (NY)': 'St. John\'s',
    'Loyola Chicago': 'Loyola Chicago',
    'Loyola Marymount': 'Loyola Marymount',
    'Loyola Maryland': 'Loyola MD',
    'Texas A&M': 'Texas A&M',
    'Col. of Charleston': 'Charleston',
    'Cal Baptist': 'Cal Baptist',
    'California Baptist': 'Cal Baptist',
    'Omaha': 'Nebraska Omaha',
    'Monmouth': 'Monmouth',
    'Seattle U': 'Seattle University',
    'UIW': 'Incarnate Word',
    'A&M-Corpus Christi': 'Texas A&M Corpus Chris',
    'Southeast Mo. St.': 'Southeast Missouri',
    'App State': 'Appalachian St.',
    'Central Conn. St.': 'Central Connecticut',
    'Queens (NC)': 'Queens',
    'Eastern Ky.': 'Eastern Kentucky',
    'West Ga.': 'West Georgia',
    'Army West Point': 'Army',
    'NIU': 'Northern Illinois',
    'UMES': 'Maryland Eastern Shore',
    'Alcorn': 'Alcorn St.',
    'N.C. Central': 'North Carolina Central',
    'FDU' : 'Fairleigh Dickinson',
    'ULM': 'Louisiana Monroe'
}

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def add_resume_table():
    """Create resume_metrics table if it doesn't exist"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resume_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            net_rank INTEGER,
            quad1_wins INTEGER,
            quad1_losses INTEGER,
            quad2_wins INTEGER,
            quad2_losses INTEGER,
            quad3_wins INTEGER,
            quad3_losses INTEGER,
            quad4_wins INTEGER,
            quad4_losses INTEGER,
            sor_rank INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    db.commit()
    db.close()
    print("✓ Resume metrics table ready")

def similarity(a, b):
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_name(name):
    """Normalize team names for better matching"""
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

def parse_quad_record(record_str):
    """Parse quad record string like '8-3' into wins and losses"""
    if not record_str or record_str == '-' or record_str == '':
        return 0, 0
    
    try:
        parts = str(record_str).strip().split('-')
        wins = int(parts[0])
        losses = int(parts[1]) if len(parts) > 1 else 0
        return wins, losses
    except:
        return 0, 0

def load_ncaa_csv(filepath):
    """Load and parse NCAA statistics CSV"""
    print(f"Loading NCAA data from {filepath}...")
    
    try:
        resume_data = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                team_name = row['Team']
                net_rank = row['NET Rank']
                
                # Parse quad records
                q1_w, q1_l = parse_quad_record(row['Q1'])
                q2_w, q2_l = parse_quad_record(row['Q2'])
                q3_w, q3_l = parse_quad_record(row['Q3'])
                q4_w, q4_l = parse_quad_record(row['Q4'])
                
                resume_data.append({
                    'team_name': team_name,
                    'net_rank': int(net_rank) if net_rank else None,
                    'quad1_wins': q1_w,
                    'quad1_losses': q1_l,
                    'quad2_wins': q2_w,
                    'quad2_losses': q2_l,
                    'quad3_wins': q3_w,
                    'quad3_losses': q3_l,
                    'quad4_wins': q4_w,
                    'quad4_losses': q4_l,
                    'sor_rank': None  # Not in NCAA CSV
                })
        
        print(f"✓ Loaded {len(resume_data)} teams from CSV")
        print(f"✓ Parsed resume data for {len(resume_data)} teams")
        return resume_data
        
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        import traceback
        traceback.print_exc()
        return []

def match_teams_to_database(resume_data, season=CURRENT_SEASON):
    """Match NCAA team names to KenPom database team_ids"""
    db = get_db()
    
    kenpom_teams = db.execute(
        'SELECT team_id, name FROM teams WHERE season = ?',
        (season,)
    ).fetchall()
    
    kenpom_teams_list = [{'team_id': t['team_id'], 'name': t['name']} for t in kenpom_teams]
    
    matches = []
    unmatched = []
    
    for resume_team in resume_data:
        ncaa_name = resume_team['team_name']
        
        # Step 1: Check manual mappings first
        kenpom_name = NCAA_TO_KENPOM_MAPPINGS.get(ncaa_name)
        
        if kenpom_name:
            # Find exact match for mapped name
            kp_team = next((t for t in kenpom_teams_list if t['name'] == kenpom_name), None)
            if kp_team:
                matches.append({
                    'team_id': kp_team['team_id'],
                    'kenpom_name': kp_team['name'],
                    'ncaa_name': ncaa_name,
                    'net_rank': resume_team['net_rank'],
                    'quad1_wins': resume_team['quad1_wins'],
                    'quad1_losses': resume_team['quad1_losses'],
                    'quad2_wins': resume_team['quad2_wins'],
                    'quad2_losses': resume_team['quad2_losses'],
                    'quad3_wins': resume_team['quad3_wins'],
                    'quad3_losses': resume_team['quad3_losses'],
                    'quad4_wins': resume_team['quad4_wins'],
                    'quad4_losses': resume_team['quad4_losses'],
                    'sor_rank': resume_team['sor_rank'],
                    'confidence': 1.0  # Manual mapping = 100% confidence
                })
                continue
        
        # Step 2: Try fuzzy matching
        ncaa_normalized = normalize_name(ncaa_name)
        
        best_match = None
        best_score = 0
        
        for kp_team in kenpom_teams_list:
            kp_name = kp_team['name']
            kp_normalized = normalize_name(kp_name)
            
            scores = [
                similarity(ncaa_name, kp_name),
                similarity(ncaa_normalized, kp_normalized),
                similarity(ncaa_name.lower(), kp_name.lower())
            ]
            
            max_score = max(scores)
            
            if max_score > best_score:
                best_score = max_score
                best_match = kp_team
        
        # NCAA names should match KenPom very well (both official sources)
        if best_score > 0.75:
            matches.append({
                'team_id': best_match['team_id'],
                'kenpom_name': best_match['name'],
                'ncaa_name': ncaa_name,
                'net_rank': resume_team['net_rank'],
                'quad1_wins': resume_team['quad1_wins'],
                'quad1_losses': resume_team['quad1_losses'],
                'quad2_wins': resume_team['quad2_wins'],
                'quad2_losses': resume_team['quad2_losses'],
                'quad3_wins': resume_team['quad3_wins'],
                'quad3_losses': resume_team['quad3_losses'],
                'quad4_wins': resume_team['quad4_wins'],
                'quad4_losses': resume_team['quad4_losses'],
                'sor_rank': resume_team['sor_rank'],
                'confidence': best_score
            })
        else:
            unmatched.append({
                'ncaa_name': ncaa_name,
                'best_match': best_match['name'] if best_match else 'None',
                'confidence': best_score
            })
    
    db.close()
    
    print(f"✓ Matched {len(matches)} teams ({len(matches)/len(resume_data)*100:.1f}%)")
    
    if unmatched:
        print(f"\n⚠️  {len(unmatched)} teams not matched:")
        for team in unmatched[:10]:
            print(f"  - {team['ncaa_name']} (best: {team['best_match']}, {team['confidence']:.2f})")
        if len(unmatched) > 10:
            print(f"  ... and {len(unmatched) - 10} more")
    
    return matches, unmatched

def update_resume_metrics(matches, season=CURRENT_SEASON):
    """Update resume_metrics table with matched data"""
    db = get_db()
    cursor = db.cursor()
    
    # Clear old data for this season
    cursor.execute('DELETE FROM resume_metrics WHERE season = ?', (season,))
    
    # Insert new data
    for match in matches:
        cursor.execute('''
            INSERT INTO resume_metrics (
                team_id, season, net_rank,
                quad1_wins, quad1_losses,
                quad2_wins, quad2_losses,
                quad3_wins, quad3_losses,
                quad4_wins, quad4_losses,
                sor_rank
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match['team_id'],
            season,
            match['net_rank'],
            match['quad1_wins'],
            match['quad1_losses'],
            match['quad2_wins'],
            match['quad2_losses'],
            match['quad3_wins'],
            match['quad3_losses'],
            match['quad4_wins'],
            match['quad4_losses'],
            match['sor_rank']
        ))
    
    db.commit()
    db.close()
    
    print(f"✓ Updated {len(matches)} teams with resume data")

def import_ncaa_data(csv_path, season=CURRENT_SEASON):
    """Main function to import NCAA resume data from CSV"""
    print(f"\n{'='*60}")
    print(f"Importing NCAA Tournament Resume Data")
    print(f"{'='*60}\n")
    
    # Step 1: Ensure table exists
    add_resume_table()
    
    # Step 2: Load CSV
    resume_data = load_ncaa_csv(csv_path)
    if not resume_data:
        print("❌ No data loaded, aborting")
        return
    
    # Step 3: Match to database
    print("\nMatching teams to database...")
    matches, unmatched = match_teams_to_database(resume_data, season)
    
    # Step 4: Update database
    print("\nUpdating database...")
    update_resume_metrics(matches, season)
    
    print(f"\n{'='*60}")
    print(f"NCAA resume data import complete!")
    print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data source: NCAA.com")
    print(f"{'='*60}\n")
    
    return len(unmatched)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_ncaa_data.py <path_to_NCAA_Statistics.csv>")
        print("\nExample:")
        print("  python import_ncaa_data.py NCAA_Statistics.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    season = int(sys.argv[2]) if len(sys.argv) > 2 else CURRENT_SEASON
    
    unmatched_count = import_ncaa_data(csv_path, season)
    
    if unmatched_count and unmatched_count > 5:
        print(f"\n💡 Tip: {unmatched_count} teams didn't match.")
        print("   This is usually due to slight name differences.")
        print("   The matched teams will work perfectly!")