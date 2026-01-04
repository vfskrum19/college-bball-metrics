# Court Vision - KenPom Team Comparison Tool

A web application for comparing college basketball teams using KenPom analytics. Features a local database for fast access and a beautiful UI for side-by-side team comparisons.

## Features

- 🏀 Compare any two college basketball teams side-by-side
- 📊 View KenPom ratings: AdjEM, AdjOE, AdjDE, Tempo, SOS
- 🎯 Four Factors analysis (offensive metrics)
- 🔍 Fast team search with autocomplete
- 💾 Local SQLite database for quick access
- 🎨 Distinctive, modern UI design
- 📈 Historical tracking support (archive snapshots)

## Architecture

```
┌─────────────┐
│   Browser   │  ← React Frontend (index.html)
│             │
│  Court      │
│  Vision     │
└──────┬──────┘
       │
       │ HTTP
       ▼
┌─────────────┐
│   Flask     │  ← Python Backend (app.py)
│   API       │
│  :5000      │
└──────┬──────┘
       │
       │ SQL
       ▼
┌─────────────┐
│   SQLite    │  ← Local Database (kenpom.db)
│  Database   │
└──────┬──────┘
       ▲
       │
┌──────┴──────┐
│  KenPom     │  ← Data Fetcher (fetch_data.py)
│  API Sync   │
└─────────────┘
```

## Setup Instructions

### 1. Prerequisites

- Python 3.8+ installed
- KenPom API subscription with API key
- Modern web browser

### 2. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt
```

### 3. Configure API Key

Open `fetch_data.py` and replace the API key placeholder:

```python
KENPOM_API_KEY = "your_actual_api_key_here"
```

### 4. Initialize Database & Fetch Data

```bash
# First run: creates database and syncs all data
python fetch_data.py

# This will:
# - Create kenpom.db
# - Fetch all teams for 2025 season
# - Fetch current ratings
# - Fetch four factors
# - Fetch preseason data
```

**Note:** The initial sync takes about 30-60 seconds due to API rate limiting.

### 5. Start the Backend

```bash
python app.py
```

Server will start at `http://localhost:5000`

### 6. Open the Frontend

Simply open `index.html` in your web browser. The app will connect to your local backend automatically.

## Usage

### Daily Updates

Run this command once per day during the season to keep data fresh:

```bash
python fetch_data.py
```

### Individual Updates

You can update specific data types:

```bash
# Update only teams
python fetch_data.py teams

# Update only ratings
python fetch_data.py ratings

# Update only four factors
python fetch_data.py four-factors

# Save a historical snapshot
python fetch_data.py archive 2025-01-15
```

### Using the App

1. **Search Teams**: Type team names in either search box
2. **Select Teams**: Click on suggestions to select teams
3. **View Comparison**: Metrics appear side-by-side automatically
4. **Compare Metrics**: 
   - Lower rank numbers are better
   - AdjEM = Overall team strength
   - AdjOE = Offensive efficiency (higher is better)
   - AdjDE = Defensive efficiency (lower is better)
   - Tempo = Pace of play

## API Endpoints

Your local Flask server provides these endpoints:

- `GET /api/teams` - List all teams
- `GET /api/teams?conference=ACC` - Filter by conference
- `GET /api/conferences` - List all conferences
- `GET /api/team/{id}/ratings` - Get team data
- `GET /api/compare?team1={id}&team2={id}` - Compare two teams
- `GET /api/search?q={query}` - Search teams by name
- `GET /api/status` - Database status

## Database Schema

### Teams Table
- Basic team info (name, conference, coach, arena)

### Ratings Table
- Current KenPom ratings and rankings
- Efficiency metrics (AdjEM, AdjOE, AdjDE)
- Tempo and adjusted tempo
- Strength of schedule metrics
- Luck rating

### Four Factors Table
- eFG% (Effective Field Goal %)
- TO% (Turnover %)
- OR% (Offensive Rebounding %)
- FT Rate (Free Throw Rate)
- Plus defensive versions of each

### Ratings Archive Table
- Historical snapshots
- Track team improvement/decline over season
- Preseason ratings

## Customization

### Update Season
Change `CURRENT_SEASON` in `fetch_data.py`:
```python
CURRENT_SEASON = 2026  # For 2025-26 season
```

### Add More Metrics
The KenPom API provides many more endpoints (point distribution, height, misc stats). You can:
1. Add new tables in `app.py` → `init_db()`
2. Add fetch functions in `fetch_data.py`
3. Update the UI in `index.html` to display new metrics

### Styling
All CSS is in `<style>` section of `index.html`. Color scheme uses CSS variables:
- `--primary`: Main accent color (orange)
- `--secondary`: Blue accent
- `--accent`: Gold/yellow
- `--dark`: Background dark
- `--light`: Text color

## Troubleshooting

**"403 Forbidden" when fetching data**
- Check your API key is correct
- Verify your KenPom subscription includes API access

**"No data available" in cards**
- Run `python fetch_data.py` to sync data
- Check console for errors

**Search not working**
- Make sure Flask backend is running on port 5000
- Check browser console for CORS errors

**Database locked errors**
- Close any other Python processes accessing the database
- Delete `kenpom.db` and re-sync

## Future Enhancements

Ideas for extending this app:
- [ ] Add historical trend charts
- [ ] Game predictions using fanmatch endpoint
- [ ] Conference comparisons
- [ ] Export comparisons as PDF/image
- [ ] Player statistics (if API provides)
- [ ] Mobile-responsive design improvements
- [ ] Dark/light theme toggle
- [ ] Favorite teams list
- [ ] Schedule automatic daily updates

## License

This is a personal project for educational purposes. Respect KenPom's terms of service when using their API.

## Credits

- Data from [KenPom.com](https://kenpom.com)
- Built with Flask, React, and SQLite
- Design inspired by modern sports analytics platforms
