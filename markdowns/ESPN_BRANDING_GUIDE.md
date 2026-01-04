# ESPN Branding Integration Guide

## What's New

Your KenPom comparison tool now includes:

1. ✅ **Team Colors** - Each team card displays in the team's actual colors
2. ✅ **Team Logos** - Official team logos appear at the top of each card
3. ✅ **Defensive Four Factors** - Now showing both offensive AND defensive metrics
4. ✅ **Footer Status Bar** - Database info moved to bottom for cleaner look

## Setup Instructions

### Step 1: Update Your Database Schema

The database needs new columns for branding. You have two options:

**Option A: Fresh Start (Recommended)**
1. Delete your `kenpom.db` file
2. Run:
   ```bash
   python
   ```
   ```python
   from app import init_db
   init_db()
   exit()
   ```
3. Sync KenPom data:
   ```bash
   python fetch_data.py
   ```

**Option B: Keep Existing Data**
The ESPN script will automatically add the necessary columns.

### Step 2: Fetch ESPN Branding Data

Run the ESPN branding sync script:

```bash
python fetch_espn_branding.py
```

This will:
- Fetch all college basketball teams from ESPN's API
- Match them to your KenPom teams (using fuzzy name matching)
- Update your database with:
  - Primary team color (hex code)
  - Secondary team color (hex code)
  - Team logo URL

**Expected Output:**
```
==================================================
Syncing ESPN Team Branding
==================================================

Found 362 KenPom teams for season 2026
Fetching teams from ESPN API...
✓ Fetched 358 teams from ESPN

Matching teams...
✓ Matched 350 teams (96.7%)

✓ Updated 350 teams with branding

⚠️  12 teams not matched:
  - Team Name (best: Similar Name, 0.75)
  ...

==================================================
ESPN branding sync complete!
==================================================
```

### Step 3: Replace Your Files

1. **Copy the new `app.py`** to your kenpom-app folder (replaces old one)
2. **Copy the new `index.html`** to your kenpom-app folder (replaces old one)
3. **Add `fetch_espn_branding.py`** to your kenpom-app folder

### Step 4: Restart Your Server

```bash
python app.py
```

### Step 5: Refresh Your Browser

Hard refresh (Ctrl+Shift+R or Cmd+Shift+R) to see the changes!

## What You'll See

### Team Cards Now Feature:

**1. Color Accent Bar**
- Thin gradient bar at the top of each card
- Uses team's primary → secondary colors
- Subtle but distinctive

**2. Team Logo**
- Centered at top of card
- 80x80px, properly sized
- Drop shadow for depth

**3. Colored Team Name**
- Team name appears in the team's primary color
- Makes it immediately recognizable

**4. Subtle Border**
- Card border uses team color at 25% opacity
- Clean, not overwhelming

**5. Defensive Four Factors**
- New "Defense" subsection added
- Shows: Opp. eFG%, Opp. TO%, Def. Reb. %, Opp. FT Rate
- Same ranking system as offense

### Footer Status Bar:

- Moved from top to bottom of page
- Smaller, more subtle design
- Shows: Database status, team count, last update time

## Troubleshooting

### "No logos or colors showing"

**Check 1:** Did you run `fetch_espn_branding.py`?
```bash
python fetch_espn_branding.py
```

**Check 2:** Verify database has branding data:
```bash
python
```
```python
import sqlite3
db = sqlite3.connect('kenpom.db')
result = db.execute("SELECT name, primary_color, logo_url FROM teams WHERE logo_url IS NOT NULL LIMIT 5").fetchall()
for row in result:
    print(row)
db.close()
exit()
```

You should see team names with color codes and logo URLs.

**Check 3:** Hard refresh your browser (Ctrl+Shift+R)

### "Some teams don't have colors/logos"

This is normal! The ESPN API uses slightly different team names than KenPom. The script uses fuzzy matching with an 80% similarity threshold.

**To see which teams didn't match:**
Look at the output when you ran `fetch_espn_branding.py`. It lists unmatched teams.

**To manually add branding for a team:**
```bash
python
```
```python
import sqlite3
db = sqlite3.connect('kenpom.db')
db.execute('''
    UPDATE teams 
    SET primary_color = '#003087', 
        secondary_color = '#FFFFFF',
        logo_url = 'https://example.com/logo.png'
    WHERE name = 'Duke'
''')
db.commit()
db.close()
exit()
```

### "Defensive four factors not showing"

Make sure you've run `python fetch_data.py` recently. The defensive metrics come from the KenPom four-factors endpoint.

## Re-syncing ESPN Data

If ESPN updates their logos or you want to refresh the branding:

```bash
python fetch_espn_branding.py
```

This is safe to run multiple times - it will update existing teams.

## Daily Workflow

**Morning routine (during basketball season):**
1. Fetch latest KenPom data:
   ```bash
   python fetch_data.py
   ```

2. (Optional) Refresh ESPN branding if teams changed:
   ```bash
   python fetch_espn_branding.py
   ```

3. Server should still be running - just refresh your browser!

## Technical Details

### How Team Colors Work

1. **Database Storage:** Colors stored as hex codes (e.g., "#003087")
2. **Frontend Application:** 
   - Cards get dynamic `borderColor` style
   - Top accent bar gets gradient of primary → secondary
   - Team name gets primary color
   - All at 40% opacity to stay subtle

3. **Fallback:** If no color data, defaults to blue accent (`#4A9EFF`)

### Logo Display

- Logos are fetched from ESPN's CDN
- Displayed at 80x80px with `object-fit: contain`
- Drop shadow for visual depth
- Cached by browser for performance

## Future Enhancements

Ideas for what could be added:
- Manual color picker for teams that don't match
- Alternative logo sizes/styles
- Team color in hover effects
- Color-based card backgrounds (subtle)
- Conference color themes

Enjoy your personalized team comparison tool! 🏀
