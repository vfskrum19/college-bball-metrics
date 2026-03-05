"""
fetch_espn_shooting_stats.py

Fetches team shooting statistics from ESPN's public API:
  - Team 3-point percentage (made/attempted/pct)
  - Team free throw percentage (made/attempted/pct)
  - Opponent 3-point percentage allowed (defensive discipline)
  - Free throw attempt rate (FTA/FGA — how often they GET to the line)

Why ESPN for this instead of KenPom Four Factors?
  - KenPom's Four Factors (eFG%, TO%, OR%, FT Rate) are behind their paywall
  - ESPN surfaces raw shooting splits freely
  - 3PT% and FT% are strong tournament-predictive metrics we can display publicly

How ESPN IDs work (important):
  - Your DB uses KenPom's internal team_ids (e.g. 31, 34)
  - ESPN has their OWN internal IDs that are completely different numbers
  - You CANNOT use your DB team_id to call ESPN's stats endpoint directly
  - Solution: fetch ESPN's full team list first, match teams by name to get
    ESPN's ID, then use that ID for the per-team stats calls
  - This is the same approach fetch_espn_branding.py uses successfully

Run manually:
    python scrapers/fetch_espn_shooting_stats.py

Add to cron.py as an optional step (won't abort pipeline on failure).
"""

import os
import sys
import time
import requests
from difflib import SequenceMatcher

# Add project root to path so we can import utils/db.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.db import get_db

# ── Constants ─────────────────────────────────────────────────────────────────

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams"
ESPN_STATS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{espn_id}/statistics"

REQUEST_DELAY   = 0.35  # seconds between requests — be polite to ESPN's servers
REQUEST_TIMEOUT = 10    # seconds before giving up on a single request

