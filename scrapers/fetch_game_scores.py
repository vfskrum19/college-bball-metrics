"""
Fetch actual game scores from Sports Reference
Updates games table with real scores to compare against KenPom predictions

Run from project root:
    python scrapers/fetch_game_scores.py              # Update all missing scores
    python scrapers/fetch_game_scores.py --team "Duke"  # Fetch specific team's games
    python scrapers/fetch_game_scores.py --stats      # Show statistics
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime, timedelta
import time
import argparse
import re

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = 2026

# Sports Reference base URL
SREF_BASE_URL = "https://www.sports-reference.com/cbb"

# Team name mappings from KenPom to Sports Reference slug format
TEAM_SLUG_OVERRIDES = {
    'Connecticut': 'connecticut',
    'UConn': 'connecticut',
    'Miami FL': 'miami-fl',
    'Miami OH': 'miami-oh',
    'N.C. State': 'north-carolina-state',
    'North Carolina St.': 'north-carolina-state',
    'UNCG': 'north-carolina-greensboro',
    'UNC Greensboro': 'north-carolina-greensboro',
    'UNC Wilmington': 'north-carolina-wilmington',
    'UNC Asheville': 'north-carolina-asheville',
    'USC': 'southern-california',
    'LSU': 'louisiana-state',
    'VCU': 'virginia-commonwealth',
    'UCF': 'central-florida',
    'SMU': 'southern-methodist',
    'BYU': 'brigham-young',
    'TCU': 'texas-christian',
    'UNLV': 'nevada-las-vegas',
    'UTEP': 'texas-el-paso',
    'UAB': 'alabama-birmingham',
    'Ole Miss': 'mississippi',
    'Mississippi': 'mississippi',
    'Pitt': 'pittsburgh',
    'Pittsburgh': 'pittsburgh',
    'UMass': 'massachusetts',
    'Massachusetts': 'massachusetts',
    'St. John\'s': 'st-johns-ny',
    "Saint John's": 'st-johns-ny',
    'St. Bonaventure': 'st-bonaventure',
    "Saint Joseph's": 'saint-josephs',
    "Saint Louis": 'saint-louis',
    "Saint Mary's": 'saint-marys-ca',
    "Saint Peter's": 'saint-peters',
    'Loyola Chicago': 'loyola-il',
    'Loyola MD': 'loyola-md',
    'Loyola Marymount': 'loyola-marymount',
    'Texas A&M': 'texas-am',
    'Texas A&M Commerce': 'texas-am-commerce',
    'Texas A&M Corpus Chris': 'texas-am-corpus-christi',
    'Penn St.': 'penn-state',
    'Ohio St.': 'ohio-state',
    'Michigan St.': 'michigan-state',
    'Florida St.': 'florida-state',
    'Oklahoma St.': 'oklahoma-state',
    'Kansas St.': 'kansas-state',
    'Iowa St.': 'iowa-state',
    'Washington St.': 'washington-state',
    'Oregon St.': 'oregon-state',
    'Arizona St.': 'arizona-state',
    'Colorado St.': 'colorado-state',
    'San Diego St.': 'san-diego-state',
    'Fresno St.': 'fresno-state',
    'San Jose St.': 'san-jose-state',
    'Boise St.': 'boise-state',
    'Utah St.': 'utah-state',
    'New Mexico St.': 'new-mexico-state',
    'Arkansas St.': 'arkansas-state',
    'Georgia St.': 'georgia-state',
    'Appalachian St.': 'appalachian-state',
    'Ga. Southern': 'georgia-southern',
    'Ball St.': 'ball-state',
    'Kent St.': 'kent-state',
    'Bowling Green': 'bowling-green-state',
    'Wright St.': 'wright-state',
    'Wichita St.': 'wichita-state',
    'Illinois St.': 'illinois-state',
    'Indiana St.': 'indiana-state',
    'Missouri St.': 'missouri-state',
    'Murray St.': 'murray-state',
    'Morehead St.': 'morehead-state',
    'Youngstown St.': 'youngstown-state',
    'Cleveland St.': 'cleveland-state',
    'Northern Ky.': 'northern-kentucky',
    'Northern Kentucky': 'northern-kentucky',
    'Green Bay': 'wisconsin-green-bay',
    'Milwaukee': 'wisconsin-milwaukee',
    'Long Beach St.': 'long-beach-state',
    'Sacramento St.': 'sacramento-state',
    'Portland St.': 'portland-state',
    'Cal Poly': 'cal-poly',
    'Cal St. Bakersfield': 'cal-state-bakersfield',
    'Cal St. Fullerton': 'cal-state-fullerton',
    'Cal St. Northridge': 'cal-state-northridge',
    'UC Davis': 'uc-davis',
    'UC Irvine': 'uc-irvine',
    'UC Riverside': 'uc-riverside',
    'UC San Diego': 'uc-san-diego',
    'UC Santa Barbara': 'uc-santa-barbara',
    'South Florida': 'south-florida',
    'North Florida': 'north-florida',
    'Central Florida': 'central-florida',
    'Florida Atlantic': 'florida-atlantic',
    'Florida Gulf Coast': 'florida-gulf-coast',
    'Florida International': 'florida-international',
    'North Texas': 'north-texas',
    'UTSA': 'texas-san-antonio',
    'UT Arlington': 'texas-arlington',
    'UT Rio Grande Valley': 'texas-rio-grande-valley',
    'Southeast Missouri St.': 'southeast-missouri-state',
    'SIU Edwardsville': 'southern-illinois-edwardsville',
    'Southern Illinois': 'southern-illinois',
    'Northern Illinois': 'northern-illinois',
    'Eastern Illinois': 'eastern-illinois',
    'Western Illinois': 'western-illinois',
    'Eastern Michigan': 'eastern-michigan',
    'Western Michigan': 'western-michigan',
    'Central Michigan': 'central-michigan',
    'Northern Iowa': 'northern-iowa',
    'Col. of Charleston': 'charleston',
    'Charleston Southern': 'charleston-southern',
    'Coastal Carolina': 'coastal-carolina',
    'East Carolina': 'east-carolina',
    'Western Carolina': 'western-carolina',
    'South Carolina St.': 'south-carolina-state',
    'North Carolina A&T': 'north-carolina-at',
    'North Carolina Central': 'north-carolina-central',
    'Bethune Cookman': 'bethune-cookman',
    'Coppin St.': 'coppin-state',
    'Morgan St.': 'morgan-state',
    'Norfolk St.': 'norfolk-state',
    'Delaware St.': 'delaware-state',
    'Maryland Eastern Shore': 'maryland-eastern-shore',
    'Howard': 'howard',
    'Hampton': 'hampton',
    'Grambling St.': 'grambling',
    'Grambling': 'grambling',
    'Jackson St.': 'jackson-state',
    'Alabama St.': 'alabama-state',
    'Alabama A&M': 'alabama-am',
    'Alcorn St.': 'alcorn-state',
    'Southern': 'southern',
    'Prairie View A&M': 'prairie-view',
    'Texas Southern': 'texas-southern',
    'Arkansas Pine Bluff': 'arkansas-pine-bluff',
    'Mississippi Valley St.': 'mississippi-valley-state',
    'McNeese St.': 'mcneese-state',
    'McNeese': 'mcneese-state',
    'Nicholls St.': 'nicholls-state',
    'Northwestern St.': 'northwestern-state',
    'Southeastern Louisiana': 'southeastern-louisiana',
    'Central Arkansas': 'central-arkansas',
    'Stephen F. Austin': 'stephen-f-austin',
    'Sam Houston St.': 'sam-houston-state',
    'Sam Houston': 'sam-houston-state',
    'Abilene Christian': 'abilene-christian',
    'Tarleton St.': 'tarleton-state',
    'Utah Tech': 'utah-tech',
    'Grand Canyon': 'grand-canyon',
    'Seattle': 'seattle',
    'Cal Baptist': 'california-baptist',
    'Mount St. Mary\'s': 'mount-st-marys',
    'Fairleigh Dickinson': 'fairleigh-dickinson',
    'LIU': 'long-island-university',
    'St. Francis NY': 'st-francis-ny',
    'St. Francis PA': 'saint-francis-pa',
    'Sacred Heart': 'sacred-heart',
    'Central Connecticut': 'central-connecticut-state',
    'Chicago St.': 'chicago-state',
    'UMKC': 'umkc',
    'Nebraska Omaha': 'nebraska-omaha',
    'North Dakota St.': 'north-dakota-state',
    'South Dakota St.': 'south-dakota-state',
    'Oral Roberts': 'oral-roberts',
    'Denver': 'denver',
    'UMBC': 'umbc',
    'UMass Lowell': 'massachusetts-lowell',
    'Albany': 'albany-ny',
    'Stony Brook': 'stony-brook',
    'Binghamton': 'binghamton',
    'Vermont': 'vermont',
    'New Hampshire': 'new-hampshire',
    'Maine': 'maine',
    'Army West Point': 'army',
    'Army': 'army',
    'Navy': 'navy',
    'American': 'american',
    'Boston University': 'boston-university',
    'Bucknell': 'bucknell',
    'Colgate': 'colgate',
    'Holy Cross': 'holy-cross',
    'Lafayette': 'lafayette',
    'Lehigh': 'lehigh',
    'Loyola MD': 'loyola-md',
    'Illinois Chicago': 'illinois-chicago',
    'Detroit Mercy': 'detroit-mercy',
    'Oakland': 'oakland',
    'Robert Morris': 'robert-morris',
    'Northern Kentucky': 'northern-kentucky',
    'Kennesaw St.': 'kennesaw-state',
    'Jacksonville St.': 'jacksonville-state',
    'Tennessee St.': 'tennessee-state',
    'Tennessee Tech': 'tennessee-tech',
    'UT Martin': 'tennessee-martin',
    'Eastern Kentucky': 'eastern-kentucky',
    'Eastern Washington': 'eastern-washington',
    'Northern Arizona': 'northern-arizona',
    'Northern Colorado': 'northern-colorado',
    'Montana St.': 'montana-state',
    'Weber St.': 'weber-state',
    'Idaho St.': 'idaho-state',
    'Southern Utah': 'southern-utah',
    'Queens': 'queens-nc',
    'Lindenwood': 'lindenwood',
    'Southern Indiana': 'southern-indiana',
    'Bellarmine': 'bellarmine',
    'West Georgia': 'west-georgia',
    'Le Moyne': 'le-moyne',
    'Stonehill': 'stonehill',
    'Mercyhurst': 'mercyhurst',
}

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def team_name_to_slug(team_name):
    """Convert KenPom team name to Sports Reference URL slug"""
    # Check overrides first
    if team_name in TEAM_SLUG_OVERRIDES:
        return TEAM_SLUG_OVERRIDES[team_name]
    
    # Default conversion: lowercase, replace spaces/periods with hyphens
    slug = team_name.lower()
    slug = re.sub(r'[.\']', '', slug)  # Remove periods and apostrophes
    slug = re.sub(r'\s+', '-', slug)   # Replace spaces with hyphens
    slug = re.sub(r'-+', '-', slug)    # Collapse multiple hyphens
    
    return slug

def fetch_team_schedule(team_name, season=CURRENT_SEASON):
    """
    Fetch a team's schedule/results from Sports Reference
    Returns list of game results
    """
    slug = team_name_to_slug(team_name)
    
    # Sports Reference uses the ending year for season
    url = f"{SREF_BASE_URL}/schools/{slug}/men/{season}-schedule.html"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the schedule table
        schedule_table = soup.find('table', {'id': 'schedule'})
        if not schedule_table:
            return None
        
        games = []
        tbody = schedule_table.find('tbody')
        if not tbody:
            return None
            
        for row in tbody.find_all('tr'):
            # Skip header rows within table
            if row.get('class') and 'thead' in row.get('class'):
                continue
                
            cells = row.find_all(['td', 'th'])
            if len(cells) < 10:
                continue
            
            try:
                # Parse date
                date_cell = row.find('td', {'data-stat': 'date_game'})
                if not date_cell:
                    continue
                date_link = date_cell.find('a')
                if date_link:
                    date_str = date_link.text.strip()
                else:
                    date_str = date_cell.text.strip()
                
                # Parse opponent
                opp_cell = row.find('td', {'data-stat': 'opp_id'})
                if opp_cell:
                    opp_link = opp_cell.find('a')
                    opponent = opp_link.text.strip() if opp_link else opp_cell.text.strip()
                else:
                    continue
                
                # Parse location (home/away)
                loc_cell = row.find('td', {'data-stat': 'game_location'})
                location = loc_cell.text.strip() if loc_cell else ''
                is_home = location != '@'
                
                # Parse scores
                team_score_cell = row.find('td', {'data-stat': 'pts'})
                opp_score_cell = row.find('td', {'data-stat': 'opp_pts'})
                
                if not team_score_cell or not opp_score_cell:
                    continue
                    
                team_score_text = team_score_cell.text.strip()
                opp_score_text = opp_score_cell.text.strip()
                
                # Skip games without scores (future games)
                if not team_score_text or not opp_score_text:
                    continue
                
                team_score = int(team_score_text)
                opp_score = int(opp_score_text)
                
                games.append({
                    'date': date_str,
                    'opponent': opponent,
                    'is_home': is_home,
                    'team_score': team_score,
                    'opp_score': opp_score
                })
                
            except (ValueError, AttributeError) as e:
                continue
        
        return games
        
    except requests.exceptions.RequestException as e:
        print(f"  ⚠ Error fetching {team_name}: {e}")
        return None

def parse_sref_date(date_str, season=CURRENT_SEASON):
    """
    Parse Sports Reference date format to YYYY-MM-DD
    Input formats: "Fri, Nov 8, 2024" or "Nov 8, 2024" or similar
    """
    try:
        # Remove day of week if present
        if ',' in date_str:
            parts = date_str.split(',')
            if len(parts) >= 2:
                # Could be "Fri, Nov 8, 2024" or "Nov 8, 2024"
                if len(parts) == 3:
                    date_str = f"{parts[1].strip()}, {parts[2].strip()}"
                elif len(parts) == 2:
                    date_str = f"{parts[0].strip()}, {parts[1].strip()}"
        
        # Try parsing
        for fmt in ['%b %d, %Y', '%B %d, %Y', '%b %d %Y', '%Y-%m-%d']:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None
    except Exception:
        return None

def update_game_scores(limit=None):
    """
    Update games table with actual scores from Sports Reference
    Fetches each team's schedule and matches games
    """
    print(f"\n{'='*60}")
    print("Fetching Actual Game Scores from Sports Reference")
    print(f"{'='*60}\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # Get unique teams that have games without scores
    teams_query = '''
        SELECT DISTINCT t.team_id, t.name
        FROM teams t
        JOIN games g ON (g.home_team_id = t.team_id OR g.away_team_id = t.team_id)
        WHERE g.home_score IS NULL
          AND g.game_date < date('now')
          AND t.season = ?
        ORDER BY t.name
    '''
    
    if limit:
        teams_query = teams_query.replace('ORDER BY t.name', f'ORDER BY t.name LIMIT {limit}')
    
    teams = cursor.execute(teams_query, (CURRENT_SEASON,)).fetchall()
    
    print(f"Found {len(teams)} teams with games needing scores\n")
    
    total_updated = 0
    teams_processed = 0
    
    for team in teams:
        team_id = team['team_id']
        team_name = team['name']
        
        print(f"  [{teams_processed + 1}/{len(teams)}] {team_name}...", end=" ", flush=True)
        
        # Fetch team's schedule from Sports Reference
        schedule = fetch_team_schedule(team_name)
        
        if not schedule:
            print("⚠ Could not fetch schedule")
            teams_processed += 1
            time.sleep(2)  # Be nice to Sports Reference
            continue
        
        # Match games and update scores
        games_updated = 0
        
        for sref_game in schedule:
            # Parse the date
            game_date = parse_sref_date(sref_game['date'])
            if not game_date:
                continue
            
            # Determine home/away scores based on perspective
            if sref_game['is_home']:
                home_score = sref_game['team_score']
                away_score = sref_game['opp_score']
            else:
                home_score = sref_game['opp_score']
                away_score = sref_game['team_score']
            
            # Try to match with our games table
            # Match by team_id and date (team could be home or away)
            cursor.execute('''
                UPDATE games
                SET home_score = ?, away_score = ?
                WHERE game_date = ?
                  AND (home_team_id = ? OR away_team_id = ?)
                  AND home_score IS NULL
            ''', (home_score, away_score, game_date, team_id, team_id))
            
            if cursor.rowcount > 0:
                games_updated += cursor.rowcount
        
        db.commit()
        
        print(f"✓ {games_updated} games updated")
        total_updated += games_updated
        teams_processed += 1
        
        # Rate limiting - be respectful to Sports Reference
        time.sleep(2)
    
    db.close()
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Teams processed: {teams_processed}")
    print(f"  Games updated with scores: {total_updated}")
    print(f"{'='*60}\n")
    
    return total_updated

def show_stats():
    """Show current games table statistics"""
    db = get_db()
    cursor = db.cursor()
    
    # Total games
    total = cursor.execute('SELECT COUNT(*) FROM games').fetchone()[0]
    
    # Games with scores
    with_scores = cursor.execute(
        'SELECT COUNT(*) FROM games WHERE home_score IS NOT NULL'
    ).fetchone()[0]
    
    # Games without scores (past games)
    missing_scores = cursor.execute('''
        SELECT COUNT(*) FROM games 
        WHERE home_score IS NULL AND game_date < date('now')
    ''').fetchone()[0]
    
    # Date range
    date_range = cursor.execute('''
        SELECT MIN(game_date), MAX(game_date) FROM games
    ''').fetchone()
    
    # Sample of games with scores
    sample = cursor.execute('''
        SELECT g.game_date, ht.name as home, at.name as away,
               g.home_score, g.away_score, g.home_pred, g.away_pred
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        WHERE g.home_score IS NOT NULL
        ORDER BY g.game_date DESC
        LIMIT 5
    ''').fetchall()
    
    db.close()
    
    print(f"\n{'='*60}")
    print("Games Table Statistics")
    print(f"{'='*60}")
    print(f"  Total games: {total}")
    print(f"  With scores: {with_scores}")
    print(f"  Missing scores (past games): {missing_scores}")
    if date_range[0]:
        print(f"  Date range: {date_range[0]} to {date_range[1]}")
    
    if sample:
        print(f"\nRecent games with scores:")
        for g in sample:
            actual = f"{g['home_score']}-{g['away_score']}"
            pred = f"{g['home_pred']:.0f}-{g['away_pred']:.0f}" if g['home_pred'] else "N/A"
            diff = ""
            if g['home_score'] and g['home_pred']:
                home_diff = g['home_score'] - g['home_pred']
                away_diff = g['away_score'] - g['away_pred']
                margin_actual = g['home_score'] - g['away_score']
                margin_pred = g['home_pred'] - g['away_pred']
                vs_spread = margin_actual - margin_pred
                diff = f" (vs exp: {vs_spread:+.1f})"
            print(f"    {g['game_date']}: {g['home']} vs {g['away']}: {actual} (pred: {pred}){diff}")
    
    print(f"{'='*60}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch actual game scores from Sports Reference')
    parser.add_argument('--team', type=str, help='Fetch specific team schedule')
    parser.add_argument('--stats', action='store_true', help='Show games table statistics')
    parser.add_argument('--limit', type=int, help='Limit number of teams to process')
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
    elif args.team:
        print(f"Fetching schedule for {args.team}...")
        schedule = fetch_team_schedule(args.team)
        if schedule:
            print(f"Found {len(schedule)} games:")
            for g in schedule[:10]:
                loc = "vs" if g['is_home'] else "@"
                print(f"  {g['date']}: {loc} {g['opponent']} - {g['team_score']}-{g['opp_score']}")
        else:
            print("Could not fetch schedule")
    else:
        update_game_scores(limit=args.limit)
        show_stats()