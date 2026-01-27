"""
Fetch actual game scores from ESPN API
Updates games table with real scores to compare against KenPom predictions

Run from project root:
    python scrapers/fetch_game_scores_espn.py              # Update all missing scores
    python scrapers/fetch_game_scores_espn.py --stats      # Show statistics
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
import sqlite3
from datetime import datetime, timedelta
import time
import argparse
import json

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = 2026

# ESPN API endpoints
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def fetch_espn_scores_for_date(date_str):
    """
    Fetch all game scores from ESPN for a specific date
    Returns dict of {(team1, team2): {home_score, away_score, home_team, away_team}}
    """
    try:
        # ESPN uses YYYYMMDD format
        espn_date = date_str.replace('-', '')
        
        params = {
            'dates': espn_date,
            'groups': 50,    # Get all Division I games
            'limit': 400     # Ensure we get all games for the day
        }
        
        response = requests.get(ESPN_SCOREBOARD_URL, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        games = {}
        
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            
            # Get competitors
            competitors = competition.get('competitors', [])
            if len(competitors) != 2:
                continue
            
            # Check if game is completed
            status = event.get('status', {}).get('type', {}).get('completed', False)
            if not status:
                continue
            
            home_team = None
            away_team = None
            home_score = None
            away_score = None
            
            for comp in competitors:
                team_name = comp.get('team', {}).get('displayName', '')
                score = comp.get('score')
                is_home = comp.get('homeAway') == 'home'
                
                if score:
                    score = int(score)
                
                if is_home:
                    home_team = team_name
                    home_score = score
                else:
                    away_team = team_name
                    away_score = score
            
            if home_team and away_team and home_score is not None and away_score is not None:
                # Store with both orderings for easier lookup
                games[(home_team.lower(), away_team.lower())] = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': home_score,
                    'away_score': away_score
                }
        
        return games
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ESPN data for {date_str}: {e}")
        return {}

def normalize_team_name(name):
    """Normalize team name for matching"""
    # Common normalizations
    name = name.lower().strip()
    
    # Remove common suffixes
    for suffix in [' wildcats', ' bulldogs', ' tigers', ' bears', ' eagles', 
                   ' hawks', ' panthers', ' cardinals', ' blue devils', ' tar heels',
                   ' crimson tide', ' volunteers', ' gators', ' seminoles', ' cavaliers',
                   ' hokies', ' yellow jackets', ' demon deacons', ' wolfpack', ' hurricanes',
                   ' fighting irish', ' spartans', ' buckeyes', ' wolverines', ' badgers',
                   ' hawkeyes', ' boilermakers', ' hoosiers', ' golden gophers', ' huskers',
                   ' jayhawks', ' cyclones', ' sooners', ' cowboys', ' longhorns',
                   ' mountaineers', ' red raiders', ' horned frogs', ' razorbacks',
                   ' aggies', ' rebels', ' commodores', ' gamecocks', ' bruins',
                   ' ducks', ' beavers', ' huskies', ' cougars', ' utes', ' buffaloes',
                   ' sun devils', ' trojans', ' cardinal', ' zags', ' gaels', ' broncos',
                   ' aztecs', ' wolf pack', ' running rebels', ' rainbow warriors',
                   ' owls', ' mustangs', ' mean green', ' roadrunners', ' miners',
                   ' racers', ' colonels', ' govs', ' skyhawks', ' redhawks', ' penguins']:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    return name.strip()

def update_scores_from_espn():
    """
    Update games table with actual scores from ESPN
    """
    print(f"\n{'='*60}")
    print("Fetching Actual Game Scores from ESPN")
    print(f"{'='*60}\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # Get all dates with games missing scores
    dates = cursor.execute('''
        SELECT DISTINCT game_date 
        FROM games 
        WHERE home_score IS NULL 
          AND game_date < date('now')
        ORDER BY game_date
    ''').fetchall()
    
    print(f"Found {len(dates)} dates with games needing scores\n")
    
    total_updated = 0
    dates_processed = 0
    
    # Build team name lookup
    teams = cursor.execute('SELECT team_id, name FROM teams WHERE season = ?', (CURRENT_SEASON,)).fetchall()
    team_name_to_id = {t['name'].lower(): t['team_id'] for t in teams}
    team_id_to_name = {t['team_id']: t['name'] for t in teams}
    
    for date_row in dates:
        game_date = date_row['game_date']
        dates_processed += 1
        
        print(f"  [{dates_processed}/{len(dates)}] {game_date}...", end=" ", flush=True)
        
        # Fetch ESPN scores for this date
        espn_games = fetch_espn_scores_for_date(game_date)
        
        if not espn_games:
            print("no ESPN data")
            time.sleep(0.3)
            continue
        
        # Get our games for this date that need scores
        our_games = cursor.execute('''
            SELECT g.id, g.game_id, g.home_team_id, g.away_team_id,
                   ht.name as home_name, at.name as away_name
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            WHERE g.game_date = ?
              AND g.home_score IS NULL
        ''', (game_date,)).fetchall()
        
        games_updated = 0
        
        for game in our_games:
            home_name = game['home_name']
            away_name = game['away_name']
            
            # Try to find matching ESPN game
            home_normalized = normalize_team_name(home_name)
            away_normalized = normalize_team_name(away_name)
            
            matched = None
            
            # Try different matching strategies
            for (espn_home, espn_away), scores in espn_games.items():
                espn_home_norm = normalize_team_name(espn_home)
                espn_away_norm = normalize_team_name(espn_away)
                
                # Direct match
                if (home_normalized in espn_home_norm or espn_home_norm in home_normalized) and \
                   (away_normalized in espn_away_norm or espn_away_norm in away_normalized):
                    matched = scores
                    break
                
                # Swapped (ESPN might have home/away different)
                if (home_normalized in espn_away_norm or espn_away_norm in home_normalized) and \
                   (away_normalized in espn_home_norm or espn_home_norm in away_normalized):
                    # Swap scores
                    matched = {
                        'home_score': scores['away_score'],
                        'away_score': scores['home_score']
                    }
                    break
            
            if matched:
                cursor.execute('''
                    UPDATE games 
                    SET home_score = ?, away_score = ?
                    WHERE id = ?
                ''', (matched['home_score'], matched['away_score'], game['id']))
                games_updated += 1
        
        db.commit()
        
        if games_updated > 0:
            print(f"✓ {games_updated} games updated")
        else:
            print(f"0 matched (had {len(our_games)} games, ESPN had {len(espn_games)})")
        
        total_updated += games_updated
        
        # Small delay to be nice to ESPN
        time.sleep(0.3)
    
    db.close()
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Dates processed: {dates_processed}")
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
            margin_actual = g['home_score'] - g['away_score']
            margin_pred = g['home_pred'] - g['away_pred'] if g['home_pred'] else 0
            vs_spread = margin_actual - margin_pred
            diff = f" (vs exp: {vs_spread:+.1f})" if g['home_pred'] else ""
            print(f"    {g['game_date']}: {g['home']} vs {g['away']}: {actual} (pred: {pred}){diff}")
    
    print(f"{'='*60}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch actual game scores from ESPN')
    parser.add_argument('--stats', action='store_true', help='Show games table statistics')
    parser.add_argument('--date', type=str, help='Fetch specific date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
    elif args.date:
        print(f"Fetching scores for {args.date}...")
        scores = fetch_espn_scores_for_date(args.date)
        print(f"Found {len(scores)} completed games:")
        for (home, away), data in list(scores.items())[:10]:
            print(f"  {data['home_team']} {data['home_score']} - {data['away_score']} {data['away_team']}")
    else:
        update_scores_from_espn()
        show_stats()