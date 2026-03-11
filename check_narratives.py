import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from utils.db import get_db

db = get_db()
cur = db.cursor()

cur.execute("SELECT COUNT(*) FROM teams WHERE narrative IS NOT NULL")
count = cur.fetchone()[0]
print(f"Teams with narratives: {count}")

cur.execute("""
    SELECT name, LEFT(narrative, 100)
    FROM teams
    WHERE narrative IS NOT NULL
    ORDER BY name
    LIMIT 5
""")
print("\nSample narratives:")
for row in cur.fetchall():
    print(f"\n  {row[0]}:")
    print(f"  {row[1]}...")

cur.execute("SELECT COUNT(*) FROM teams WHERE narrative IS NULL")
missing = cur.fetchone()[0]
print(f"\nTeams WITHOUT narratives: {missing}")

db.close()
