import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from utils.db import get_db, commit

db = get_db()
cur = db.cursor()

# Find Duke's team_id
cur.execute("SELECT team_id, name, narrative FROM teams WHERE name = 'Duke'")
row = cur.fetchone()
print(f"Before: {row}")

# Write a test narrative
cur.execute("""
    UPDATE teams
    SET narrative = %s,
        narrative_updated_at = NOW()::TEXT
    WHERE name = 'Duke'
""", ('TEST NARRATIVE — delete me.',))

commit(db)
db.close()

# Re-open and verify it persisted
db2 = get_db()
cur2 = db2.cursor()
cur2.execute("SELECT team_id, name, narrative FROM teams WHERE name = 'Duke'")
row2 = cur2.fetchone()
print(f"After:  {row2}")
db2.close()
