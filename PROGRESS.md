# KenPom App — Development Progress Summary
Last updated: 2026-03-10

## Architecture
- **Frontend:** React (Vite), served as static files by Flask
- **Backend:** Flask (Python), Gunicorn on Railway
- **Database:** PostgreSQL on Railway (migrated from SQLite)
- **Automation:** metrics-cron service on Railway, runs daily at 6am ET (10:00 UTC)

## Repository Structure
```
project root/
  cron.py                          # Daily pipeline runner
  Dockerfile                       # Multi-stage: Node build + Python runtime
  railway.toml                     # Railway config
  requirements.txt
  backend/                         # Flask app
  frontend/                        # React app
  scrapers/                        # All data scrapers
  utils/
    db.py                          # Shared DB utility (SQLite/PostgreSQL)
  database/                        # SQLite file (local dev only)
```

## Railway Services
| Service | Purpose | Start Command | Schedule |
|---------|---------|---------------|----------|
| main app | Flask + React | via Dockerfile CMD | always on |
| metrics-cron | Daily data update | python cron.py | 0 10 * * * |

### Cron Environment Variables
| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Auto-injected by Railway PostgreSQL plugin |
| `KENPOM_API_KEY` | KenPom API key |
| `BRACKET_FINALIZED` | `false` until Selection Sunday (~March 16), then `true` |

## Scrapers
All scrapers use `utils/db.py` for database connections.

| File | Purpose | Cron Role |
|------|---------|-----------|
| fetch_data.py | Teams, ratings, four factors | Required |
| fetch_games.py | Fanmatch predictions | Required |
| fetch_momentum_ratings.py | Rating snapshots | Required |
| fetch_game_scores_espn.py | Actual game scores | Required |
| calculate_momentum.py | Momentum scores | Required |
| import_bracket_matrix.py | Projected bracket (pre-Selection Sunday) | Optional |
| fetch_historical_four_factors.py | Historical FF + contender scores | Optional |
| fetch_espn_shooting_stats.py | Team 3PT%, FT%, opp 3PT%, FT rate | Optional |
| fetch_espn_branding.py | Team logos/colors | Manual |
| import_ncaa_data.py | NET rank, quad records | Manual (CSV download) |

## utils/db.py — Automatic SQLite->PostgreSQL Conversions
All handled in _pg_sql() — every scraper gets these automatically:

| SQLite | PostgreSQL | Reason |
|--------|-----------|--------|
| ? | %s | Parameter placeholder syntax |
| date('now') | CURRENT_DATE | Date function syntax |
| game_date < CURRENT_DATE | game_date::date < CURRENT_DATE | TEXT vs DATE type |
| INTEGER PRIMARY KEY AUTOINCREMENT | SERIAL PRIMARY KEY | Auto-increment syntax |
| LIKE | ILIKE | SQLite LIKE is case-insensitive, PostgreSQL is not |
| INSERT OR REPLACE | INSERT ... ON CONFLICT DO UPDATE | Upsert syntax |

### insert_or_replace() — Composite Unique Keys
Tables with composite unique constraints need conflict_columns specified.
Tables already fixed:
- ratings_archive -> ['team_id', 'season', 'archive_date']
- historical_four_factors -> ['season', 'team_name']
- final_four_analysis -> ['metric']
- contender_scores -> ['team_id', 'season']

## Production Status (as of 2026-03-10)
- Daily cron running clean — 8 steps (7 required + 1 optional shooting stats)
- Game score backfill complete (Nov 2025 - Mar 2026)
- Momentum calculator accurate with full game history
- Bracket Matrix projected field updating daily
- Team cards: shooting profile live (3PT%, 3PA Rate, FT%, FT Rate)
- Resume section: quality wins / notable losses with game context
- Search bar working case-insensitively
- CompareView working correctly
- ESPN shooting stats scraped for 319/365 teams (87%); remainder are small programs outside tournament

