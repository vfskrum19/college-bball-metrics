"""
debug_espn_names.py

Run this to see what ESPN actually calls the teams that aren't matching.
This prints every ESPN team name that fuzzy-matches our unmatched KenPom names
at any similarity score, so we can see what the real ESPN display name is.

Run from project root:
    python scrapers/debug_espn_names.py
"""

import sys
import os
import requests
from difflib import SequenceMatcher

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams"

# The 46 teams that didn't match last run
UNMATCHED = [
    "Appalachian St.", "Lindenwood", "LIU", "Louisiana Monroe",
    "Massachusetts", "Northern Arizona", "Pittsburgh", "Purdue Fort Wayne",
    "Queens", "Southern Illinois",
    # 5 more not shown in output — add if you know them, otherwise run to discover
]

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# Fetch ESPN team list
print("Fetching ESPN team list...")
response = requests.get(ESPN_TEAMS_URL, params={"limit": 1000}, timeout=10)
data = response.json()

espn_teams = []
for entry in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
    team = entry.get("team", {})
    espn_id = team.get("id")
    name = team.get("displayName", "")
    short = team.get("shortDisplayName", "")
    espn_teams.append({"espn_id": espn_id, "name": name, "short": short})

print(f"Got {len(espn_teams)} ESPN teams\n")
print("=" * 70)

# For each unmatched team, show top 3 ESPN candidates by similarity
for kp_name in UNMATCHED:
    scored = []
    for t in espn_teams:
        score = max(
            similarity(kp_name, t["name"]),
            similarity(kp_name, t["short"]),
        )
        scored.append((score, t["name"], t["espn_id"]))
    scored.sort(reverse=True)

    top = scored[:3]
    print(f"KenPom: '{kp_name}'")
    for score, espn_name, eid in top:
        print(f"  {score:.2f}  '{espn_name}'  (id={eid})")
    print()