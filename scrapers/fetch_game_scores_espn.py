"""
Fetch actual game scores from ESPN API
Updates games table with real scores to compare against KenPom predictions

Run from project root:
    python scrapers/fetch_game_scores_espn.py          # Update all missing scores
    python scrapers/fetch_game_scores_espn.py --stats  # Show statistics
"""

import os
import sys
from pathlib import Path
import requests
from datetime import datetime, timedelta
import time
import argparse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from utils.db import get_db, close_db, execute, commit, db_type

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CURRENT_SEASON = 2026
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

# KenPom to ESPN name mappings
KENPOM_TO_ESPN = {
    'Albany': 'ualbany',
    'American': 'american university',
    'Gardner-Webb': 'gardner-webb runnin',
    'Seattle': 'seattle u',
    'Central Connecticut': 'central connecticut',
    'Southeast Missouri': 'southeast missouri state',
    'Middle Tennessee': 'middle tennessee blue',
    'Stony Brook': 'stony brook',
    'UC Davis': 'uc davis',
    'Tarleton St.': 'tarleton state',
    'UMass Lowell': 'umass lowell',
    'Florida St.': 'florida state',
    'N.C. State': 'nc state',
    'Michigan St.': 'michigan state',
    'Ohio St.': 'ohio state',
    'Penn St.': 'penn state',
    'Arizona St.': 'arizona state',
    'Iowa St.': 'iowa state',
    'Kansas St.': 'kansas state',
    'Oklahoma St.': 'oklahoma state',
    'Connecticut': 'uconn',
    'Mississippi': 'ole miss',
    'Mississippi St.': 'mississippi state',
    'South Carolina St.': 'south carolina state',
    'Miami FL': 'miami',
    'USC': 'usc',
    'Boise St.': 'boise state',
    'Colorado St.': 'colorado state',
    'Fresno St.': 'fresno state',
    'San Diego St.': 'san diego state',
    'San Jose St.': 'san jose state',
    'Utah St.': 'utah state',
    'Miami OH': 'miami (oh)',
    'Ball St.': 'ball state',
    'Kent St.': 'kent state',
    'Idaho St.': 'idaho state',
    'Montana St.': 'montana state',
    'Portland St.': 'portland state',
    'Sacramento St.': 'sacramento state',
    'Weber St.': 'weber state',
    'CSUN': 'cal state northridge',
    'Cal St. Bakersfield': 'cal state bakersfield',
    'Cal St. Fullerton': 'cal state fullerton',
    'Long Beach St.': 'long beach state',
    'Hawaii': "hawai'i",
    'FIU': 'florida international',
    'Jacksonville St.': 'jacksonville state',
    'Kennesaw St.': 'kennesaw state',
    'Missouri St.': 'missouri state',
    'New Mexico St.': 'new mexico state',
    'Sam Houston St.': 'sam houston',
    'Sam Houston': 'sam houston',
    'Cleveland St.': 'cleveland state',
    'IU Indy': 'iu indianapolis',
    'Wright St.': 'wright state',
    'Youngstown St.': 'youngstown state',
    'Coppin St.': 'coppin state',
    'Delaware St.': 'delaware state',
    'Morgan St.': 'morgan state',
    'Norfolk St.': 'norfolk state',
    'Illinois Chicago': 'uic',
    'Illinois St.': 'illinois state',
    'Indiana St.': 'indiana state',
    'Murray St.': 'murray state',
    'Wichita St.': 'wichita state',
    'Chicago St.': 'chicago state',
    'LIU': 'long island university',
    'Penn': 'pennsylvania',
    'Morehead St.': 'morehead state',
    'SIUE': 'siu edwardsville',
    'Tennessee Martin': 'ut martin',
    'Tennessee St.': 'tennessee state',
    'Loyola MD': 'loyola maryland',
    'Appalachian St.': 'app state',
    'Arkansas St.': 'arkansas state',
    'Georgia St.': 'georgia state',
    'Louisiana Monroe': 'ul monroe',
    'Louisiana': 'louisiana',
    'Texas St.': 'texas state',
    'East Tennessee St.': 'east tennessee state',
    'Alabama St.': 'alabama state',
    'Alcorn St.': 'alcorn state',
    'Arkansas Pine Bluff': 'arkansas-pine bluff',
    'Bethune Cookman': 'bethune-cookman',
    'Jackson St.': 'jackson state',
    'Grambling St.': 'grambling',
    'Mississippi Valley St.': 'mississippi valley state',
    'Northwestern St.': 'northwestern state',
    'Southeastern Louisiana': 'se louisiana',
    'Texas A&M Corpus Chris': 'texas a&m-corpus christi',
    'Nicholls St.': 'nicholls',
    'Nebraska Omaha': 'omaha',
    'North Dakota St.': 'north dakota state',
    'South Dakota St.': 'south dakota state',
    'St. Thomas': 'st. thomas-minnesota',
    'Cal Baptist': 'california baptist',
    'Tarleton': 'tarleton state',
    'UT Rio Grande Valley': 'ut rio grande valley',
    'Oregon St.': 'oregon state',
    'Washington St.': 'washington state',
    'Gardner Webb': 'gardner-webb',
    'USC Upstate': 'south carolina upstate',
    'Queens': 'queens university',
}


