import requests

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

# Feb 4
params = {'dates': '20260204', 'groups': 50, 'limit': 400}
response = requests.get(ESPN_URL, params=params, timeout=15)
data = response.json()

print("Feb 4 games involving New Mexico, Utah St, or Boise St:")
for event in data.get('events', []):
    comp = event.get('competitions', [{}])[0]
    competitors = comp.get('competitors', [])
    if len(competitors) == 2:
        home = competitors[0] if competitors[0].get('homeAway') == 'home' else competitors[1]
        away = competitors[1] if competitors[0].get('homeAway') == 'home' else competitors[0]
        home_name = home.get('team', {}).get('displayName', '')
        away_name = away.get('team', {}).get('displayName', '')
        home_score = home.get('score', 'N/A')
        away_score = away.get('score', 'N/A')
        
        if 'new mexico' in home_name.lower() or 'utah' in home_name.lower() or 'new mexico' in away_name.lower() or 'utah' in away_name.lower():
            print(f"  {home_name} {home_score} vs {away_name} {away_score}")

print("\nFeb 7 games involving New Mexico or Boise St:")
params = {'dates': '20260207', 'groups': 50, 'limit': 400}
response = requests.get(ESPN_URL, params=params, timeout=15)
data = response.json()

for event in data.get('events', []):
    comp = event.get('competitions', [{}])[0]
    competitors = comp.get('competitors', [])
    if len(competitors) == 2:
        home = competitors[0] if competitors[0].get('homeAway') == 'home' else competitors[1]
        away = competitors[1] if competitors[0].get('homeAway') == 'home' else competitors[0]
        home_name = home.get('team', {}).get('displayName', '')
        away_name = away.get('team', {}).get('displayName', '')
        home_score = home.get('score', 'N/A')
        away_score = away.get('score', 'N/A')
        
        if 'new mexico' in home_name.lower() or 'boise' in home_name.lower() or 'new mexico' in away_name.lower() or 'boise' in away_name.lower():
            print(f"  {home_name} {home_score} vs {away_name} {away_score}")