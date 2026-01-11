#!/usr/bin/env python3
"""
Test parsing the saved Bracket Matrix HTML
"""
import sys
from bs4 import BeautifulSoup

def parse_bracket_matrix_html(html_file):
    """Parse saved Bracket Matrix HTML file"""
    print(f"Reading HTML from {html_file}...")
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables")
    
    bracket_teams = []
    
    for table_idx, table in enumerate(tables):
        rows = table.find_all('tr')
        if len(rows) < 4:
            continue
        
        print(f"\nProcessing table {table_idx + 1} with {len(rows)} rows")
        
        # Skip first 3 rows (headers and empty row)
        for row_idx, row in enumerate(rows[3:], start=4):
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 3:
                seed_text = cells[0].get_text(strip=True)
                team_text = cells[1].get_text(strip=True)
                conference_text = cells[2].get_text(strip=True)
                
                try:
                    seed = int(seed_text)
                    if 1 <= seed <= 16 and team_text and len(team_text) > 2:
                        bracket_teams.append({
                            'team_name': team_text,
                            'seed': seed,
                            'conference': conference_text
                        })
                        print(f"  Row {row_idx}: Seed {seed} - {team_text} ({conference_text})")
                except (ValueError, TypeError):
                    continue
    
    print(f"\n✓ Parsed {len(bracket_teams)} teams total")
    
    # Show summary by seed
    from collections import defaultdict
    by_seed = defaultdict(list)
    for team in bracket_teams:
        by_seed[team['seed']].append(team['team_name'])
    
    print("\n=== TEAMS BY SEED LINE ===")
    for seed in sorted(by_seed.keys()):
        teams = by_seed[seed]
        print(f"Seed {seed}: {len(teams)} teams - {', '.join(teams)}")
    
    return bracket_teams

if __name__ == '__main__':
    html_file = 'bracket_matrix_debug.html'
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
    
    teams = parse_bracket_matrix_html(html_file)
    print(f"\n{'='*60}")
    print(f"Total teams scraped: {len(teams)}")
    print(f"Expected: 68 teams (4 seeds × 16 + 4 play-in seeds)")
    print(f"{'='*60}")