# Tournament Resume Data Setup Guide

## 🏀 What This Adds

Your KenPom comparison tool now includes **Tournament Resume metrics**:

- **NET Ranking** - NCAA's official tournament selection metric
- **Quad Records** - W-L records in each quadrant (Q1, Q2, Q3, Q4)
- **Strength of Record (SOR)** - How impressive the wins are

This data is scraped from **WarrenNolan.com** and stored in your existing `kenpom.db` database.

## 📦 What You Got

### New Files:
- **`fetch_resume_data.py`** - Scrapes WarrenNolan for NET/quad data
- **Updated `app.py`** - API now includes resume data
- **Updated `static/js/app.js`** - Frontend displays "Tournament Resume" section
- **Updated `requirements.txt`** - Added BeautifulSoup for web scraping

### New Database Table:
```sql
resume_metrics (
    team_id → references teams
    net_rank
    quad1_wins, quad1_losses
    quad2_wins, quad2_losses  
    quad3_wins, quad3_losses
    quad4_wins, quad4_losses
    sor_rank
)
```

## 🚀 Setup Instructions

### Step 1: Install New Dependency

```bash
pip install beautifulsoup4
```

Or install everything fresh:
```bash
pip install -r requirements.txt
```

### Step 2: Replace Your Files

1. **Replace `app.py`** with the updated version
2. **Replace `static/js/app.js`** with the updated version
3. **Add `fetch_resume_data.py`** to your kenpom-app folder

### Step 3: Fetch Resume Data

```bash
python fetch_resume_data.py
```

This will:
- Create the `resume_metrics` table in `kenpom.db`
- Scrape WarrenNolan for all teams
- Match teams to your existing database
- Store NET rankings and quad records

**Expected output:**
```
==================================================
Syncing Tournament Resume Data
==================================================

✓ Resume metrics table ready
Fetching data from https://www.warrennolan.com/basketball/2026/net...
✓ Scraped 362 teams from WarrenNolan

Matching teams to database...
✓ Matched 340 teams (93.9%)

⚠️  22 teams not matched:
  - Team Name (best: Similar Name, 0.72)
  ...

Updating database...
✓ Updated 340 teams with resume data

==================================================
Resume data sync complete!
==================================================
```

### Step 4: Restart Flask

```bash
# Stop server (Ctrl+C)
python app.py
```

### Step 5: Refresh Browser

Hard refresh (Ctrl+Shift+R) and compare two teams!

You should now see a **"Tournament Resume"** section showing:
- NET Ranking: #15
- Quadrant 1: 8-3
- Quadrant 2: 4-1
- Quadrant 3: 2-0
- Quadrant 4: 6-0
- Strength of Record: #12

## 📊 What the Quad Records Mean

**Quadrants are based on game location + opponent NET rank:**

| Quad | Home | Neutral | Away |
|------|------|---------|------|
| Q1 | 1-30 | 1-50 | 1-75 |
| Q2 | 31-75 | 51-100 | 76-135 |
| Q3 | 76-160 | 101-200 | 136-240 |
| Q4 | 161+ | 201+ | 241+ |

**Why it matters:**
- **Q1 wins** = Best quality wins (impress selection committee)
- **Q3/Q4 losses** = "Bad losses" (hurt tournament chances)
- Committee heavily weighs quad records for at-large bids

## 🔄 Daily Updates

During basketball season, run this once per day (WarrenNolan updates overnight):

```bash
python fetch_data.py              # KenPom data
python fetch_espn_branding_improved.py  # Team colors/logos
python fetch_resume_data.py       # NET/quad records
```

## 🎨 How It Looks

The new "Tournament Resume" section appears below "Four Factors" in each team card:

```
┌─────────────────────────────────┐
│ [LOGO]  DUKE                    │
│         ACC • Coach             │
│         15-2                    │
├─────────────────────────────────┤
│ Overall Rankings                │
│ ...                             │
├─────────────────────────────────┤
│ Four Factors                    │
│ ...                             │
├─────────────────────────────────┤
│ Tournament Resume          ← NEW│
│ NET Ranking          #8         │
│ Quadrant 1           10-2       │
│ Quadrant 2           4-0        │
│ Quadrant 3           1-0        │
│ Quadrant 4           0-0        │
│ Strength of Record   #5         │
└─────────────────────────────────┘
```

## 🔧 Troubleshooting

### "No module named 'bs4'"
```bash
pip install beautifulsoup4
```

### "Resume section not showing"
1. Did you run `python fetch_resume_data.py`?
2. Check if data exists:
   ```bash
   python
   ```
   ```python
   import sqlite3
   db = sqlite3.connect('kenpom.db')
   count = db.execute("SELECT COUNT(*) FROM resume_metrics").fetchone()[0]
   print(f"Teams with resume data: {count}")
   db.close()
   exit()
   ```

### "Many teams not matched"
This is normal! Team names differ between WarrenNolan and KenPom:
- WarrenNolan: "UConn"
- KenPom: "Connecticut"

The script matches ~90-95% automatically. Matched teams will show resume data, unmatched won't (but everything else still works).

### "WarrenNolan page changed"
Web scraping can break if websites change their layout. If this happens:
1. Let me know the error
2. I can update the scraper to handle the new format

## 📈 Future Enhancements

Ideas for extending this feature:

- **Bad Loss Highlighting** - Show Q3/Q4 losses in red
- **Resume Score** - Calculate overall resume strength
- **Quadrant Breakdown** - Show home/away/neutral splits
- **Historical Tracking** - Track how quad records change over season
- **Bubble Watch** - Highlight teams on tournament bubble

## 🎯 Understanding the Data

**NET (NCAA Evaluation Tool):**
- Official metric used by selection committee
- Replaced RPI in 2018
- Factors: winning %, strength of schedule, game location, scoring margin (capped)

**Quadrants:**
- Categorize wins/losses by opponent quality + location
- Selection committee focuses heavily on Q1/Q2 records
- Q3/Q4 losses are particularly damaging

**SOR (Strength of Record):**
- "How difficult is this team's record to achieve?"
- Accounts for strength of schedule
- Different from NET (which measures team quality)

## 🎓 Pro Tips

**Good Resume:**
- High NET ranking (top 50)
- Lots of Q1 wins (8+)
- Few Q3/Q4 losses (0-1)
- Strong Q1+Q2 record combined

**Bubble Team:**
- NET in 40-80 range
- 4-6 Q1 wins
- 1-2 Q3 losses might be okay
- Q4 losses = kiss of death

**Compare bubble teams** to see who has the better tournament case!

Enjoy your enhanced comparison tool! 🏀🎉
