import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from utils.db import get_db

db = get_db()
cur = db.cursor()

cur.execute("""
    SELECT name, narrative, narrative_updated_at
    FROM teams
    WHERE name ILIKE %s
""", ('%georgia%',))

for row in cur.fetchall():
    print(f"Team: {row[0]}")
    print(f"Narrative: {row[1]}")
    print(f"Updated: {row[2]}")
    print()

# Also check overall count
cur.execute("SELECT COUNT(*) FROM teams WHERE narrative IS NOT NULL AND narrative != ''")
print(f"Total teams with narratives: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM teams WHERE narrative IS NULL OR narrative = ''")
print(f"Total teams WITHOUT narratives: {cur.fetchone()[0]}")

db.close()
