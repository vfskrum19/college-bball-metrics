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
from datetime import datetime
from difflib import SequenceMatcher

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.db import get_db, execute, commit

# ── Constants ─────────────────────────────────────────────────────────────────

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams"
ESPN_STATS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{espn_id}/statistics"

REQUEST_DELAY   = 0.35  # seconds between requests — be polite to ESPN's servers
REQUEST_TIMEOUT = 10    # seconds before giving up on a single request

# Manual overrides for teams whose names differ too much for fuzzy matching.
# Key = KenPom name, Value = ESPN displayName (exact).
# Add entries here if you see a team in the unmatched output at the end.
MANUAL_MAPPINGS = {
    # ── Confirmed from ESPN debug output (exact displayName including mascot) ──
    "Appalachian St.":       "App State Mountaineers",
    "LIU":                   "Long Island University Sharks",
    "Louisiana Monroe":      "Louisiana Monroe Warhawks",
    "Massachusetts":         "Massachusetts Minutemen",
    "Northern Arizona":      "Northern Arizona Lumberjacks",
    "Pittsburgh":            "Pittsburgh Panthers",
    "Purdue Fort Wayne":     "Purdue Fort Wayne Mastodons",
    "Southern Illinois":     "Southern Illinois Salukis",
    "Ball St.":              "Ball State Cardinals",
    "Bethune Cookman":       "Bethune-Cookman Wildcats",
    "Boston University":     "Boston University Terriers",
    "Cal St. Bakersfield":   "Cal State Bakersfield Roadrunners",
    "Cal St. Fullerton":     "Cal State Fullerton Titans",
    "Central Connecticut":   "Central Connecticut Blue Devils",
    "Central Michigan":      "Central Michigan Chippewas",
    "Charleston Southern":   "Charleston Southern Buccaneers",
    "CSUN":                  "Cal State Northridge Matadors",
    "East Tennessee St.":    "East Tennessee State Buccaneers",
    "Eastern Illinois":      "Eastern Illinois Panthers",
    "Eastern Kentucky":      "Eastern Kentucky Colonels",
    "Eastern Michigan":      "Eastern Michigan Eagles",
    "Eastern Washington":    "Eastern Washington Eagles",
    "Fairleigh Dickinson":   "Fairleigh Dickinson Knights",
    "Florida Atlantic":      "Florida Atlantic Owls",
    "Florida Gulf Coast":    "Florida Gulf Coast Eagles",
    "Florida International": "Florida International Panthers",
    "Ga. Southern":          "Georgia Southern Eagles",
    "Ga. Tech":              "Georgia Tech Yellow Jackets",
    "Gardner Webb":          "Gardner-Webb Runnin' Bulldogs",
    "Gardner-Webb":          "Gardner-Webb Runnin' Bulldogs",
    "Illinois Chicago":      "UIC Flames",
    "IU Indy":               "IU Indianapolis Jaguars",
    "Long Island":           "Long Island University Sharks",
    "Louisiana Monroe":      "Louisiana Monroe Warhawks",
    "Loyola Chicago":        "Loyola Chicago Ramblers",
    "Loyola MD":             "Loyola Maryland Greyhounds",
    "McNeese St.":           "McNeese Cowboys",
    "Miami FL":              "Miami Hurricanes",
    "Miami OH":              "Miami (OH) RedHawks",
    "Middle Tennessee":      "Middle Tennessee Blue Raiders",
    "Mississippi":           "Ole Miss Rebels",
    "Nebraska Omaha":        "Omaha Mavericks",
    "Northern Illinois":     "Northern Illinois Huskies",
    "Northwestern St.":      "Northwestern State Demons",
    "Penn":                  "Pennsylvania Quakers",
    "SE Missouri St.":       "Southeast Missouri State Redhawks",
    "SIUE":                  "SIU Edwardsville Cougars",
    "Siu Edwardsville":      "SIU Edwardsville Cougars",
    "South Carolina St.":    "South Carolina State Bulldogs",
    "Southeast Missouri":    "Southeast Missouri State Redhawks",
    "Stephen F. Austin":     "Stephen F. Austin Lumberjacks",
    "Stony Brook":           "Stony Brook Seawolves",
    "Tennessee Martin":      "UT Martin Skyhawks",
    "Tennessee Tech":        "Tennessee Tech Golden Eagles",
    "Tennessee St.":         "Tennessee State Tigers",
    "Texas A&M Corpus Chris":"Texas A&M-Corpus Christi Islanders",
    # ── St./State schools (fuzzy usually catches these but explicit is safer) ─
    "Arkansas St.":          "Arkansas State Red Wolves",
    "Boise St.":             "Boise State Broncos",
    "Colorado St.":          "Colorado State Rams",
    "Florida St.":           "Florida State Seminoles",
    "Fresno St.":            "Fresno State Bulldogs",
    "Idaho St.":             "Idaho State Bengals",
    "Illinois St.":          "Illinois State Redbirds",
    "Indiana St.":           "Indiana State Sycamores",
    "Iowa St.":              "Iowa State Cyclones",
    "Jacksonville St.":      "Jacksonville State Gamecocks",
    "Kansas St.":            "Kansas State Wildcats",
    "Kennesaw St.":          "Kennesaw State Owls",
    "Kent St.":              "Kent State Golden Flashes",
    "Michigan St.":          "Michigan State Spartans",
    "Mississippi St.":       "Mississippi State Bulldogs",
    "Missouri St.":          "Missouri State Bears",
    "Montana St.":           "Montana State Bobcats",
    "Morehead St.":          "Morehead State Eagles",
    "Murray St.":            "Murray State Racers",
    "NC St.":                "NC State Wolfpack",
    "New Mexico St.":        "New Mexico State Aggies",
    "Ohio St.":              "Ohio State Buckeyes",
    "Oklahoma St.":          "Oklahoma State Cowboys",
    "Oregon St.":            "Oregon State Beavers",
    "Penn St.":              "Penn State Nittany Lions",
    "Sacramento St.":        "Sacramento State Hornets",
    "Sam Houston St.":       "Sam Houston Bearkats",
    "Sam Houston":           "Sam Houston Bearkats",
    "San Diego St.":         "San Diego State Aztecs",
    "San Jose St.":          "San José State Spartans",
    "South Dakota St.":      "South Dakota State Jackrabbits",
    "Texas St.":             "Texas State Bobcats",
    "Utah St.":              "Utah State Aggies",
    "Washington St.":        "Washington State Cougars",
    "Weber St.":             "Weber State Wildcats",
    "Wichita St.":           "Wichita State Shockers",
    "Wright St.":            "Wright State Raiders",
    "Youngstown St.":        "Youngstown State Penguins",
    "North Dakota St.":      "North Dakota State Bison",
    # ── Cal system ───────────────────────────────────────────────────────────
    "Cal Baptist":           "California Baptist Lancers",
    "Cal St. Northridge":    "Cal State Northridge Matadors",
    "Long Beach St.":        "Long Beach State Beach",
    # ── Other confirmed mismatches ────────────────────────────────────────────
    "Col. of Charleston":    "Charleston Cougars",
    "Connecticut":           "UConn Huskies",
    "Grambling St.":         "Grambling Tigers",
    "Hawaii":                "Hawai'i Rainbow Warriors",
    "Jackson St.":           "Jackson State Tigers",
    "Mississippi Valley St.":"Mississippi Valley State Delta Devils",
    "Nicholls St.":          "Nicholls Colonels",
    "Queens":                "Queens University Royals",
    "Southeastern Louisiana":"SE Louisiana Lions",
    "St. Thomas":            "St. Thomas (MN) Tommies",
    "Albany":                "UAlbany Great Danes",
    "Tarleton St.":          "Tarleton State Texans",
    "Tarleton":              "Tarleton State Texans",
    "UC Davis":              "UC Davis Aggies",
    "UMass Lowell":          "UMass Lowell River Hawks",
    "USC Upstate":           "South Carolina Upstate Spartans",
    "UT Arlington":          "UT Arlington Mavericks",
    "UT Rio Grande Valley":  "UT Rio Grande Valley Vaqueros",
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
        ("fg3_rate",            "REAL"),
        ("ft_pct",              "REAL"),
        ("ft_made",             "REAL"),
        ("ft_att",              "REAL"),
        ("opp_fg3_pct",         "REAL"),
        ("ft_rate",             "REAL"),
        ("shooting_updated_at", "TEXT"),
    ]

    # IF NOT EXISTS lets PostgreSQL handle the "already exists" case without
    # a bare except that silently swallows real errors (bad perms, typos, etc.)
    for col_name, col_type in new_columns:
        cursor.execute(
            f"ALTER TABLE teams ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
        )

    db.commit()
    print(f"[OK] Shooting stat columns ready — {len(new_columns)} columns verified in schema")

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

        # ESPN's response structure varies — try all known paths
        categories = (
            data.get("results", {}).get("stats", {}).get("categories")
            or data.get("stats", {}).get("categories")
            or []
        )

        for category in categories:
            for stat in category.get("stats", []):
                name  = stat.get("name", "")
                value = stat.get("value")
                if value is None:
                    continue
                try:
                    val = float(value)
                except (TypeError, ValueError):
                    continue

                # ESPN returns percentages already as percentages (e.g. 32.5 not 0.325)
                if name == "threePointFieldGoalPct":
                    stats["fg3_pct"] = round(val, 1)
                elif name == "threePointFieldGoalsMade":
                    stats["fg3_made"] = round(val, 1)
                elif name == "threePointFieldGoalsAttempted":
                    stats["fg3_att"] = round(val, 1)
                elif name == "freeThrowPct":
                    stats["ft_pct"] = round(val, 1)
                elif name == "freeThrowsMade":
                    stats["ft_made"] = round(val, 1)
                elif name == "freeThrowsAttempted":
                    stats["ft_att"] = round(val, 1)
                elif name == "fieldGoalsAttempted":
                    fga = val
                elif name == "opponentThreePointFieldGoalPct":
                    stats["opp_fg3_pct"] = round(val, 1)

        # FT rate = FTA/FGA — how often they get to the line
        if "ft_att" in stats and fga and fga > 0:
            stats["ft_rate"] = round(stats["ft_att"] / fga, 3)

        # 3PA rate = 3PA/FGA — how often they shoot threes (shot profile)
        if "fg3_att" in stats and fga and fga > 0:
            stats["fg3_rate"] = round(stats["fg3_att"] / fga, 3)

        return stats if stats else None

    except requests.RequestException as e:
        print(f"    Request failed for {team_name}: {e}")
        return None

