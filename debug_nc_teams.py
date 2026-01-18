import sqlite3

db = sqlite3.connect('database/kenpom.db')
db.row_factory = sqlite3.Row

print("=== NC Teams in Database ===\n")
teams = db.execute("""
    SELECT t.team_id, t.name, r.rank_adj_em 
    FROM teams t
    LEFT JOIN ratings r ON t.team_id = r.team_id
    WHERE t.name LIKE '%North Carolina%' 
       OR t.name LIKE '%N.C.%' 
       OR t.name LIKE '%NC %'
       OR t.name LIKE '%A&T%'
    ORDER BY t.name
""").fetchall()

for t in teams:
    print(f"ID {t['team_id']}: {t['name']} (Rank #{t['rank_adj_em']})")

print("\n=== Bracket Entries ===\n")
bracket = db.execute("""
    SELECT b.team_id, b.seed, b.region, t.name, r.rank_adj_em
    FROM bracket b
    JOIN teams t ON b.team_id = t.team_id
    LEFT JOIN ratings r ON t.team_id = r.team_id
    WHERE t.name LIKE '%North Carolina%' 
       OR t.name LIKE '%N.C.%' 
       OR t.name LIKE '%NC %'
       OR t.name LIKE '%A&T%'
    ORDER BY b.region, b.seed
""").fetchall()

for b in bracket:
    print(f"Seed #{b['seed']} {b['region']}: {b['name']} (ID {b['team_id']}, Rank #{b['rank_adj_em']})")

db.close()