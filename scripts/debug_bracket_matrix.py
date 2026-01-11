import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BRACKET_MATRIX_URL = "https://www.bracketmatrix.com"

print("Fetching Bracket Matrix...")
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
response = requests.get(BRACKET_MATRIX_URL, headers=headers, timeout=30, verify=False)
soup = BeautifulSoup(response.content, 'html.parser')

print("\n=== TABLES FOUND ===")
tables = soup.find_all('table')
print(f"Total tables: {len(tables)}")

for idx, table in enumerate(tables, 1):
    print(f"\n--- TABLE {idx} ---")
    
    # Check for headers
    headers = table.find_all('th')
    if headers:
        print(f"Headers ({len(headers)}): {[h.get_text(strip=True) for h in headers[:10]]}")
    
    # Check rows
    rows = table.find_all('tr')
    print(f"Total rows: {len(rows)}")
    
    # Show first 3 data rows
    print("Sample rows:")
    for row_idx, row in enumerate(rows[:5], 1):
        cells = row.find_all(['td', 'th'])
        cell_data = [c.get_text(strip=True) for c in cells[:8]]
        print(f"  Row {row_idx}: {cell_data}")
    
    # Check table attributes
    if table.get('class'):
        print(f"Table classes: {table.get('class')}")
    if table.get('id'):
        print(f"Table ID: {table.get('id')}")

print("\n=== OTHER ELEMENTS ===")
# Look for divs that might contain bracket data
divs_with_class = soup.find_all('div', class_=True)
print(f"Divs with classes: {len(divs_with_class)}")

# Look for team names in any element
all_text = soup.get_text()
if 'Duke' in all_text or 'Kentucky' in all_text or 'Kansas' in all_text:
    print("✓ Found common team names in page text")
else:
    print("⚠️ No common team names found")

print("\nSaving HTML to file for inspection...")
with open('bracket_matrix_debug.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())
print("✓ Saved to bracket_matrix_debug.html")