# ── Step 5: Write to DB ───────────────────────────────────────────────────────

def update_team_shooting(team_id, stats):
    """Update shooting columns on the teams table row for this team_id."""
    db = get_db()

    column_map = {
        "fg3_pct":     "fg3_pct",
        "fg3_made":    "fg3_made",
        "fg3_att":     "fg3_att",
        "fg3_rate":    "fg3_rate",
        "ft_pct":      "ft_pct",
        "ft_made":     "ft_made",
        "ft_att":      "ft_att",
        "opp_fg3_pct": "opp_fg3_pct",
        "ft_rate":     "ft_rate",
    }

    set_clauses = []
    values = []

    for stat_key, col_name in column_map.items():
        if stat_key in stats:
            set_clauses.append(f"{col_name} = ?")
            values.append(stats[stat_key])

    if not set_clauses:
        return

    set_clauses.append("shooting_updated_at = ?")
    values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    values.append(team_id)

    sql = f"UPDATE teams SET {', '.join(set_clauses)} WHERE team_id = ?"

    try:
        execute(db, sql, values)
        commit(db)
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

        # Print progress every 25 teams so cron logs show it's alive
        if i % 25 == 0 or i == len(matched_teams):
            pct = i / len(matched_teams) * 100
            print(f"  [{i}/{len(matched_teams)}] {pct:.0f}% — {updated} updated, {skipped} skipped")

    print(f"\n{'=' * 60}")
    print(f"Complete: {updated} updated, {skipped} skipped")
    print(f"{'=' * 60}\n")

    return updated > 0


if __name__ == "__main__":
    success = fetch_shooting_stats()
    sys.exit(0 if success else 1)