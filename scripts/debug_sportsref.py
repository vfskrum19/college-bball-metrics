"""
Debug script to check Sports Reference table structure
"""
import requests
from bs4 import BeautifulSoup

url = 'https://www.sports-reference.com/cbb/schools/arizona/men/2026.html'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print(f"Fetching {url}...")
response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

soup = BeautifulSoup(response.content, 'html.parser')

# Find all tables
tables = soup.find_all('table')
print(f"\nFound {len(tables)} tables:")
for t in tables:
    table_id = t.get('id', 'no-id')
    print(f"  - {table_id}")

# Check each table for player data
for t in tables:
    table_id = t.get('id', 'no-id')
    tbody = t.find('tbody')
    
    if tbody:
        rows = tbody.find_all('tr')
        if rows:
            print(f"\n=== Table: {table_id} ({len(rows)} rows) ===")
            
            # Show first row structure
            first_row = rows[0]
            cells = first_row.find_all(['td', 'th'])
            
            print("First row columns:")
            for cell in cells:
                stat = cell.get('data-stat', 'no-stat')
                value = cell.get_text(strip=True)
                print(f"  {stat}: '{value}'")
            
            # Only show first 2 tables in detail
            if table_id in ['roster', 'per_game', 'totals', 'per_poss', 'advanced']:
                print("\nFirst 3 players:")
                for row in rows[:3]:
                    player_cell = row.find(['td', 'th'], {'data-stat': 'player'})
                    if player_cell:
                        print(f"  - {player_cell.get_text(strip=True)}")
