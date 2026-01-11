import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
from difflib import SequenceMatcher
import time
import re

DATABASE = 'kenpom.db'
NET_URL = "https://www.warrennolan.com/basketball/2026/net"
NITTY_URL = "https://www.warrennolan.com/basketball/2026/net-nitty"
CURRENT_SEASON = 2026

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
    if not record_str or record_str == '-':
        return 0, 0
    
    try:
        parts = record_str.strip().split('-')
        wins = int(parts[0])
        losses = int(parts[1]) if len(parts) > 1 else 0
        return wins, losses
    except:
        return 0, 0

def clean_team_name(name):
    """Extract team name from format like 'MichiganBig Ten (2-0)' """
    # Remove conference info in parentheses
    name = re.sub(r'\([^)]*\)', '', name)
    
    # Common conference names that might be concatenated
    conferences = [
        'Big Ten', 'Big 12', 'ACC', 'SEC', 'Big East', 'Pac-12',
        'Atlantic 10', 'Mountain West', 'West Coast', 'American',
        'Conference USA', 'MAC', 'Sun Belt', 'WAC', 'Summit',
        'Patriot', 'Ivy', 'MAAC', 'Southern', 'Southland',
        'Big Sky', 'Big South', 'Colonial', 'Horizon', 'MEAC',
        'Missouri Valley', 'Northeast', 'Ohio Valley', 'SWAC'
    ]
    
    # Try to split off conference name
    for conf in conferences:
        conf_pattern = conf.replace(' ', '')  # Remove spaces for matching
        if conf_pattern.lower() in name.lower():
            # Split on the conference name
            parts = re.split(conf_pattern, name, flags=re.IGNORECASE)
            if parts[0]:
                name = parts[0]
                break
    
    return name.strip()

