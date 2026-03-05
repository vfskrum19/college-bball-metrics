# Court Vision — College Basketball Analytics

A full-stack analytics dashboard for NCAA Division I basketball, powered by KenPom data. Features team ratings, momentum tracking, tournament resume analysis, and championship contender scoring.

Live at: https://college-bball-metrics-production.up.railway.app/ 

---

## Features

- **Team Search & Compare** — side-by-side comparison of any two D1 teams with full KenPom metrics
- **Momentum Tracker** — rolling performance trends based on actual game results vs. expectations
- **Tournament Resume** — NET rankings and quad record breakdowns for every team
- **Championship Contender Scores** — teams scored against historical metrics of national champions (2002–2025)
- **Bracket Projections** — consensus bracket from Bracket Matrix (pre-Selection Sunday), switching to real bracket after

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React (Vite) |
| Backend | Flask (Python) |
| Database | PostgreSQL (Railway) |
| Hosting | Railway |
| Data | KenPom API, ESPN API, NCAA.com |

---

## Architecture

```
project root/
  cron.py               # Daily data pipeline runner
  Dockerfile            # Multi-stage build: Node (React) + Python (Flask)
  railway.toml          # Railway deployment config
  requirements.txt      # Python dependencies
  backend/              # Flask app, API routes, validators
  frontend/             # React app (Vite)
  scrapers/             # Data scrapers (KenPom, ESPN, NCAA)
  utils/
    db.py               # Shared database utility (SQLite local / PostgreSQL production)
  database/             # SQLite file (local development only)
```

### Multi-stage Dockerfile
Stage 1 builds the React frontend using Node. Stage 2 installs Python, copies the built frontend, and runs Flask via Gunicorn. The final image contains no Node runtime — only the compiled static assets.

---

## Railway Services

| Service | Purpose | Schedule |
|---------|---------|----------|
| main app | Serves Flask API + React frontend | Always on |
| metrics-cron | Runs daily data pipeline | 6:00am ET (10:00 UTC) |

### Required Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `DATABASE_URL` | Both | Auto-injected by Railway PostgreSQL plugin |
| `KENPOM_API_KEY` | cron | KenPom API authentication |
| `BRACKET_FINALIZED` | cron | `false` pre-Selection Sunday, `true` after |

---

## Daily Data Pipeline

The cron service runs `cron.py` every morning at 6am ET. Steps run in order — a failure in one step does not abort the rest.

| Step | Scraper | Role |
|------|---------|------|
| 1 | fetch_data.py | Teams, ratings, four factors from KenPom |
| 2 | fetch_games.py | Game predictions (Fanmatch, last 3 days) |
| 3 | import_bracket_matrix.py | Consensus bracket projection (optional, pre-Selection Sunday) |
| 4 | fetch_momentum_ratings.py | Daily rating snapshots for trajectory |
| 5 | fetch_game_scores_espn.py | Actual scores from ESPN API |
| 6 | calculate_momentum.py | Momentum scores from game results |
| 7 | fetch_historical_four_factors.py | Championship contender scores (optional) |

Required steps failing will exit with code 1 (visible as a failed run in Railway dashboard). Optional steps log a warning and continue.

---

## Local Development

### Prerequisites
- Python 3.12+
- Node 20+
- A `.env` file in the project root

### .env file
```
KENPOM_API_KEY=your_key_here
# Leave DATABASE_URL unset to use local SQLite
```

### Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Build frontend
cd frontend && npm run build && cd ..

# Run Flask dev server
python backend/app.py
```

### Running scrapers locally
```bash
# Full data sync
python scrapers/fetch_data.py

# Specific scrapers
python scrapers/fetch_games.py --days 7
python scrapers/fetch_game_scores_espn.py
python scrapers/calculate_momentum.py

# Test cron without executing
python cron.py --dry-run

# Run full pipeline manually
python cron.py
```

### Local vs Production database
The `utils/db.py` utility auto-detects which database to use:
- **No `DATABASE_URL` set** → uses `database/kenpom.db` (SQLite, local dev)
- **`DATABASE_URL` set** → connects to PostgreSQL (Railway production)

All SQL syntax differences between SQLite and PostgreSQL are handled automatically in `utils/db.py` — scrapers don't need to know which database they're talking to.

---

## Manual Data Updates

Some data sources require manual intervention:

### NCAA Resume Data (NET rankings, quad records)
1. Download `NCAA_Statistics.csv` from NCAA.com
2. Run: `python scrapers/import_ncaa_data.py NCAA_Statistics.csv`

### ESPN Team Branding (logos, colors)
Run once per season or when teams are added:
```bash
python scrapers/fetch_espn_branding.py
```

### Historical Four Factors (championship contender analysis)
Run once to populate historical data (2002–2025), then the cron handles current season scoring:
```bash
python scrapers/fetch_historical_four_factors.py --all
```

---

## Tournament Bracket

### Pre-Selection Sunday
The cron imports the Bracket Matrix consensus projection daily. This reflects the aggregate of all major bracketologists' predictions.

### After Selection Sunday (~March 16)
1. Run the ESPN bracket importer once to load the real field
2. Set `BRACKET_FINALIZED=true` in the Railway cron environment variables
3. The cron will skip bracket imports from that point — the real bracket doesn't change

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search` | GET | Search teams by name (`?q=duke`) |
| `/api/team/:id` | GET | Full team data (ratings, four factors, resume) |
| `/api/compare` | GET | Side-by-side team comparison (`?team1=id&team2=id`) |
| `/api/momentum` | GET | Momentum rankings with tier filters |
| `/api/bracket` | GET | Current bracket with seeds and regions |
| `/api/contenders` | GET | Championship contender tier list |

---

## Security

- Rate limiting on all API endpoints (Flask-Limiter)
- Input validation and sanitization on all query parameters
- CORS configured for production domain only
- Bot protection via request validation middleware
