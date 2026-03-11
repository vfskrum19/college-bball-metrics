# NCAA Tournament Analytics App

A full-stack web app for tracking college basketball metrics heading into March Madness. Pulls from KenPom (ratings), ESPN (shooting stats, scores, team branding), and the Bracket Matrix (projected field), and presents it all in an interactive bracket and team card interface.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React (Vite), served as static files by Flask |
| Backend | Flask (Python), Gunicorn |
| Database | PostgreSQL (Railway) |
| Hosting | Railway (app + cron as separate services) |
| Data | KenPom API, ESPN public API, Bracket Matrix |

## Project Structure

```
/
├── backend/
│   └── app.py                  # Flask app factory + all API routes
├── frontend/
│   └── src/
│       └── components/
│           ├── BracketVisualizer.jsx
│           ├── compare/TeamCard.jsx
│           └── player/PlayerCard.jsx
├── scrapers/
│   ├── fetch_data.py                   # KenPom ratings + teams
│   ├── fetch_games.py                  # Fanmatch predictions
│   ├── fetch_game_scores_espn.py       # Actual game scores
│   ├── fetch_momentum_ratings.py       # Daily rating snapshots
│   ├── calculate_momentum.py           # Momentum score computation
│   ├── fetch_historical_four_factors.py
│   ├── import_bracket_matrix.py        # Projected bracket (pre-Selection Sunday)
│   ├── fetch_espn_shooting_stats.py    # 3PT%, FT%, FT Rate, 3PA Rate
│   └── fetch_espn_branding.py          # Team logos + colors (manual)
├── utils/
│   └── db.py                           # DB connection + SQLite→PostgreSQL translation
├── cron.py                             # Daily pipeline runner
├── Dockerfile                          # Multi-stage: Node build + Python runtime
└── railway.toml
```

## Daily Pipeline (cron.py)

Runs at 6:00am ET via Railway cron service (`0 10 * * *`).

| Step | Scraper | Type |
|------|---------|------|
| 1 | fetch_data.py | Required |
| 2 | fetch_games.py | Required |
| 3 | import_bracket_matrix.py | Optional (skipped after `BRACKET_FINALIZED=true`) |
| 4 | fetch_momentum_ratings.py | Required |
| 5 | fetch_game_scores_espn.py | Required |
| 6 | calculate_momentum.py | Required |
| 7 | fetch_historical_four_factors.py | Optional |
| 8 | fetch_espn_shooting_stats.py | Optional |

Required steps failing exits the pipeline with code 1 (Railway flags the run). Optional steps log a warning and continue — stale data is acceptable, a broken pipeline is not.

## API Endpoints

All routes live inside `create_app()` — required by the application factory pattern.

| Endpoint | Description |
|----------|-------------|
| `GET /api/bracket` | Full bracket with all regions and seeds |
| `GET /api/team/<id>/ratings` | KenPom ratings, resume, momentum |
| `GET /api/team/<id>/shooting` | ESPN shooting stats (3PT%, FT%, rates) |
| `GET /api/team/<id>/resume-games` | Quality wins + notable losses with game context |
| `GET /api/players/<id>` | Key players for a team |
| `GET /api/contenders` | Championship contender scores |
| `GET /api/search?q=` | Team name search (case-insensitive) |

### Shooting Stats API Shape

Rates are stored as decimals, displayed as percentages — multiply × 100 in the frontend:

```json
{
  "shooting": {
    "three_point_pct": 34.1,
    "three_point_rate": 0.429,
    "free_throw_pct": 72.6,
    "ft_rate": 0.374,
    "opp_fg3_pct": null,
    "updated_at": "2026-03-10 11:01:30"
  }
}
```

## Local Development

```bash
# Install Python deps
pip install -r requirements.txt

# Install frontend deps
cd frontend && npm install

# Build frontend (Flask serves the built files)
npm run build

# Set DATABASE_URL in .env (points to Railway PostgreSQL)
# Run Flask dev server
python backend/app.py
```

Run a scraper manually:
```bash
python scrapers/fetch_espn_shooting_stats.py
python cron.py --dry-run   # print steps without executing
```

## Railway Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | Both | Auto-injected by Railway PostgreSQL plugin |
| `KENPOM_API_KEY` | Cron | KenPom API authentication |
| `BRACKET_FINALIZED` | Cron | Set `true` on Selection Sunday to skip bracket import |

## Key Design Decisions

**ESPN ID mapping** — ESPN uses internal team IDs completely different from KenPom's. The shooting scraper fetches ESPN's full team list first, matches teams by name (manual mappings + fuzzy matching at 0.82 threshold), then uses ESPN's ID for per-team stats calls.

**`IF NOT EXISTS` for schema migrations** — all `ALTER TABLE ADD COLUMN` statements use `IF NOT EXISTS` rather than try/except. This prevents bare exception handlers from silently swallowing real errors (permissions issues, typos, etc.) while still being safe to re-run.

**Required vs optional pipeline steps** — steps where failure would break the user experience (ratings, momentum, games) are required and exit with code 1. Steps like shooting stats and contender scores are optional — a failure just means slightly stale data.

**Flat API shapes** — the shooting endpoint returns a flat object rather than nested `three_point: { pct, made, att }`. Simpler to consume and easier to change individual fields without breaking consumers.

## Selection Sunday Checklist (~March 16)

1. ESPN publishes real bracket ~6pm ET
2. Run `import_espn_bracket.py` once (builds out the real bracket in DB)
3. Set `BRACKET_FINALIZED=true` in Railway cron environment
4. Cron skips Bracket Matrix import from that point forward