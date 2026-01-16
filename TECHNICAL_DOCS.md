# Court Vision - Technical Documentation

A guide to understanding how the app works and why decisions were made.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Why These Technologies?](#why-these-technologies)
3. [Data Flow](#data-flow)
4. [Frontend Architecture](#frontend-architecture)
5. [Backend Architecture](#backend-architecture)
6. [Database Design](#database-design)
7. [Key Design Decisions](#key-design-decisions)
8. [Common Patterns](#common-patterns)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                         │
│                     http://localhost:5173                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    VITE DEV SERVER                          │
│                      (Port 5173)                            │
│  • Serves React app                                         │
│  • Hot module replacement                                   │
│  • Proxies /api/* to Flask                                  │
└─────────────────────────┬───────────────────────────────────┘
                          │ /api/* requests
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    FLASK BACKEND                            │
│                      (Port 5000)                            │
│  • REST API endpoints                                       │
│  • Database queries                                         │
│  • JSON responses                                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   SQLITE DATABASE                           │
│                    (kenpom.db)                              │
│  • Teams, ratings, four factors                             │
│  • Resume metrics, bracket data                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Why These Technologies?

### React (Frontend Framework)
**Why React over vanilla JS or other frameworks?**
- Component-based architecture = reusable pieces (TeamCard, StatBar, etc.)
- State management is clean (useState, useEffect hooks)
- Huge ecosystem and community support
- Easy to add features without refactoring everything

**Why Vite over Create React App?**
- 10-100x faster development server startup
- Hot Module Replacement (HMR) that actually works fast
- Modern ES modules, no legacy bundler cruft
- Simpler configuration

### Flask (Backend Framework)
**Why Flask over Django or FastAPI?**
- Lightweight - no boilerplate for a simple API
- Quick to set up and modify
- Perfect for SQLite + JSON responses
- Easy to understand (one file can hold entire API)

**Why not Django?**
- Overkill for this use case (no ORM needed, no admin panel, no auth)
- More complex project structure

**Why not FastAPI?**
- Would be a great choice too (async, auto-docs)
- Flask was simpler for quick iteration

### SQLite (Database)
**Why SQLite over PostgreSQL or MySQL?**
- Zero configuration - just a file
- No separate server process
- Fast for read-heavy workloads (this app mostly reads)
- Easy to backup (copy one file)
- Perfect for ~400 teams and <10,000 rows total

**When would we switch to PostgreSQL?**
- Multiple concurrent users writing data
- Need for complex queries with better optimization
- Deploying to production with multiple servers

---

## Data Flow

### How data gets into the database:

```
KenPom.com ──────────► fetch_data.py ──────────► teams, ratings, four_factors
     │
     └── (API with auth)

ESPN API ────────────► fetch_espn_branding.py ─► teams (logo_url, colors)
     │
     └── (Public API)

Bracket Matrix ──────► import_bracket_matrix.py ► bracket, matchups
     │
     └── (Web scraping)

NCAA Stats CSV ──────► import_ncaa_data.py ─────► resume_metrics
     │
     └── (Manual download)
```

### How data flows to the user:

```
User clicks "Duke" in bracket
        │
        ▼
React calls: fetch('/api/team/73/ratings')
        │
        ▼
Vite proxies to: http://localhost:5000/api/team/73/ratings
        │
        ▼
Flask queries SQLite:
  - SELECT * FROM teams WHERE team_id = 73
  - SELECT * FROM ratings WHERE team_id = 73
  - SELECT * FROM four_factors WHERE team_id = 73
  - SELECT * FROM resume_metrics WHERE team_id = 73
        │
        ▼
Flask returns JSON:
  {
    "team": {...},
    "ratings": {...},
    "four_factors": {...},
    "resume": {...}
  }
        │
        ▼
React receives JSON, updates state
        │
        ▼
TeamCard component re-renders with Duke's data
```

---

## Frontend Architecture

### Component Hierarchy

```
App.jsx
├── Header (title, nav)
├── Routes
│   ├── "/" → CompareView
│   │   ├── SearchBox (×2)
│   │   └── TeamCard (×2)
│   │       ├── Team header (logo, name, record)
│   │       ├── Metrics sections
│   │       └── Resume section
│   │
│   └── "/bracket" → BracketVisualizer
│       ├── RegionTabs
│       ├── RegionBracket (×4)
│       │   └── Matchup (×8 per region)
│       │       └── TeamRow (×2 per matchup)
│       ├── MatchupModal (on click)
│       └── TeamCardModal (on click)
│
└── Footer (status bar)
```

### State Management

**Why useState/useEffect over Redux or Zustand?**
- App is simple enough that prop drilling isn't painful
- No complex state that needs to be shared globally
- React Query would be nice for caching, but fetch + useState works

**Key state patterns:**
```jsx
// Loading states
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);
const [data, setData] = useState(null);

// Fetch on mount
useEffect(() => {
  fetch('/api/something')
    .then(res => res.json())
    .then(setData)
    .catch(setError)
    .finally(() => setLoading(false));
}, []);
```

### Styling Approach

**Why plain CSS over Tailwind or styled-components?**
- Full control over design
- No learning curve for collaborators
- CSS variables make theming easy
- Component-specific CSS files (BracketVisualizer.css)

**CSS Variables (defined in styles.css):**
```css
:root {
  --bg-primary: #0a0a0a;      /* Main background */
  --bg-secondary: #1a1a2e;    /* Card backgrounds */
  --bg-tertiary: #252540;     /* Nested elements */
  --text-primary: #ffffff;    /* Main text */
  --text-secondary: #888;     /* Muted text */
  --accent-primary: #667eea;  /* Purple accent */
  --accent-secondary: #764ba2; /* Gradient end */
  --success: #4ade80;         /* Better stat */
  --error: #ef4444;           /* Bad losses */
}
```

---

## Backend Architecture

### API Design Principles

1. **RESTful endpoints** - Resources as nouns, HTTP verbs for actions
2. **JSON responses** - Consistent structure
3. **Error handling** - Proper status codes (404, 500)
4. **Single responsibility** - Each endpoint does one thing

### Endpoint Patterns

```python
# Simple GET - return one resource
@app.route('/api/team/<int:team_id>/ratings')
def get_team_ratings(team_id):
    # Query database
    # Return JSON or 404

# Query parameters - filtering/searching
@app.route('/api/search')
def search_teams():
    query = request.args.get('q', '')
    # Search and return matches

# Composite endpoint - multiple related resources
@app.route('/api/compare')
def compare_teams():
    team1_id = request.args.get('team1')
    team2_id = request.args.get('team2')
    # Return both teams' full data
```

### Database Connection Pattern

```python
def get_db():
    """Get database connection with Row factory"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row  # Access columns by name
    return db

# Usage in endpoints:
db = get_db()
result = db.execute('SELECT * FROM teams WHERE team_id = ?', (team_id,)).fetchone()
db.close()
return jsonify(dict(result))
```

---

## Database Design

### Entity Relationship

```
teams (1) ─────────────< (many) ratings
  │
  ├──────────────────< (many) four_factors
  │
  ├──────────────────< (many) resume_metrics
  │
  └──────────────────< (many) bracket
                              │
                              └────< matchups
```

### Why Separate Tables?

**Option A (what we did): Normalized tables**
```
teams: id, name, conference, coach, logo_url, colors
ratings: team_id, adj_em, adj_oe, adj_de, tempo, ...
four_factors: team_id, efg_pct, to_pct, or_pct, ...
```

**Option B (alternative): One big table**
```
teams: id, name, conference, adj_em, adj_oe, efg_pct, to_pct, ...
```

**Why Option A?**
- Different update frequencies (ratings daily, team info rarely)
- Cleaner queries when you only need some data
- Easier to add new metric categories
- Matches how the data sources provide it

### Key Design Decisions

**team_id as primary key:**
- Using KenPom's team IDs for consistency
- Allows joining with external data sources

**season column everywhere:**
- Supports historical data
- Can compare across years
- Easy to filter current season

**updated_at timestamps:**
- Track data freshness
- Debug stale data issues

---

## Key Design Decisions

### 1. Vite + React over Babel-in-browser

**Before:** 
```html
<script src="babel.min.js"></script>
<script type="text/babel" src="app.js"></script>
```

**After:**
```
npm run dev → Vite dev server with HMR
```

**Why we changed:**
- Multiple features = multiple files = import/export needed
- Faster development (no browser compilation)
- Better error messages
- Industry standard approach

### 2. Proxy API calls through Vite

**vite.config.js:**
```javascript
proxy: {
  '/api': {
    target: 'http://localhost:5000',
  }
}
```

**Why:**
- Frontend calls `/api/teams` (same origin)
- Vite forwards to Flask at `localhost:5000`
- No CORS issues in development
- Same pattern works in production

### 3. Click team → Matchup first, then TeamCard

**User flow:**
1. Click team in bracket
2. See matchup preview (both teams compared)
3. Click either team for full TeamCard

**Why this order:**
- Matchup context is usually what user wants
- Quick comparison without deep dive
- Full stats available one click away

### 4. Auto-calculated player roles

**Star:** Highest (minutes × usage)
**X-Factor:** Best 3PT% or secondary usage
**Contributor:** Everyone else

**Why auto-calculate:**
- 365 teams × 8 players = 2,920 manual assignments
- Stats-based is objective and consistent
- Can override later if needed

---

## Common Patterns

### Fetching data in React

```jsx
function MyComponent() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/endpoint')
      .then(res => res.json())
      .then(data => {
        setData(data);
        setLoading(false);
      });
  }, []); // Empty deps = run once on mount

  if (loading) return <Spinner />;
  return <div>{/* render data */}</div>;
}
```

### Conditional rendering

```jsx
{loading && <Spinner />}
{error && <Error message={error} />}
{data && <Content data={data} />}
{!data && !loading && <EmptyState />}
```

### Database queries with parameters

```python
# SAFE - parameterized query
cursor.execute('SELECT * FROM teams WHERE name = ?', (user_input,))

# UNSAFE - string interpolation (SQL injection risk!)
cursor.execute(f'SELECT * FROM teams WHERE name = "{user_input}"')
```

### Path resolution in Python

```python
from pathlib import Path

# Get project root from any script location
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
```

---

## Debugging Tips

### Frontend not loading?
1. Check Vite is running: `npm run dev`
2. Check browser console for errors
3. Check Network tab for failed requests

### API returning 404?
1. Check Flask is running: `python backend/app.py`
2. Check endpoint URL spelling
3. Check team_id exists in database

### Data looks stale?
1. Check `updated_at` in database
2. Re-run appropriate scraper
3. Check scraper logs for errors

### Styles not applying?
1. Hard refresh: Ctrl+Shift+R
2. Check CSS file is imported
3. Check class names match

---

## Future Considerations

### If we need authentication:
- Add Flask-Login or JWT tokens
- Protect scraper endpoints
- User-specific saved brackets

### If we need real-time updates:
- WebSockets for live scores
- Server-Sent Events for bracket updates

### If we need better performance:
- React Query for caching
- Database indexes on frequent queries
- Consider PostgreSQL for concurrent writes

### If we deploy to production:
- Build frontend: `npm run build`
- Serve static files from Flask
- Use gunicorn for Flask
- Add environment variables for secrets
