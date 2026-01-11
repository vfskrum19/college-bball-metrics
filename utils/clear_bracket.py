#!/usr/bin/env python3
"""
Clear bracket and matchups tables and re-import
"""
import os
from pathlib import Path
import sqlite3

# Get project root (parent of this file's directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

def clear_bracket():
    """Clear existing bracket data"""
    db = sqlite3.connect(DATABASE)
    
    print("Clearing existing bracket data...")
    db.execute("DELETE FROM matchups WHERE season = 2026")
    db.execute("DELETE FROM bracket WHERE season = 2026")
    db.commit()
    
    print("✓ Bracket data cleared")
    
    db.close()

if __name__ == '__main__':
    clear_bracket()
    print("\nNow run: python import_bracket_matrix.py")
