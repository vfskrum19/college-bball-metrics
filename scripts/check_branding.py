import sqlite3

DATABASE = '../kenpom.db'

def check_branding():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    # Check if columns exist
    print("Checking database schema...")
    columns = db.execute("PRAGMA table_info(teams)").fetchall()
    column_names = [col['name'] for col in columns]
    
    print("\nColumns in teams table:")
    for name in column_names:
        print(f"  - {name}")
    
    has_branding = all(col in column_names for col in ['primary_color', 'secondary_color', 'logo_url'])
    
    if not has_branding:
        print("\n❌ Branding columns are MISSING!")
        print("You need to run the ESPN branding script first.")
        db.close()
        return
    
    print("\n✓ Branding columns exist")
    
    # Check how many teams have branding data
    total_teams = db.execute("SELECT COUNT(*) as count FROM teams WHERE season = 2026").fetchone()['count']
    teams_with_colors = db.execute("SELECT COUNT(*) as count FROM teams WHERE season = 2026 AND primary_color IS NOT NULL").fetchone()['count']
    teams_with_logos = db.execute("SELECT COUNT(*) as count FROM teams WHERE season = 2026 AND logo_url IS NOT NULL").fetchone()['count']
    
    print(f"\nBranding data for 2026 season:")
    print(f"  Total teams: {total_teams}")
    print(f"  Teams with colors: {teams_with_colors}")
    print(f"  Teams with logos: {teams_with_logos}")
    
    if teams_with_colors == 0:
        print("\n❌ NO teams have branding data!")
        print("Run: python fetch_espn_branding_improved.py")
        db.close()
        return
    
    # Show a few examples
    print("\nSample teams with branding:")
    samples = db.execute("""
        SELECT name, primary_color, secondary_color, logo_url 
        FROM teams 
        WHERE season = 2026 AND primary_color IS NOT NULL 
        LIMIT 5
    """).fetchall()
    
    for team in samples:
        print(f"\n  {team['name']}")
        print(f"    Primary: {team['primary_color']}")
        print(f"    Secondary: {team['secondary_color']}")
        print(f"    Logo: {team['logo_url'][:50]}..." if team['logo_url'] else "    Logo: None")
    
    db.close()

if __name__ == '__main__':
    check_branding()
