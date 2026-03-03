# 🏀 KenPom Bracketology App

A comprehensive college basketball analytics platform powered by KenPom data, featuring:
- **Team Comparison Tool** - Side-by-side matchup analysis with efficiency metrics
- **Momentum Tracker** - Track hot/cold teams, find upset candidates
- **Championship Contender Tiers** - Historical analysis identifying title-worthy teams
- **Bracket Visualization** - NCAA tournament bracket with analytics overlays

---

## 📁 Project Structure

```
kenpom-app/
├── backend/
│   └── app.py              # Flask API server
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MomentumTracker.jsx
│   │   │   ├── MomentumTracker.css
│   │   │   ├── ComparisonTool.jsx
│   │   │   └── ...
│   │   └── App.jsx
│   └── index.html
├── scrapers/
│   ├── fetch_data.py                    # Core KenPom data (ratings, four factors)
│   ├── fetch_momentum_ratings.py        # Historical rating snapshots
│   ├── fetch_game_scores_espn.py        # Game scores from ESPN
│   ├── calculate_momentum.py            # Calculate momentum scores
│   ├── fetch_historical_four_factors.py # Championship contender analysis
│   ├── fetch_espn_branding.py           # Team logos and colors
│   └── fetch_players.py                 # Player data
├── database/
│   └── kenpom.db           # SQLite database
├── .env                    # API keys (not in git)
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- KenPom API subscription (for API key)

### Setup

```bash
# Clone and enter directory
cd kenpom-app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Python dependencies
pip install flask flask-cors requests python-dotenv

# Install frontend dependencies
cd frontend
npm install
cd ..

# Create .env file with your API key
echo "KENPOM_API_KEY=your_key_here" > .env
```

### Run the App

```bash
# Terminal 1: Start backend
cd backend
python app.py

# Terminal 2: Start frontend
cd frontend
npm run dev
```

Visit `http://localhost:5173`

---

## 📊 Data Update Commands

### ⚠️ IMPORTANT: Date Handling

All data fetching scripts use **YESTERDAY** as the most recent date, not today. This is intentional because:
- Today's games may still be in progress
- KenPom updates ratings after all games complete
- Weekend data is especially incomplete during the day

### Daily Update Routine

Run these commands in order to update all momentum data:

```bash
# 1. Fetch latest KenPom ratings and four factors
python scrapers/fetch_data.py

# 2. Fetch game predictions from KenPom Fanmatch
python scrapers/fetch_games.py

# 3. Fetch rating snapshots (for trajectory calculation)
python scrapers/fetch_momentum_ratings.py

# 4. Fetch game scores from ESPN
python scrapers/fetch_game_scores_espn.py

# 5. Calculate momentum scores
python scrapers/calculate_momentum.py
```

Or run the full pipeline with one command:
```bash
python scrapers/calculate_momentum.py --full
```

---

## 🔧 Individual Scraper Reference

### `fetch_data.py` - Core KenPom Data
Fetches current ratings, four factors, and team info.

```bash
# Full refresh of all data
python scrapers/fetch_data.py

# Specific data types
python scrapers/fetch_data.py --ratings
python scrapers/fetch_data.py --four-factors
python scrapers/fetch_data.py --teams
```

**Tables updated:** `teams`, `ratings`, `four_factors`

---

### `fetch_games.py` - Game Predictions (Fanmatch)
Fetches KenPom Fanmatch predictions (predicted scores, win probabilities). **This populates the games table that everything else depends on.**

```bash
# Fetch last 30 days (default)
python scrapers/fetch_games.py

# Fetch last 45 days
python scrapers/fetch_games.py --days 45

# Fetch specific date
python scrapers/fetch_games.py --date 2026-01-15
```

**Tables updated:** `games` (game_date, home/away teams, predicted scores, win probabilities)

**Note:** Uses yesterday as end date. This must run BEFORE `fetch_game_scores_espn.py` since ESPN scores are matched against games in this table.

