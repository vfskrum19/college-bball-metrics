# KenPom App — Development Progress Summary
Last updated: 2026-03-06

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

---

## Active Branch: feature/team-card-redesign
**Created: 2026-03-06** — branched from main after production was confirmed stable.
**Do not merge to main until frontend work is complete and tested.**

### Goal
Redesign team cards and matchup view to:
- Remove KenPom Four Factors from public display (paywall data)
- Replace with ESPN-sourced shooting stats (3PT%, FT%)
- Add quality wins / notable losses with game context to resume section
- Keep KenPom ranking numbers (free tier) but drop raw efficiency values

### What's Been Built on This Branch

#### New scraper: `scrapers/fetch_espn_shooting_stats.py`
- Fetches ESPN's full team list to get ESPN's internal IDs (different from KenPom IDs)
- Matches 356/365 teams by name (98%) using manual mappings + fuzzy matching
- Remaining 9 unmatched are programs not in ESPN's system (Lindenwood, Southern Indiana etc.) — none are tournament teams
- Adds columns to teams table: `fg3_pct`, `fg3_made`, `fg3_att`, `ft_pct`, `ft_made`, `ft_att`, `opp_fg3_pct`, `ft_rate`, `shooting_updated_at`
- Self-migrating: runs `ALTER TABLE ADD COLUMN` on startup, safe to run repeatedly
- Key lesson: ESPN's `displayName` always includes mascot (e.g. "Ball State Cardinals") — manual mappings must include full name or fuzzy match falls below 0.82 threshold

#### New API endpoints in `backend/app.py`
Both endpoints live inside `create_app()` — required by the application factory pattern.

**`GET /api/team/<id>/shooting`**
- Returns ESPN shooting stats for a team
- Returns `shooting: null` with message if scraper hasn't run yet (frontend shows loading state)
- Replaces Four Factors section on team cards

**`GET /api/team/<id>/resume-games`**
- Returns quality wins (top 5 by opponent NET rank) and notable losses (top 3)
- Each game includes: opponent name/logo/NET rank, home/away indicator ("vs" or "@"), date, score
- Losses flagged `is_bad_loss: true` if opponent NET rank > 100
- Limits capped server-side (max 10 wins, 8 losses) — callers can override via query params
- Uses UNION ALL to handle both home and away games in a single query

#### Updated `cron.py`
- Added `fetch_espn_shooting_stats` as Step 8 (optional)
- Runs last — slowest optional step (~2 min for 356 HTTP calls), all critical steps finish first
- Failure raises RuntimeError which cron catches, logs, and continues without aborting pipeline

### What's Next (Frontend)
The data pipeline is fully built. Remaining work is all React component changes:

1. **Team card shooting section** — replace Four Factors UI with new shooting stats
   - Call `/api/team/<id>/shooting` instead of reading from four_factors
   - Display: Team 3PT% | Opp 3PT% allowed | Team FT% | FT Rate
   - Show "Stats loading..." if data is null

2. **Resume section expansion** — add quality wins/losses with game context
   - Call `/api/team/<id>/resume-games` 
   - Display each win/loss with: opponent logo, "@"/"vs" indicator, date, score, opponent NET rank
   - Cap display at 5 wins / 3 losses (matches ESPN bracket breakdown style)
   - Flag bad losses in red

3. **Remove raw efficiency values** — show KenPom rank badges only, drop decimal values
   - Keep: `#10 KenPom`, `#8 NET`, rank badges on AdjEM/ORtg/DRtg/Tempo
   - Remove: raw values like `29.2`, `123.6`, `94.4` from the efficiency section

4. **Trim contributors list** — cap at 4 players (currently shows 6, bottom 2 add no value)

### Files Changed on This Branch
| File | Change |
|------|--------|
| `backend/app.py` | Added `/api/team/<id>/shooting` and `/api/team/<id>/resume-games` endpoints; added `/api/contenders` endpoint that was missing |
| `cron.py` | Added fetch_espn_shooting_stats as optional Step 8 |
| `scrapers/fetch_espn_shooting_stats.py` | New file |

---

## Future Work
- import_espn_bracket.py — real bracket importer from ESPN API
- Stylistic team profile algorithm (pace, shot profile, defense type → matchup narrative)
- cron_players.py — separate Railway cron for player stats
- SendGrid email alerts on cron failure (deferred, using Railway logs for now)
- README rewrite to reflect production architecture