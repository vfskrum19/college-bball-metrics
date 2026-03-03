"""
SQLite → PostgreSQL Migration Script
=====================================
Reads every table from your local SQLite database and writes it to
the PostgreSQL database on Railway.

WHY WE'RE DOING THIS:
    SQLite is a file on your machine. It's great for development but
    can't be used on Railway (Railway doesn't have access to your
    local filesystem). PostgreSQL is a proper server database that
    Railway hosts for you, handles concurrent connections, and
    persists data across deployments.

SAFETY:
    - Your SQLite file is never modified. It stays as a local backup.
    - The script verifies row counts after migration.
    - If anything fails, you can re-run it safely (it clears tables first).

USAGE:
    1. Make sure DATABASE_URL is in your .env file
    2. From your project root, run:
       python database/migrate_to_postgres.py

    To do a dry run (check connection without writing data):
       python database/migrate_to_postgres.py --dry-run
"""

import sqlite3
import sys
import os
import argparse
from pathlib import Path

# Load .env file so DATABASE_URL is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed - rely on env var being set manually
    pass

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed.")
    print("Run: pip install psycopg2-binary")
    sys.exit(1)

# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).parent.parent
SQLITE_PATH = PROJECT_ROOT / 'database' / 'kenpom.db'
DATABASE_URL = os.environ.get('DATABASE_URL')

# ============================================================
# HELPERS
# ============================================================

def get_sqlite_conn():
    if not SQLITE_PATH.exists():
        print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_postgres_conn():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Add it to your .env file: DATABASE_URL=postgresql://...")
        sys.exit(1)

    # Railway sometimes provides postgres:// but psycopg2 needs postgresql://
    url = DATABASE_URL
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    try:
        conn = psycopg2.connect(url)
        return conn
    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to PostgreSQL: {e}")
        print("Check that your DATABASE_URL is correct.")
        sys.exit(1)


def sqlite_to_postgres_type(sqlite_type):
    """
    Convert SQLite column types to PostgreSQL equivalents.
    
    SQLite is loosely typed - it stores almost everything as TEXT or INTEGER.
    PostgreSQL is strict - we map each type explicitly.
    """
    sqlite_type = (sqlite_type or '').upper()
    
    if 'INT' in sqlite_type:
        return 'INTEGER'
    elif 'REAL' in sqlite_type or 'FLOAT' in sqlite_type or 'DOUBLE' in sqlite_type:
        return 'DOUBLE PRECISION'
    elif 'BOOL' in sqlite_type:
        return 'BOOLEAN'
    elif 'DATE' in sqlite_type:
        return 'TEXT'  # Keep as TEXT - avoids format parsing issues
    elif 'BLOB' in sqlite_type:
        return 'BYTEA'
    else:
        return 'TEXT'  # Default - safe catch-all


def get_sqlite_tables(sqlite_conn):
    """Get all user tables from SQLite (excludes sqlite_sequence etc.)"""
    cursor = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row[0] for row in cursor.fetchall()]


def get_sqlite_schema(sqlite_conn, table_name):
    """Get column definitions for a SQLite table"""
    cursor = sqlite_conn.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def get_row_count(conn, table_name, is_postgres=False):
    """Get row count for a table"""
    if is_postgres:
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        return cursor.fetchone()[0]
    else:
        return conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]


# ============================================================
# MIGRATION LOGIC
# ============================================================

def create_postgres_table(pg_conn, table_name, columns):
    """
    Create a table in PostgreSQL based on SQLite column definitions.
    
    We DROP and recreate so the script is safe to re-run. If you run
    it twice, the second run starts fresh rather than duplicating data.
    """
    cursor = pg_conn.cursor()
    
    # Build column definitions
    col_defs = []
    primary_key = None
    
    for col in columns:
        col_name = col[1]   # column name
        col_type = col[2]   # declared type
        not_null = col[3]   # 1 if NOT NULL
        default_val = col[4]  # default value
        is_pk = col[5]      # 1 if primary key
        
        pg_type = sqlite_to_postgres_type(col_type)
        
        # Use SERIAL for auto-increment primary keys
        if is_pk and 'INT' in (col_type or '').upper():
            pg_type = 'SERIAL'
            primary_key = col_name
        
        col_def = f'"{col_name}" {pg_type}'
        
        if is_pk:
            col_def += ' PRIMARY KEY'
        elif not_null:
            col_def += ' NOT NULL'
            
        if default_val is not None and not is_pk:
            # Convert SQLite defaults to PostgreSQL equivalents
            if str(default_val).upper() in ('CURRENT_TIMESTAMP', 'NOW()'):
                col_def += ' DEFAULT CURRENT_TIMESTAMP'
            elif str(default_val) not in ('NULL',):
                col_def += f' DEFAULT {default_val}'
        
        col_defs.append(col_def)
    
    # Drop existing table and recreate
    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
    
    create_sql = f'CREATE TABLE "{table_name}" (\n  ' + ',\n  '.join(col_defs) + '\n)'
    
    try:
        cursor.execute(create_sql)
        pg_conn.commit()
    except Exception as e:
        pg_conn.rollback()
        print(f"  ERROR creating table {table_name}: {e}")
        print(f"  SQL was: {create_sql}")
        raise


