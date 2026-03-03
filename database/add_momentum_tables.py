"""
Database migration for Momentum Tracker feature
Creates tables for:
- games: Individual game results with KenPom predictions
- momentum_ratings: Historical snapshots of team ratings
- momentum_cache: Pre-calculated momentum scores

Run from project root:
    python database/migrations/add_momentum_tables.py
"""

import sqlite3
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

def run_migration():
    print(f"\n{'='*60}")
    print("Momentum Tracker Database Migration")
    print(f"{'='*60}\n")
    
    if not DATABASE.exists():
        print(f"❌ Database not found at {DATABASE}")
        return False
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # =========================================================
    # Table 1: games
    # Stores individual game results with KenPom predictions
    # =========================================================
    print("Creating 'games' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER UNIQUE,
            season INTEGER NOT NULL,
            game_date DATE NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            home_pred REAL,
            away_pred REAL,
            home_win_prob REAL,
            pred_tempo REAL,
            home_rank INTEGER,
            away_rank INTEGER,
            thrill_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (home_team_id) REFERENCES teams (team_id),
            FOREIGN KEY (away_team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Create indexes for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_games_date ON games (game_date)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_games_home_team ON games (home_team_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_games_away_team ON games (away_team_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_games_season ON games (season)
    ''')
    print("✓ 'games' table created")
    
    # =========================================================
    # Table 2: momentum_ratings
    # Historical snapshots of team ratings for trajectory tracking
    # =========================================================
    print("Creating 'momentum_ratings' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS momentum_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            snapshot_date DATE NOT NULL,
            season INTEGER NOT NULL,
            rank_adj_em INTEGER,
            adj_em REAL,
            adj_oe REAL,
            adj_de REAL,
            rank_adj_oe INTEGER,
            rank_adj_de INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, snapshot_date),
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Create indexes
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_momentum_ratings_team ON momentum_ratings (team_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_momentum_ratings_date ON momentum_ratings (snapshot_date)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_momentum_ratings_season ON momentum_ratings (season)
    ''')
    print("✓ 'momentum_ratings' table created")
    
    # =========================================================
    # Table 3: momentum_cache
    # Pre-calculated momentum scores (refreshed daily)
    # =========================================================
    print("Creating 'momentum_cache' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS momentum_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Last 10 games record
            games_played_l10 INTEGER DEFAULT 0,
            wins_l10 INTEGER DEFAULT 0,
            losses_l10 INTEGER DEFAULT 0,
            
            -- Streaks
            win_streak INTEGER DEFAULT 0,
            loss_streak INTEGER DEFAULT 0,
            
            -- Performance metrics
            avg_margin_l10 REAL,
            avg_vs_expected_l10 REAL,
            best_win_margin INTEGER,
            worst_loss_margin INTEGER,
            
            -- Rating trajectory
            rank_change_l10 INTEGER,
            adj_em_change_l10 REAL,
            rank_start_l10 INTEGER,
            rank_current INTEGER,
            adj_em_start_l10 REAL,
            adj_em_current REAL,
            
            -- Composite score
            momentum_score REAL,
            trend_direction TEXT CHECK(trend_direction IN ('hot', 'cold', 'stable', 'rising', 'falling')),
            
            -- Additional context
            last_game_date DATE,
            games_data TEXT,  -- JSON array of last 10 games for detailed view
            
            UNIQUE(team_id, season),
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Create indexes
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_momentum_cache_team ON momentum_cache (team_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_momentum_cache_score ON momentum_cache (momentum_score DESC)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_momentum_cache_season ON momentum_cache (season)
    ''')
    print("✓ 'momentum_cache' table created")
    
    # =========================================================
    # Commit and verify
    # =========================================================
    conn.commit()
    
    # Verify tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n{'='*60}")
    print("Migration complete! Current tables:")
    print(f"{'='*60}")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  • {table}: {count} rows")
    
    conn.close()
    print(f"\n✓ Database ready for momentum tracking!\n")
    return True

def rollback_migration():
    """Remove momentum tables (use with caution)"""
    print("Rolling back momentum tables...")
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS momentum_cache")
    cursor.execute("DROP TABLE IF EXISTS momentum_ratings")
    cursor.execute("DROP TABLE IF EXISTS games")
    
    conn.commit()
    conn.close()
    print("✓ Momentum tables removed")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        confirm = input("This will DELETE all momentum data. Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            rollback_migration()
        else:
            print("Rollback cancelled")
    else:
        run_migration()
