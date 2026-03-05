# KenPom App — Development Progress Summary
Last updated: 2026-03-05

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

## Scrapers Converted to PostgreSQL
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

## Production Status (as of 2026-03-05)
- Daily cron running clean (confirmed morning of 2026-03-05)
- All 7 pipeline steps completing successfully
- Game score backfill complete (Nov 2025 - Mar 2026)
- Momentum calculator accurate with full game history
- Bracket Matrix projected field updating daily
- Team cards populating correctly (ratings, four factors, resume)
- Search bar working case-insensitively
- CompareView working correctly

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

## Future Work
- import_espn_bracket.py — real bracket importer from ESPN API
- cron_players.py — separate Railway cron for player stats
- SendGrid email alerts on cron failure (deferred, using Railway logs for now)
- README rewrite to reflect production architecture