def fetch_espn_scores_for_date(date_str):
    """Fetch all completed game scores from ESPN for a specific date."""
    try:
        espn_date = date_str.replace('-', '')
        params = {'dates': espn_date, 'groups': 50, 'limit': 400}
        response = requests.get(ESPN_SCOREBOARD_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        games = {}
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            if len(competitors) != 2:
                continue

            status = event.get('status', {}).get('type', {}).get('completed', False)
            if not status:
                continue

            home_team = away_team = home_score = away_score = None
            for comp in competitors:
                team_name = comp.get('team', {}).get('displayName', '')
                score = comp.get('score')
                is_home = comp.get('homeAway') == 'home'
                if score:
                    score = int(score)
                if is_home:
                    home_team, home_score = team_name, score
                else:
                    away_team, away_score = team_name, score

            if home_team and away_team and home_score is not None and away_score is not None:
                games[(home_team.lower(), away_team.lower())] = {
                    'home_team': home_team, 'away_team': away_team,
                    'home_score': home_score, 'away_score': away_score
                }

        return games

    except requests.exceptions.RequestException as e:
        print(f"Error fetching ESPN data for {date_str}: {e}")
        return {}


def normalize_team_name(name):
    name = name.lower().strip()
    name = name.replace('\u00e9', 'e').replace('\u00f1', 'n').replace('\u2019', "'")
    return name


def strip_mascot(name):
    multi_word_mascots = [
        " ragin' cajuns", ' blue devils', ' tar heels', ' crimson tide',
        ' yellow jackets', ' demon deacons', ' fighting irish', ' golden gophers',
        ' red raiders', ' horned frogs', ' sun devils', ' wolf pack',
        ' running rebels', ' rainbow warriors', ' mean green', ' red wolves',
        ' golden lions', ' black knights', ' fighting camels', ' golden griffins',
        ' blue hens', ' fighting illini', ' golden flashes', ' mountain hawks',
        ' black bears', ' red foxes', ' golden eagles', ' great danes',
        ' river hawks', ' purple eagles', ' fighting hawks', ' blue hose',
        ' big red', ' big green', ' golden hurricane', ' red storm',
        ' golden grizzlies', ' green wave', ' thundering herd', ' blue demons',
        ' nittany lions', ' delta devils', ' golden suns', ' red flash',
        ' scarlet knights', ' golden bears', ' screaming eagles',
        ' purple aces', " runnin' bulldogs",
    ]
    for mascot in multi_word_mascots:
        if name.endswith(mascot):
            return name[:-len(mascot)].strip()
    parts = name.rsplit(' ', 1)
    if len(parts) == 2 and len(parts[0]) >= 2:
        return parts[0].strip()
    return name


def names_match(kenpom_name, espn_raw_name):
    kp = normalize_team_name(kenpom_name)
    espn = normalize_team_name(espn_raw_name)
    if kp == espn:
        return True
    if kp == strip_mascot(espn):
        return True
    return False


def update_scores_from_espn():
    print(f"\n{'='*60}")
    print(f"Fetching Game Scores from ESPN [{db_type()}]")
    print(f"{'='*60}\n")

    db = get_db()

    dates = execute(db, '''
        SELECT DISTINCT game_date
        FROM games
        WHERE home_score IS NULL
          AND game_date < CURRENT_DATE
        ORDER BY game_date
    ''').fetchall()

    print(f"Found {len(dates)} dates with games needing scores\n")

    total_updated = 0

    for i, date_row in enumerate(dates, 1):
        game_date = date_row['game_date']
        print(f"  [{i}/{len(dates)}] {game_date}...", end=" ", flush=True)

        espn_games = fetch_espn_scores_for_date(game_date)

        if not espn_games:
            print("no ESPN data")
            time.sleep(0.3)
            continue

        our_games = execute(db, '''
            SELECT g.id, g.home_team_id, g.away_team_id,
                   ht.name as home_name, at.name as away_name
            FROM games g
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            WHERE g.game_date = ? AND g.home_score IS NULL
        ''', (game_date,)).fetchall()

        games_updated = 0
        for game in our_games:
            home_mapped = KENPOM_TO_ESPN.get(game['home_name'], game['home_name'])
            away_mapped = KENPOM_TO_ESPN.get(game['away_name'], game['away_name'])

            matched = None
            for (espn_home, espn_away), scores in espn_games.items():
                if names_match(home_mapped, espn_home) and names_match(away_mapped, espn_away):
                    matched = scores
                    break
                if names_match(home_mapped, espn_away) and names_match(away_mapped, espn_home):
                    matched = {'home_score': scores['away_score'], 'away_score': scores['home_score']}
                    break

            if matched:
                execute(db, '''
                    UPDATE games SET home_score = ?, away_score = ? WHERE id = ?
                ''', (matched['home_score'], matched['away_score'], game['id']))
                games_updated += 1

        commit(db)

        if games_updated == len(our_games):
            print(f"✓ {games_updated} games updated")
        elif games_updated > 0:
            print(f"✓ {games_updated}/{len(our_games)} games updated")
        else:
            print(f"0 matched ({len(our_games)} games)")

        total_updated += games_updated
        time.sleep(0.3)

    close_db(db)

    print(f"\n{'='*60}")
    print(f"  Games updated with scores: {total_updated}")
    print(f"{'='*60}\n")
    return total_updated


def show_stats():
    db = get_db()
    total = execute(db, 'SELECT COUNT(*) as c FROM games').fetchone()['c']
    with_scores = execute(db, 'SELECT COUNT(*) as c FROM games WHERE home_score IS NOT NULL').fetchone()['c']
    missing = execute(db, "SELECT COUNT(*) as c FROM games WHERE home_score IS NULL AND game_date < CURRENT_DATE").fetchone()['c']
    date_range = execute(db, 'SELECT MIN(game_date) as mn, MAX(game_date) as mx FROM games').fetchone()
    close_db(db)

    print(f"\n{'='*60}")
    print(f"Games Table Statistics [{db_type()}]")
    print(f"{'='*60}")
    print(f"  Total: {total}  With scores: {with_scores}  Missing: {missing}")
    if date_range and date_range['mn']:
        print(f"  Date range: {date_range['mn']} to {date_range['mx']}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch actual game scores from ESPN')
    parser.add_argument('--stats', action='store_true')
    parser.add_argument('--date', type=str, help='Fetch specific date (YYYY-MM-DD)')
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.date:
        scores = fetch_espn_scores_for_date(args.date)
        print(f"Found {len(scores)} completed games on {args.date}")
    else:
        update_scores_from_espn()
        show_stats()