---

### `fetch_momentum_ratings.py` - Historical Snapshots
Fetches rating snapshots every 3 days for calculating trajectory.

```bash
# Fetch last 30 days (default)
python scrapers/fetch_momentum_ratings.py

# Fetch last 45 days
python scrapers/fetch_momentum_ratings.py --days 45

# Fetch specific date
python scrapers/fetch_momentum_ratings.py --date 2026-01-15

# Show statistics
python scrapers/fetch_momentum_ratings.py --stats
```

**Tables updated:** `momentum_ratings`

**Note:** Uses yesterday as end date. Snapshots are taken every 3 days to balance API calls vs data granularity.

---

### `fetch_game_scores_espn.py` - Game Scores
Fetches actual game scores from ESPN API to compare against predictions.

```bash
# Update all games missing scores
python scrapers/fetch_game_scores_espn.py

# Show statistics
python scrapers/fetch_game_scores_espn.py --stats
```

**Tables updated:** `games` (home_score, away_score columns)

**Note:** Only fetches past dates. Matches teams using a comprehensive name mapping (KenPom → ESPN).

---

### `calculate_momentum.py` - Momentum Scores
Calculates momentum scores using game results, vs-expected performance, and rating trajectory.

```bash
# Calculate for all teams
python scrapers/calculate_momentum.py

# Calculate for specific team
python scrapers/calculate_momentum.py --team Duke

# Show top 20 hottest teams
python scrapers/calculate_momentum.py --top 20

# Full pipeline (fetch + calculate)
python scrapers/calculate_momentum.py --full
```

**Tables updated:** `momentum_cache`

**Momentum Score Components:**
| Component | Weight | Description |
|-----------|--------|-------------|
| Win % | 25 pts | Win percentage in last 10 games |
| vs Expected | 30 pts | Performance vs KenPom predictions |
| Win Streak | 10 pts | Current win streak bonus |
| Rank Trajectory | 20 pts | Rank improvement over period |
| Margin | 15 pts | Average margin of victory |

---

### `fetch_historical_four_factors.py` - Championship Analysis
Analyzes historical Final Four/Champion data to identify meaningful metrics.

```bash
# Full pipeline: fetch + analyze + score
python scrapers/fetch_historical_four_factors.py --all

# Individual steps
python scrapers/fetch_historical_four_factors.py              # Fetch historical data
python scrapers/fetch_historical_four_factors.py --analyze    # Run threshold analysis
python scrapers/fetch_historical_four_factors.py --contenders # Score current teams
python scrapers/fetch_historical_four_factors.py --stats      # Show database stats

# Fetch specific year
python scrapers/fetch_historical_four_factors.py --year 2024
```

**Tables updated:** `historical_four_factors`, `final_four_analysis`, `contender_scores`

---

### `fetch_espn_branding.py` - Team Logos & Colors
Fetches team logos and primary/secondary colors from ESPN.

```bash
python scrapers/fetch_espn_branding.py
```

**Tables updated:** `teams` (logo_url, primary_color, secondary_color)

---

## 📈 API Endpoints

### Momentum Tracker
| Endpoint | Description |
|----------|-------------|
| `GET /api/momentum/rankings` | Get momentum rankings with filters |
| `GET /api/momentum/team/<id>` | Get detailed momentum for one team |
| `GET /api/momentum/upsets` | Get first-round upset candidates |
| `GET /api/momentum/vulnerable` | Get vulnerable favorites |
| `GET /api/momentum/conferences` | Get conference list for filtering |

**Rankings Query Parameters:**
- `limit` - Number of results (default: 50)
- `min_games` - Minimum games played (default: 5)
- `trend` - Filter by trend: hot, rising, stable, falling, cold
- `tournament` - Tournament teams only: true/false
- `kenpom_min`, `kenpom_max` - KenPom rank range
- `conference` - Filter by conference name

