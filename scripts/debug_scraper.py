import requests
from bs4 import BeautifulSoup

WARRENNOLAN_URL = "https://www.warrennolan.com/basketball/2026/net"

print("Fetching page...")
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
response = requests.get(WARRENNOLAN_URL, headers=headers, timeout=30)

print(f"Status code: {response.status_code}")
print(f"Content length: {len(response.content)} bytes")

soup = BeautifulSoup(response.content, 'html.parser')

# Find all tables
tables = soup.find_all('table')
print(f"\nFound {len(tables)} tables on the page")

for i, table in enumerate(tables):
    print(f"\n--- Table {i+1} ---")
    rows = table.find_all('tr')
    print(f"Rows: {len(rows)}")
    
    if rows:
        # Show first few rows
        for j, row in enumerate(rows[:3]):
            cells = row.find_all(['td', 'th'])
            cell_text = [cell.get_text(strip=True) for cell in cells]
            print(f"Row {j+1}: {cell_text}")

# Also check for divs or other structures
print("\n--- Looking for other structures ---")
divs_with_class = soup.find_all('div', class_=True)
print(f"Found {len(divs_with_class)} divs with classes")

# Check if data might be in a specific div
data_containers = soup.find_all(['div', 'section'], {'id': True})
print(f"Found {len(data_containers)} elements with IDs")
for container in data_containers[:5]:
    print(f"  ID: {container.get('id')}")