def scrape_net_rankings():
    """Scrape NET rankings from main page"""
    print(f"Fetching NET rankings from {NET_URL}...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(NET_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            print("❌ Could not find NET table")
            return {}
        
        rows = table.find_all('tr')[1:]
        net_data = {}
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            
            try:
                team_name = cells[0].get_text(strip=True)
                net_rank_text = cells[2].get_text(strip=True)
                
                if team_name and net_rank_text.isdigit():
                    net_data[team_name] = int(net_rank_text)
            except:
                continue
        
        print(f"✓ Scraped NET rankings for {len(net_data)} teams")
        return net_data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching NET data: {e}")
        return {}

def scrape_nitty_gritty():
    """Scrape quad records from nitty-gritty page"""
    print(f"Fetching quad records from {NITTY_URL}...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(NITTY_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            print("❌ Could not find nitty-gritty table")
            return []
        
        rows = table.find_all('tr')[1:]  # Skip header
        quad_data = []
        
        for row in rows:
            cells = row.find_all('td')
            
            # Need at least 14 columns for quad data
            if len(cells) < 14:
                continue
            
            try:
                # Column structure based on debug output:
                # 0: NET rank
                # 1: Team + Conference
                # 10: Q1 record
                # 11: Q2 record
                # 12: Q3 record
                # 13: Q4 record
                
                raw_team = cells[1].get_text(strip=True)
                team_name = clean_team_name(raw_team)
                
                q1_record = cells[10].get_text(strip=True)
                q2_record = cells[11].get_text(strip=True)
                q3_record = cells[12].get_text(strip=True)
                q4_record = cells[13].get_text(strip=True)
                
                q1_w, q1_l = parse_quad_record(q1_record)
                q2_w, q2_l = parse_quad_record(q2_record)
                q3_w, q3_l = parse_quad_record(q3_record)
                q4_w, q4_l = parse_quad_record(q4_record)
                
                if team_name:
                    quad_data.append({
                        'team_name': team_name,
                        'quad1_wins': q1_w,
                        'quad1_losses': q1_l,
                        'quad2_wins': q2_w,
                        'quad2_losses': q2_l,
                        'quad3_wins': q3_w,
                        'quad3_losses': q3_l,
                        'quad4_wins': q4_w,
                        'quad4_losses': q4_l,
                    })
                
            except Exception as e:
                continue
        
        print(f"✓ Scraped quad records for {len(quad_data)} teams")
        return quad_data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching quad data: {e}")
        return []

def merge_data(net_data, quad_data):
    """Merge NET rankings with quad records"""
    print("\nMerging NET and quad data...")
    
    complete_data = []
    
    for quad_team in quad_data:
        team_name = quad_team['team_name']
        
        # Try to find NET rank for this team
        net_rank = net_data.get(team_name)
        
        # If not found, try fuzzy matching
        if not net_rank:
            best_match = None
            best_score = 0
            
            for net_team_name, rank in net_data.items():
                score = similarity(team_name, net_team_name)
                if score > best_score:
                    best_score = score
                    best_match = rank
            
            if best_score > 0.8:
                net_rank = best_match
        
        complete_data.append({
            'team_name': team_name,
            'net_rank': net_rank,
            'quad1_wins': quad_team['quad1_wins'],
            'quad1_losses': quad_team['quad1_losses'],
            'quad2_wins': quad_team['quad2_wins'],
            'quad2_losses': quad_team['quad2_losses'],
            'quad3_wins': quad_team['quad3_wins'],
            'quad3_losses': quad_team['quad3_losses'],
            'quad4_wins': quad_team['quad4_wins'],
            'quad4_losses': quad_team['quad4_losses'],
            'sor_rank': None
        })
    
    print(f"✓ Merged data for {len(complete_data)} teams")
    return complete_data

def match_teams_to_database(resume_data, season=CURRENT_SEASON):
    """Match WarrenNolan team names to KenPom database team_ids"""
    db = get_db()
    
    kenpom_teams = db.execute(
        'SELECT team_id, name FROM teams WHERE season = ?',
        (season,)
    ).fetchall()
    
    kenpom_teams_list = [{'team_id': t['team_id'], 'name': t['name']} for t in kenpom_teams]
    
    matches = []
    unmatched = []
    
    for resume_team in resume_data:
        wn_name = resume_team['team_name']
        wn_normalized = normalize_name(wn_name)
        
        best_match = None
        best_score = 0
        
        for kp_team in kenpom_teams_list:
            kp_name = kp_team['name']
            kp_normalized = normalize_name(kp_name)
            
            scores = [
                similarity(wn_name, kp_name),
                similarity(wn_normalized, kp_normalized),
                similarity(wn_name.lower(), kp_name.lower())
            ]
            
            max_score = max(scores)
            
            if max_score > best_score:
                best_score = max_score
                best_match = kp_team
        
        if best_score > 0.75:
            matches.append({
                'team_id': best_match['team_id'],
                'kenpom_name': best_match['name'],
                'warrennolan_name': wn_name,
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
                'warrennolan_name': wn_name,
                'best_match': best_match['name'] if best_match else 'None',
                'confidence': best_score
            })
    
    db.close()
    
    print(f"✓ Matched {len(matches)} teams ({len(matches)/len(resume_data)*100:.1f}%)")
    
    if unmatched:
        print(f"\n⚠️  {len(unmatched)} teams not matched:")
        for team in unmatched[:10]:
            print(f"  - {team['warrennolan_name']} (best: {team['best_match']}, {team['confidence']:.2f})")
        if len(unmatched) > 10:
            print(f"  ... and {len(unmatched) - 10} more")
    
    return matches, unmatched

def update_resume_metrics(matches, season=CURRENT_SEASON):
    """Update resume_metrics table with matched data"""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('DELETE FROM resume_metrics WHERE season = ?', (season,))
    
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
    
    print(f"✓ Updated {len(matches)} teams with complete resume data")

def sync_resume_data(season=CURRENT_SEASON):
    """Main function to sync complete resume data"""
    print(f"\n{'='*60}")
    print(f"Syncing Tournament Resume Data (NET + Quads)")
    print(f"{'='*60}\n")
    
    add_resume_table()
    
    # Step 1: Get NET rankings
    net_data = scrape_net_rankings()
    if not net_data:
        print("❌ No NET data, aborting")
        return
    
    # Step 2: Get quad records
    quad_data = scrape_nitty_gritty()
    if not quad_data:
        print("❌ No quad data, aborting")
        return
    
    # Step 3: Merge datasets
    complete_data = merge_data(net_data, quad_data)
    
    # Step 4: Match to database
    print("\nMatching teams to database...")
    matches, unmatched = match_teams_to_database(complete_data, season)
    
    # Step 5: Update database
    print("\nUpdating database...")
    update_resume_metrics(matches, season)
    
    print(f"\n{'='*60}")
    print(f"Resume data sync complete!")
    print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    return len(unmatched)

if __name__ == '__main__':
    import sys
    season = int(sys.argv[1]) if len(sys.argv) > 1 else CURRENT_SEASON
    unmatched_count = sync_resume_data(season)
    
    if unmatched_count and unmatched_count > 10:
        print(f"\n💡 Tip: {unmatched_count} teams didn't match.")
        print("   This is usually due to name differences between WarrenNolan and KenPom.")