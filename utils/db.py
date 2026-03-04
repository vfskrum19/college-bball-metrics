"""
utils/db.py - Shared database connection for all scrapers

WHY THIS EXISTS:
    Every scraper needs a database connection. Rather than duplicating
    the SQLite/PostgreSQL switching logic in every file, we put it here
    once. Any scraper that needs the database does:

        from utils.db import get_db, query, execute, close_db

    This also means if we ever change databases again, there's exactly
    one file to update.

USAGE IN SCRAPERS:
    from utils.db import get_db, close_db, execute, executemany

    # Get a connection
    db = get_db()

    # Run a query (returns list of dict-like rows)
    rows = db.execute('SELECT * FROM teams WHERE season = ?', (2026,)).fetchall()

    # For PostgreSQL compatibility, use the helpers:
    execute(db, 'INSERT INTO teams VALUES (?, ?, ?)', (1, 'Duke', 'ACC'))

    # Always close when done
    close_db(db)
"""

import os
import sqlite3
from pathlib import Path

# Load .env if available (local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get('DATABASE_URL')

# Fix Railway's postgres:// prefix
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

USE_POSTGRES = DATABASE_URL is not None

# SQLite fallback path
PROJECT_ROOT = Path(__file__).parent.parent
SQLITE_PATH = PROJECT_ROOT / 'database' / 'kenpom.db'


def get_db():
    """
    Get a database connection.
    Returns PostgreSQL connection if DATABASE_URL is set, SQLite otherwise.
    Both return connections whose cursors support dict-like row access.
    """
    if USE_POSTGRES:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            raise ImportError(
                "psycopg2 not installed. Run: pip install psycopg2-binary"
            )
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect(str(SQLITE_PATH))
        conn.row_factory = sqlite3.Row
        return conn


def close_db(conn):
    """Close a database connection."""
    if conn:
        conn.close()


def get_cursor(conn):
    """
    Get a cursor that returns dict-like rows for both SQLite and PostgreSQL.
    """
    if USE_POSTGRES:
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        return conn.cursor()


def _pg_sql(sql):
    """
    Convert SQLite SQL to PostgreSQL-compatible SQL.

    Handles:
    1. ? placeholders       →  %s
    2. date('now')          →  CURRENT_DATE
    3. game_date < CURRENT_DATE  →  game_date::date < CURRENT_DATE
       (game_date is TEXT; PostgreSQL won't compare text to date implicitly)
    4. AUTOINCREMENT        →  (removed — PostgreSQL uses SERIAL which is
                                declared in the column type, not a keyword)
    5. INTEGER PRIMARY KEY AUTOINCREMENT  →  SERIAL PRIMARY KEY
    6. INSERT OR REPLACE    →  handled separately in insert_or_replace()
    """
    import re

    sql = sql.replace('?', '%s')
    sql = sql.replace("date('now')", 'CURRENT_DATE')

    # SQLite AUTOINCREMENT is implicit with SERIAL in PostgreSQL
    # Must replace before the standalone AUTOINCREMENT strip
    sql = re.sub(
        r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
        'SERIAL PRIMARY KEY',
        sql, flags=re.IGNORECASE
    )
    # Strip any remaining standalone AUTOINCREMENT keywords
    sql = re.sub(r'\bAUTOINCREMENT\b', '', sql, flags=re.IGNORECASE)

    # Cast text date columns when compared to CURRENT_DATE
    sql = re.sub(
        r'\bgame_date\s*(<=?|>=?|=)\s*CURRENT_DATE',
        lambda m: f'game_date::date {m.group(1)} CURRENT_DATE',
        sql
    )

    return sql


def execute(conn, sql, params=None):
    """
    Execute a SQL statement on either database.
    Automatically converts SQLite syntax to PostgreSQL where needed.
    Returns the cursor.
    """
    cursor = get_cursor(conn)
    pg_sql = _pg_sql(sql) if USE_POSTGRES else sql
    cursor.execute(pg_sql, params or [])
    return cursor


def executemany(conn, sql, params_list):
    """
    Execute a SQL statement with multiple parameter sets.
    More efficient than calling execute() in a loop.
    """
    cursor = get_cursor(conn)
    pg_sql = _pg_sql(sql) if USE_POSTGRES else sql

    if USE_POSTGRES:
        import psycopg2.extras
        psycopg2.extras.execute_batch(cursor, pg_sql, params_list)
    else:
        cursor.executemany(pg_sql, params_list)

    return cursor


def commit(conn):
    """Commit a transaction."""
    conn.commit()


def insert_or_replace(conn, table, columns, values, conflict_columns=None):
    """
    Handle INSERT OR REPLACE (SQLite) vs INSERT ... ON CONFLICT DO UPDATE (PostgreSQL).

    WHY THIS IS NEEDED:
        SQLite has INSERT OR REPLACE which is a convenient shorthand.
        PostgreSQL requires the more explicit ON CONFLICT syntax and needs
        to know WHICH columns form the unique constraint to conflict on.
        Some tables conflict on a single primary key (default), others on
        a composite unique constraint across multiple columns — for example
        ratings_archive is unique on (team_id, season, archive_date).

    Args:
        conn:             database connection
        table:            table name
        columns:          list of column names to insert
        values:           tuple of values matching columns order
        conflict_columns: list of columns forming the unique constraint.
                          Defaults to [columns[0]] (first column = primary key).
                          Pass multiple columns for composite unique constraints.

    Examples:
        # Single primary key (default):
        insert_or_replace(db, 'teams', ['team_id', 'name'], (1, 'Duke'))

        # Composite unique constraint:
        insert_or_replace(db, 'ratings_archive',
            ['team_id', 'season', 'archive_date', ...],
            (1, 2026, '2026-03-04', ...),
            conflict_columns=['team_id', 'season', 'archive_date']
        )
    """
    if conflict_columns is None:
        conflict_columns = [columns[0]]

    if USE_POSTGRES:
        cols = ', '.join(f'"{c}"' for c in columns)
        placeholders = ', '.join(['%s'] * len(columns))
        conflict_target = ', '.join(f'"{c}"' for c in conflict_columns)
        updates = ', '.join(
            f'"{c}" = EXCLUDED."{c}"'
            for c in columns
            if c not in conflict_columns
        )
        sql = f'''
            INSERT INTO "{table}" ({cols})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_target}) DO UPDATE SET {updates}
        '''
    else:
        cols = ', '.join(columns)
        placeholders = ', '.join(['?'] * len(columns))
        sql = f'INSERT OR REPLACE INTO "{table}" ({cols}) VALUES ({placeholders})'

    cursor = get_cursor(conn)
    cursor.execute(sql, values)
    return cursor


def db_type():
    """Returns 'postgresql' or 'sqlite' - useful for logging."""
    return 'postgresql' if USE_POSTGRES else 'sqlite'