## Bugs Fixed During Migration
| Bug | Fix |
|-----|-----|
| fetch_games.py had db.py contents pasted into it | Replaced with correct file |
| Python True/False for INTEGER columns in fetch_data.py | Changed to 1/0 |
| insert_or_replace() always conflicted on first column only | Added conflict_columns param |
| Dockerfile missing scrapers/utils/cron.py | Added COPY lines to Stage 2 |
| AUTOINCREMENT in CREATE TABLE statements | Handled in _pg_sql() |
| ratings_archive duplicate rows blocking unique constraint | fix_ratings_archive.py one-time script |
| Search bar case sensitive (LIKE) | LIKE -> ILIKE in _pg_sql() |

## Selection Sunday Checklist (~March 16)
1. ESPN publishes real bracket ~6pm ET
2. Run import_espn_bracket.py once (not yet built)
3. Set BRACKET_FINALIZED=true in Railway cron environment variables
4. Cron skips Bracket Matrix import from that point forward

---

## Branch: feature/team-card-redesign → MERGED TO MAIN (2026-03-10)

### What Was Built

#### `scrapers/fetch_espn_shooting_stats.py`
- Fetches ESPN's full team list to get ESPN's internal IDs (different from KenPom IDs)
- Matches 356/365 teams by name (98%) using manual mappings + fuzzy matching
- Adds columns to teams table: `fg3_pct`, `fg3_att`, `fg3_rate`, `ft_pct`, `ft_att`, `ft_rate`, `opp_fg3_pct`, `shooting_updated_at`
- `fg3_rate` = 3PA/FGA (shot profile metric), `ft_rate` = FTA/FGA (aggressiveness at rim)
- Self-migrating: uses `ALTER TABLE ADD COLUMN IF NOT EXISTS` — safe to re-run
- Key fix: switched from bare `except Exception: pass` to `IF NOT EXISTS` to stop silently swallowing real DB errors

#### API changes (`backend/app.py`)
**`GET /api/team/<id>/shooting`** — flat response shape:
```json
{ "three_point_pct": 34.1, "three_point_rate": 0.429, "free_throw_pct": 72.6, "ft_rate": 0.374, "opp_fg3_pct": null }
```
- Rates stored as decimals (0.374), displayed as percentages (37.4%) — multiply × 100 in frontend
- Percentages stored as whole numbers (34.1), display as-is with `%` suffix

**`GET /api/team/<id>/resume-games`** — quality wins + notable losses with game context

#### Frontend (`TeamCard.jsx`, `BracketVisualizer.jsx`)
- Replaced Four Factors section with Shooting Profile (3PT%, 3PA Rate, FT%, FT Rate)
- Removed season totals (made/att) from display — rates tell the story
- `(FTA/FGA)` and `(3PA/FGA)` descriptors moved inline to label side
- `BracketVisualizer` matchup modal updated to flat API shape + added 3PA Rate and FT Rate rows
- `SectionErrorBoundary` class component added — catches render errors in ShootingProfile/ResumeGames, shows fallback instead of crashing whole card
- Resume section: quality wins and notable losses with opponent logo, location, NET rank, score, date; bad losses flagged red

#### `cron.py`
- Step 8 (optional): `fetch_espn_shooting_stats` — runs last, ~2 min for 356 HTTP calls
- Failure logged and skipped without aborting pipeline (stale shooting stats are acceptable)

### Files Changed
| File | Change |
|------|--------|
| `scrapers/fetch_espn_shooting_stats.py` | New — ESPN shooting stats scraper |
| `backend/app.py` | New shooting + resume-games endpoints; flat API shape; fg3_rate added |
| `cron.py` | Step 8 added |
| `frontend/src/components/TeamCard.jsx` | Full shooting profile section rewrite |
| `frontend/src/components/BracketVisualizer.jsx` | Shooting StatBars updated to flat API shape |

---

## Future Work
- **import_espn_bracket.py** — real bracket importer from ESPN API (needed for Selection Sunday)
- **Team narrative engine** — generate a one-paragraph scouting report per team based on shot profile, pace, defensive style, and resume strength; display on team card and matchup modal
- **Clickable opponent links** — resume game rows link to that opponent's team card
- **cron_players.py** — separate Railway cron for player stats
- **SendGrid email alerts** on cron failure (deferred, using Railway logs for now)
- **Rate limiting + bot protection** — add to Flask API before any public launch