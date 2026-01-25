"""
Add advanced stats columns to player_stats table
Run this once before running the updated scraper
"""
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

def add_advanced_columns():
    """Add advanced stats columns to player_stats table"""
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    
    # New columns to add
    new_columns = [
        ('usage_pct', 'REAL'),      # Usage rate - % of team plays used
        ('ortg', 'REAL'),           # Offensive rating - points per 100 possessions
        ('drtg', 'REAL'),           # Defensive rating
        ('bpm', 'REAL'),            # Box Plus/Minus
        ('obpm', 'REAL'),           # Offensive BPM
        ('dbpm', 'REAL'),           # Defensive BPM
        ('ws', 'REAL'),             # Win Shares
        ('ws_40', 'REAL'),          # Win Shares per 40 minutes
        ('ast_pct', 'REAL'),        # Assist percentage
        ('tov_pct', 'REAL'),        # Turnover percentage
        ('orb_pct', 'REAL'),        # Offensive rebound percentage
        ('drb_pct', 'REAL'),        # Defensive rebound percentage
        ('stl_pct', 'REAL'),        # Steal percentage
        ('blk_pct', 'REAL'),        # Block percentage
        ('per', 'REAL'),            # Player Efficiency Rating
        ('ts_pct', 'REAL'),         # True Shooting %
    ]
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(player_stats)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # Add missing columns
    added = 0
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE player_stats ADD COLUMN {col_name} {col_type}")
                print(f"  Added: {col_name}")
                added += 1
            except sqlite3.OperationalError as e:
                print(f"  Skipped {col_name}: {e}")
        else:
            print(f"  Exists: {col_name}")
    
    db.commit()
    db.close()
    
    print(f"\n✓ Added {added} new columns to player_stats")

if __name__ == '__main__':
    print("Adding advanced stats columns to player_stats table...\n")
    add_advanced_columns()