### Team Data
| Endpoint | Description |
|----------|-------------|
| `GET /api/teams` | Get all teams |
| `GET /api/team/<id>/ratings` | Get team ratings |
| `GET /api/compare?team1=X&team2=Y` | Compare two teams |
| `GET /api/search?q=query` | Search teams by name |

### Bracket
| Endpoint | Description |
|----------|-------------|
| `GET /api/bracket` | Get full bracket |
| `GET /api/bracket/region/<n>` | Get region data |
| `GET /api/matchup/<id>` | Get matchup details |

---

## 🗄️ Database Schema

### Core Tables
- `teams` - Team info, logos, colors
- `ratings` - Current KenPom ratings
- `four_factors` - Current four factors data
- `games` - Schedule with predictions and actual scores

### Momentum Tables
- `momentum_ratings` - Historical rating snapshots
- `momentum_cache` - Calculated momentum scores

### Tournament Tables
- `bracket` - Tournament seeds and regions
- `matchups` - First round matchups

### Analysis Tables
- `historical_four_factors` - Historical data (2002-2025)
- `final_four_analysis` - Metric thresholds from champions
- `contender_scores` - Current teams scored against thresholds

---

## 🐛 Troubleshooting

### "No momentum data showing"
1. Check that games have scores: `python scrapers/fetch_game_scores_espn.py --stats`
2. Run full momentum pipeline: `python scrapers/calculate_momentum.py --full`

### "Team logos not showing"
1. Check logo_url in database
2. Re-fetch: `python scrapers/fetch_espn_branding.py`

### "API returns empty data"
1. Verify KENPOM_API_KEY in .env file
2. Check API subscription status
3. Try fetching yesterday's data (today may be incomplete)

### "Team names don't match"
ESPN and KenPom use different names. The mapping is in `fetch_game_scores_espn.py`. Add missing mappings to `KENPOM_TO_ESPN` dict.

---

## 📅 Recommended Update Schedule

| Frequency | Scripts | Purpose |
|-----------|---------|---------|
| Daily (morning) | `fetch_data.py`, `fetch_game_scores_espn.py`, `calculate_momentum.py` | Fresh ratings and momentum |
| Every 3 days | `fetch_momentum_ratings.py` | Rating trajectory snapshots |
| Weekly | `fetch_historical_four_factors.py --contenders` | Update contender tiers |
| As needed | `fetch_espn_branding.py` | New team logos/colors |

---

## 🏆 Championship Contender Methodology

Based on analysis of 23 National Champions (2002-2025, excluding 2020):

### Critical Metrics (75%+ of champions meet threshold)
| Metric | Threshold | Champions Meeting |
|--------|-----------|-------------------|
| AdjEM Rank | Top 10 | 87% |
| AdjOE Rank | Top 15 | 74% |
| AdjDE Rank | Top 40 | 100% |

### Important Metrics (useful but not dealbreakers)
| Metric | Threshold | Champions Meeting |
|--------|-----------|-------------------|
| Defensive eFG% | Top 50 | 78% |
| Offensive eFG% | Top 75 | 74% |
| Offensive Reb% | Top 50 | 74% |

### Tier Classification
| Tier | Metrics Met (of 6) |
|------|-------------------|
| 🏆 Elite Contender | 5-6 |
| 🎯 Strong Contender | 4 |
| ⚠️ Flawed Contender | 2-3 |
| ❌ Long Shot | 0-1 |

---

## 📝 Notes

- **Data Freshness:** KenPom updates ratings after each day's games complete. Morning runs get yesterday's complete picture.
- **API Rate Limits:** Scripts include `time.sleep()` calls to be respectful to APIs.
- **Season:** Current season is hardcoded as `CURRENT_SEASON = 2026` in scripts.

---

## 🤝 Contributing

1. Follow existing code patterns
2. Add new scrapers to `/scrapers` directory
3. Update this README with new commands
4. Test with `--stats` flags before committing

---

*Last updated: February 2, 2026*