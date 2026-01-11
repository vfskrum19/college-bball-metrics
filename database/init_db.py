import sqlite3

import os
from pathlib import Path

# Get the directory where this script is located (database/)
SCRIPT_DIR = Path(__file__).parent
DATABASE = SCRIPT_DIR / 'kenpom.db'

def init_db():
    """Initialize database with all required tables"""
    print("Initializing database...")
    
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    
    # Teams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            conference TEXT,
            coach TEXT,
            arena TEXT,
            arena_city TEXT,
            arena_state TEXT,
            season INTEGER,
            primary_color TEXT,
            secondary_color TEXT,
            logo_url TEXT
        )
    ''')
    
    # Ratings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            data_through TEXT,
            wins INTEGER,
            losses INTEGER,
            adj_em REAL,
            rank_adj_em INTEGER,
            adj_oe REAL,
            rank_adj_oe INTEGER,
            adj_de REAL,
            rank_adj_de INTEGER,
            tempo REAL,
            rank_tempo INTEGER,
            adj_tempo REAL,
            rank_adj_tempo INTEGER,
            luck REAL,
            rank_luck INTEGER,
            sos REAL,
            rank_sos INTEGER,
            ncsos REAL,
            rank_ncsos INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Four factors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS four_factors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            data_through TEXT,
            efg_pct REAL,
            rank_efg_pct INTEGER,
            to_pct REAL,
            rank_to_pct INTEGER,
            or_pct REAL,
            rank_or_pct INTEGER,
            ft_rate REAL,
            rank_ft_rate INTEGER,
            defg_pct REAL,
            rank_defg_pct INTEGER,
            dto_pct REAL,
            rank_dto_pct INTEGER,
            dor_pct REAL,
            rank_dor_pct INTEGER,
            dft_rate REAL,
            rank_dft_rate INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Ratings archive table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            archive_date TEXT,
            is_preseason INTEGER,
            adj_em REAL,
            rank_adj_em INTEGER,
            adj_oe REAL,
            rank_adj_oe INTEGER,
            adj_de REAL,
            rank_adj_de INTEGER,
            adj_tempo REAL,
            rank_adj_tempo INTEGER,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    db.commit()
    db.close()
    
    print("✓ Database initialized successfully!")

if __name__ == '__main__':
    init_db()
