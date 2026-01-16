"""
Database migration to add player tables
Run this once to add player support to existing database
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

def migrate():
    """Add player tables to database"""
    print("Adding player tables to database...")
    
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    
    # Players table - basic info
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY,
            team_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            position TEXT,
            jersey_number INTEGER,
            height TEXT,
            year TEXT,
            headshot_url TEXT,
            season INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    ''')
    print("✓ Created players table")
    
    # Player stats table - KenPom metrics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            games_played INTEGER,
            minutes_pct REAL,
            ortg REAL,
            usage_rate REAL,
            efg_pct REAL,
            ts_pct REAL,
            or_pct REAL,
            dr_pct REAL,
            ast_rate REAL,
            to_rate REAL,
            blk_rate REAL,
            stl_rate REAL,
            ft_rate REAL,
            ppg REAL,
            rpg REAL,
            apg REAL,
            fg_pct REAL,
            three_pct REAL,
            ft_pct REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players(player_id),
            FOREIGN KEY (team_id) REFERENCES teams(team_id),
            UNIQUE(player_id, season)
        )
    ''')
    print("✓ Created player_stats table")
    
    # Team roles table - star, x_factor, contributor
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('star', 'x_factor', 'contributor')),
            role_reason TEXT,
            display_order INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(team_id),
            FOREIGN KEY (player_id) REFERENCES players(player_id),
            UNIQUE(team_id, player_id, season)
        )
    ''')
    print("✓ Created team_roles table")
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id, season)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_team ON player_stats(team_id, season)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_team_roles_team ON team_roles(team_id, season)')
    print("✓ Created indexes")
    
    db.commit()
    db.close()
    
    print("\n✓ Migration complete! Player tables added to database.")

if __name__ == '__main__':
    migrate()
