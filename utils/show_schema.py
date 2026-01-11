#!/usr/bin/env python3
"""
Show all tables in the database
"""
import os
from pathlib import Path
import sqlite3

# Get project root (parent of this file's directory)
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

def show_schema():
    """Display database schema"""
    db = sqlite3.connect(DATABASE)
    
    print("="*70)
    print("DATABASE TABLES")
    print("="*70)
    
    tables = db.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """).fetchall()
    
    print("\nTables found:")
    for table in tables:
        table_name = table[0]
        count = db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"  - {table_name:30s} ({count} rows)")
    
    print("\n" + "="*70)
    print("TEAMS TABLE STRUCTURE")
    print("="*70)
    
    columns = db.execute("PRAGMA table_info(teams)").fetchall()
    print("\nColumns in 'teams' table:")
    for col in columns:
        print(f"  - {col[1]:20s} {col[2]}")
    
    db.close()

if __name__ == '__main__':
    show_schema()