# Manual overrides for teams whose names differ too much for fuzzy matching.
# Key = KenPom name, Value = ESPN displayName (exact).
# Add entries here if you see a team in the unmatched output at the end.
MANUAL_MAPPINGS = {
    "Appalachian St.":       "Appalachian State",
    "Arkansas St.":          "Arkansas State",
    "Ball St.":              "Ball State",
    "Boise St.":             "Boise State",
    "Bowling Green":         "Bowling Green",
    "Cal Baptist":           "California Baptist",
    "Cal Poly":              "Cal Poly",
    "Cal St. Bakersfield":   "Cal State Bakersfield",
    "Cal St. Fullerton":     "Cal State Fullerton",
    "Cal St. Northridge":    "Cal State Northridge",
    "Central Connecticut":   "Central Connecticut State",
    "Col. of Charleston":    "Charleston",
    "Colorado St.":          "Colorado State",
    "Eastern Illinois":      "Eastern Illinois",
    "Eastern Kentucky":      "Eastern Kentucky",
    "Eastern Michigan":      "Eastern Michigan",
    "Eastern Washington":    "Eastern Washington",
    "Fairleigh Dickinson":   "Fairleigh Dickinson",
    "Florida Atlantic":      "Florida Atlantic",
    "Florida Gulf Coast":    "Florida Gulf Coast",
    "Florida International": "FIU",
    "Florida St.":           "Florida State",
    "Fresno St.":            "Fresno State",
    "Ga. Southern":          "Georgia Southern",
    "Ga. Tech":              "Georgia Tech",
    "Gardner Webb":          "Gardner-Webb",
    "Illinois St.":          "Illinois State",
    "Indiana St.":           "Indiana State",
    "Iowa St.":              "Iowa State",
    "Jacksonville St.":      "Jacksonville State",
    "Kansas St.":            "Kansas State",
    "Kennesaw St.":          "Kennesaw State",
    "Kent St.":              "Kent State",
    "Long Island":           "LIU",
    "Louisiana Monroe":      "Louisiana Monroe",
    "Loyola Chicago":        "Loyola Chicago",
    "Loyola MD":             "Loyola Maryland",
    "McNeese St.":           "McNeese",
    "Miami FL":              "Miami",
    "Michigan St.":          "Michigan State",
    "Middle Tennessee":      "Middle Tennessee State",
    "Mississippi St.":       "Mississippi State",
    "Missouri St.":          "Missouri State",
    "Montana St.":           "Montana State",
    "Morehead St.":          "Morehead State",
    "Murray St.":            "Murray State",
    "NC St.":                "NC State",
    "New Mexico St.":        "New Mexico State",
    "Northern Illinois":     "Northern Illinois",
    "Northwestern St.":      "Northwestern State",
    "Ohio St.":              "Ohio State",
    "Oklahoma St.":          "Oklahoma State",
    "Oregon St.":            "Oregon State",
    "Penn St.":              "Penn State",
    "Sacramento St.":        "Sacramento State",
    "Sam Houston St.":       "Sam Houston",
    "San Diego St.":         "San Diego State",
    "SE Missouri St.":       "Southeast Missouri State",
    "Siu Edwardsville":      "SIU Edwardsville",
    "South Dakota St.":      "South Dakota State",
    "Southeast Missouri":    "Southeast Missouri State",
    "Stephen F. Austin":     "SFA",
    "Tarleton St.":          "Tarleton State",
    "Tennessee St.":         "Tennessee State",
    "Tennessee Tech":        "Tennessee Tech",
    "Texas A&M":             "Texas A&M",
    "Texas St.":             "Texas State",
    "UT Arlington":          "UT Arlington",
    "Utah St.":              "Utah State",
    "Wichita St.":           "Wichita State",
    "Wright St.":            "Wright State",
    "Youngstown St.":        "Youngstown State",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def similarity(a, b):
    """String similarity ratio between 0 and 1."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_name(name):
    """Normalize a team name to improve fuzzy matching across naming conventions."""
    replacements = {
        " university": "",
        " college": "",
        "saint ": "st. ",
        "&": "and",
    }
    n = name.lower().strip()
    for old, new in replacements.items():
        n = n.replace(old, new)
    return " ".join(n.split())

# ── Step 1: DB columns ────────────────────────────────────────────────────────

def add_shooting_columns():
    """
    Add shooting stat columns to teams table. Safe to run repeatedly —
    silently skips columns that already exist.
    """
    db = get_db()
    cursor = db.cursor()

    new_columns = [
        ("fg3_pct",             "REAL"),
        ("fg3_made",            "REAL"),
        ("fg3_att",             "REAL"),
        ("ft_pct",              "REAL"),
        ("ft_made",             "REAL"),
        ("ft_att",              "REAL"),
        ("opp_fg3_pct",         "REAL"),
        ("ft_rate",             "REAL"),
        ("shooting_updated_at", "TEXT"),
    ]

    added = 0
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE teams ADD COLUMN {col_name} {col_type}")
            added += 1
        except Exception:
            pass  # Column already exists

    db.commit()
    print(f"✓ Shooting stat columns ready ({added} new columns added)")

# ── Step 2: ESPN team list (ESPN's own IDs) ───────────────────────────────────

def fetch_espn_team_list():
    """
    Fetch all D1 teams from ESPN.

    Returns a list of dicts with espn_id (ESPN's internal ID, NOT your DB's
    team_id), plus name fields for matching.
    """
    try:
        response = requests.get(ESPN_TEAMS_URL, params={"limit": 1000}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        espn_teams = []
        for entry in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
            team = entry.get("team", {})
            espn_id = team.get("id")
            if not espn_id:
                continue
            name = team.get("displayName", "")
            espn_teams.append({
                "espn_id":      str(espn_id),
                "name":         name,
                "short_name":   team.get("shortDisplayName", ""),
                "abbreviation": team.get("abbreviation", ""),
                "normalized":   normalize_name(name),
            })

        print(f"  ESPN team list: {len(espn_teams)} teams fetched")
        return espn_teams

    except requests.RequestException as e:
        print(f"  ERROR fetching ESPN team list: {e}")
        return []

# ── Step 3: Match DB teams → ESPN teams ──────────────────────────────────────

def match_to_espn(db_teams, espn_teams):
    """
    Map each KenPom DB team to an ESPN team to get ESPN's internal ID.

    Matching order (first match wins):
      1. Manual mapping from MANUAL_MAPPINGS dict
      2. Exact case-insensitive name match
      3. Fuzzy match on display name, short name, and normalized name

    Returns a list of matched teams with both DB team_id and espn_id.
    Prints unmatched teams so you can add them to MANUAL_MAPPINGS.
    """
    matched = []
    unmatched = []

    espn_by_name = {t["name"].lower(): t for t in espn_teams}

    for db_team in db_teams:
        kp_name = db_team["name"]
        found = None

        # 1. Manual mapping
        if kp_name in MANUAL_MAPPINGS:
            target = MANUAL_MAPPINGS[kp_name].lower()
            found = espn_by_name.get(target)

        # 2. Exact match
        if not found:
            found = espn_by_name.get(kp_name.lower())

        # 3. Fuzzy match
        if not found:
            best_score = 0
            kp_norm = normalize_name(kp_name)
            for espn_team in espn_teams:
                score = max(
                    similarity(kp_name, espn_team["name"]),
                    similarity(kp_name, espn_team["short_name"]),
                    similarity(kp_norm, espn_team["normalized"]),
                )
                if score > best_score:
                    best_score = score
                    if score > 0.82:
                        found = espn_team

        if found:
            matched.append({
                "team_id":   db_team["team_id"],
                "name":      kp_name,
                "espn_id":   found["espn_id"],
                "espn_name": found["name"],
            })
        else:
            unmatched.append(kp_name)

    pct = len(matched) / len(db_teams) * 100 if db_teams else 0
    print(f"  Matched {len(matched)}/{len(db_teams)} teams ({pct:.0f}%)")
    if unmatched:
        print(f"  Unmatched ({len(unmatched)}): {', '.join(unmatched[:10])}")
        if len(unmatched) > 10:
            print(f"    ... and {len(unmatched) - 10} more (add to MANUAL_MAPPINGS if needed)")

    return matched

# ── Step 4: Per-team stats from ESPN ─────────────────────────────────────────

def fetch_team_shooting(espn_id, team_name):
    """
    Hit ESPN's per-team statistics endpoint using ESPN's internal ID
    and extract the shooting stats we care about.

    Returns a dict of stat values, or None on failure/no data.
    """
    url = ESPN_STATS_URL.format(espn_id=espn_id)
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 404:
            return None

        if response.status_code == 400:
            print(f"    400 error for {team_name} (espn_id={espn_id})")
            return None

        response.raise_for_status()
        data = response.json()

        stats = {}
        fga = None

        for category in data.get("splits", {}).get("categories", []):
            for stat in category.get("stats", []):
                name  = stat.get("name", "")
                value = stat.get("value")
                if value is None:
                    continue
                try:
                    val = float(value)
                except (TypeError, ValueError):
                    continue

                # ESPN returns percentages as decimals — multiply by 100
                if name == "threePointFieldGoalPct":
                    stats["fg3_pct"] = round(val * 100, 1)
                elif name == "threePointFieldGoalsMade":
                    stats["fg3_made"] = round(val, 1)
                elif name == "threePointFieldGoalsAttempted":
                    stats["fg3_att"] = round(val, 1)
                elif name == "freeThrowPct":
                    stats["ft_pct"] = round(val * 100, 1)
                elif name == "freeThrowsMade":
                    stats["ft_made"] = round(val, 1)
                elif name == "freeThrowsAttempted":
                    stats["ft_att"] = round(val, 1)
                elif name == "fieldGoalsAttempted":
                    fga = val
                elif name == "opponentThreePointFieldGoalPct":
                    stats["opp_fg3_pct"] = round(val * 100, 1)

        # FT rate = FTA/FGA — frequency of getting to the line, not just making them
        if "ft_att" in stats and fga and fga > 0:
            stats["ft_rate"] = round(stats["ft_att"] / fga, 3)

        return stats if stats else None

    except requests.RequestException as e:
        print(f"    Request failed for {team_name}: {e}")
        return None

# ── Step 5: Write to DB ───────────────────────────────────────────────────────

def update_team_shooting(team_id, stats):
    """Update shooting columns on the teams table row for this team_id."""
    db = get_db()
    cursor = db.cursor()

    column_map = {
        "fg3_pct":    "fg3_pct",
        "fg3_made":   "fg3_made",
        "fg3_att":    "fg3_att",
        "ft_pct":     "ft_pct",
        "ft_made":    "ft_made",
        "ft_att":     "ft_att",
        "opp_fg3_pct":"opp_fg3_pct",
        "ft_rate":    "ft_rate",
    }

    set_clauses = []
    values = []

    for stat_key, col_name in column_map.items():
        if stat_key in stats:
            set_clauses.append(f"{col_name} = ?")
            values.append(stats[stat_key])

    if not set_clauses:
        return

    set_clauses.append("shooting_updated_at = datetime('now')")
    values.append(team_id)

    sql = f"UPDATE teams SET {', '.join(set_clauses)} WHERE team_id = ?"

    try:
        cursor.execute(sql, values)
        db.commit()
    except Exception as e:
        print(f"    DB update failed for team_id={team_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass

# ── Main ──────────────────────────────────────────────────────────────────────

def fetch_shooting_stats():
    print("\n" + "=" * 60)
    print("Fetching ESPN Shooting Statistics")
    print("=" * 60)

    add_shooting_columns()

    # Get our teams from DB
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT team_id, name FROM teams WHERE team_id IS NOT NULL")
    db_teams = [{"team_id": r[0], "name": r[1]} for r in cursor.fetchall()]

    if not db_teams:
        print("No teams found in DB.")
        return False

    print(f"  DB teams: {len(db_teams)}")

    # Fetch ESPN's team list to get ESPN's internal IDs
    espn_teams = fetch_espn_team_list()
    if not espn_teams:
        print("Failed to fetch ESPN team list — aborting.")
        return False

    # Match our teams to ESPN teams by name
    matched_teams = match_to_espn(db_teams, espn_teams)
    if not matched_teams:
        print("No teams matched — aborting.")
        return False

    # Fetch stats for each matched team
    updated = 0
    skipped = 0

    for i, team in enumerate(matched_teams, 1):
        stats = fetch_team_shooting(team["espn_id"], team["name"])
        time.sleep(REQUEST_DELAY)

        if not stats:
            skipped += 1
            continue

        update_team_shooting(team["team_id"], stats)
        updated += 1

        if i % 50 == 0 or i == len(matched_teams):
            print(f"  [{i}/{len(matched_teams)}] — {updated} updated, {skipped} skipped")

    print(f"\n{'=' * 60}")
    print(f"Complete: {updated} updated, {skipped} skipped")
    print(f"{'=' * 60}\n")

    return updated > 0


if __name__ == "__main__":
    success = fetch_shooting_stats()
    sys.exit(0 if success else 1)