def migrate_table(sqlite_conn, pg_conn, table_name, dry_run=False):
    """
    Copy all rows from a SQLite table into PostgreSQL.
    
    Uses batch inserts (1000 rows at a time) for efficiency.
    Batching matters when tables have thousands of rows - inserting
    one row at a time would be very slow over a network connection.
    """
    # Get schema
    columns = get_sqlite_schema(sqlite_conn, table_name)
    col_names = [col[1] for col in columns]
    
    # Get data
    rows = sqlite_conn.execute(f"SELECT * FROM {table_name}").fetchall()
    row_count = len(rows)
    
    print(f"  {table_name}: {row_count} rows", end='')
    
    if dry_run:
        print(" [DRY RUN - skipping write]")
        return row_count
    
    # Create table in Postgres
    create_postgres_table(pg_conn, table_name, columns)
    
    if row_count == 0:
        print(" ✓ (empty table)")
        return 0
    
    # Insert in batches
    cursor = pg_conn.cursor()
    quoted_cols = ', '.join(f'"{c}"' for c in col_names)
    placeholders = ', '.join(['%s'] * len(col_names))
    insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})'
    
    # For SERIAL columns, we need to insert the actual IDs and then
    # reset the sequence so future inserts don't conflict
    has_serial = any(
        col[5] == 1 and 'INT' in (col[2] or '').upper()
        for col in columns
    )
    
    BATCH_SIZE = 1000
    batch = []
    
    for row in rows:
        batch.append(tuple(row))
        if len(batch) >= BATCH_SIZE:
            try:
                psycopg2.extras.execute_batch(cursor, insert_sql, batch)
                pg_conn.commit()
            except Exception as e:
                pg_conn.rollback()
                print(f"\n  ERROR inserting batch into {table_name}: {e}")
                raise
            batch = []
    
    # Insert remaining rows
    if batch:
        try:
            psycopg2.extras.execute_batch(cursor, insert_sql, batch)
            pg_conn.commit()
        except Exception as e:
            pg_conn.rollback()
            print(f"\n  ERROR inserting final batch into {table_name}: {e}")
            raise
    
    # Reset sequence for auto-increment columns so new inserts get correct IDs
    if has_serial:
        pk_col = next(col[1] for col in columns if col[5] == 1)
        cursor.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('"{table_name}"', '{pk_col}'),
                COALESCE((SELECT MAX("{pk_col}") FROM "{table_name}"), 1)
            )
        """)
        pg_conn.commit()
    
    print(f" ✓")
    return row_count


def verify_migration(sqlite_conn, pg_conn, tables):
    """
    Compare row counts between SQLite and PostgreSQL for every table.
    
    This is the trust-but-verify step. A mismatch means something went
    wrong during the batch inserts and you should investigate before
    switching your app to use PostgreSQL.
    """
    print("\n" + "="*60)
    print("VERIFICATION - Comparing row counts")
    print("="*60)
    
    all_match = True
    
    for table in tables:
        sqlite_count = get_row_count(sqlite_conn, table, is_postgres=False)
        pg_count = get_row_count(pg_conn, table, is_postgres=True)
        
        match = sqlite_count == pg_count
        status = "✓" if match else "✗ MISMATCH"
        
        if not match:
            all_match = False
        
        print(f"  {table:30s} SQLite: {sqlite_count:6d}  Postgres: {pg_count:6d}  {status}")
    
    print("="*60)
    if all_match:
        print("✓ All tables match. Migration successful!")
    else:
        print("✗ Some tables don't match. Check errors above before switching to PostgreSQL.")
    
    return all_match


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Migrate SQLite database to PostgreSQL')
    parser.add_argument('--dry-run', action='store_true',
                        help='Test connections and show what would be migrated without writing')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("SQLite → PostgreSQL Migration")
    if args.dry_run:
        print("DRY RUN MODE - No data will be written")
    print("="*60)
    
    # Connect to both databases
    print(f"\nConnecting to SQLite: {SQLITE_PATH}")
    sqlite_conn = get_sqlite_conn()
    print("✓ SQLite connected")
    
    print(f"\nConnecting to PostgreSQL...")
    pg_conn = get_postgres_conn()
    print("✓ PostgreSQL connected")
    
    # Get tables to migrate
    tables = get_sqlite_tables(sqlite_conn)
    print(f"\nFound {len(tables)} tables to migrate:")
    for t in tables:
        print(f"  - {t}")
    
    # Migrate each table
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Migrating tables...")
    
    total_rows = 0
    failed_tables = []
    
    for table in tables:
        try:
            rows = migrate_table(sqlite_conn, pg_conn, table, dry_run=args.dry_run)
            total_rows += rows
        except Exception as e:
            failed_tables.append(table)
            print(f"\n  FAILED: {table} - {e}")
    
    if failed_tables:
        print(f"\n✗ Migration failed for: {', '.join(failed_tables)}")
        sys.exit(1)
    
    if not args.dry_run:
        # Verify everything made it across
        all_match = verify_migration(sqlite_conn, pg_conn, tables)
        
        if not all_match:
            print("\nReview the mismatches above before switching to PostgreSQL.")
            sys.exit(1)
    
    print(f"\n{'Would migrate' if args.dry_run else 'Migrated'} {total_rows} total rows across {len(tables)} tables.")
    
    if not args.dry_run:
        print("\nNext step: Set DATABASE_URL in your Railway environment variables.")
        print("Your SQLite file is untouched and remains as a local backup.")
    
    sqlite_conn.close()
    pg_conn.close()


if __name__ == '__main__':
    main()
