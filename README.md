# Court Vision 🏀

A metrics-driven NCAA basketball analysis tool featuring team comparisons, tournament bracket visualization, and advanced KenPom statistics.

![Court Vision](https://img.shields.io/badge/React-18-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![SQLite](https://img.shields.io/badge/SQLite-3-orange)

## Features

### 📊 Team Comparison Tool
Compare any two teams side-by-side with comprehensive metrics:
- KenPom efficiency ratings (AdjEM, AdjO, AdjD)
- Four Factors analysis (eFG%, TO%, OR%, FT Rate)
- Strength of Schedule rankings
- Tournament resume (Quad 1-4 records, NET ranking)
- Team colors and logos

### 🏆 Interactive Bracket Visualizer
Explore the projected NCAA Tournament bracket:
- Bracket Matrix consensus seedings (68 teams)
- All four regions with proper bracket structure
- First Four play-in games
- Click any team for detailed stats
- Matchup previews with head-to-head comparisons
- KenPom-based game projections

## Screenshots

*Team Comparison View*
- Side-by-side team cards with color-coded metrics
- Search with autocomplete for 365+ teams

*Bracket View*
- ESPN-style matchup boxes
- Region tabs for focused viewing
- Click-through to team details and matchup analysis

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React 18 + Vite | Fast, modern UI with hot reload |
| Backend | Flask + Flask-CORS | REST API serving JSON data |
| Database | SQLite | Lightweight, file-based storage |
| Styling | CSS3 | Custom dark theme, responsive design |

## Project Structure

```
kenpom-app/
├── backend/
│   └── app.py                 # Flask API server
├── database/
│   ├── init_db.py            # Database schema
│   └── kenpom.db             # SQLite database
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main app with routing
│   │   ├── styles.css        # Global styles
│   │   └── components/
│   │       ├── compare/
│   │       │   ├── CompareView.jsx
│   │       │   └── TeamCard.jsx
│   │       └── bracket/
│   │           ├── BracketVisualizer.jsx
│   │           └── BracketVisualizer.css
│   ├── package.json
│   └── vite.config.js
├── scrapers/
│   ├── fetch_data.py         # KenPom team/ratings data
│   ├── fetch_espn_branding.py # Team logos and colors
│   ├── import_bracket_matrix.py # Tournament projections
│   └── import_ncaa_data.py   # Quad records from NCAA
├── data/
│   ├── bracket_matrix.json   # Cached bracket data
│   └── NCAA_Statistics.csv   # NCAA team statistics
├── utils/
│   └── verify_database.py    # Data validation
├── setup.py                  # Full setup automation
├── requirements.txt          # Python dependencies
└── README.md
```

## Installation

### Prerequisites
- Python 3.12+
- Node.js 20+
- KenPom subscription (for data fetching)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/kenpom-app.git
   cd kenpom-app
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Configure API key**
   - Open `scrapers/fetch_data.py`
   - Add your KenPom API key to `KENPOM_API_KEY`

5. **Run initial setup**
   ```bash
   python setup.py
   ```
   This will:
   - Initialize the database
   - Fetch KenPom ratings
   - Fetch ESPN team branding
   - Import NCAA quad records
   - Import Bracket Matrix projections

## Running the App

**Start both servers:**

Terminal 1 - Backend:
```bash
python backend/app.py
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/teams` | GET | List all teams |
| `/api/team/<id>/ratings` | GET | Full team stats |
| `/api/compare?team1=X&team2=Y` | GET | Compare two teams |
| `/api/search?q=query` | GET | Search teams by name |
| `/api/bracket` | GET | Full tournament bracket |
| `/api/bracket/region/<name>` | GET | Single region data |
| `/api/matchup/<id>` | GET | Matchup details |
| `/api/status` | GET | Database status |

## Data Sources

| Source | Data | Update Frequency |
|--------|------|------------------|
| KenPom | Efficiency ratings, Four Factors, tempo | Daily during season |
| ESPN | Team logos, colors | Once per season |
| Bracket Matrix | Tournament projections (consensus of 100+ brackets) | Daily during bracket season |
| NCAA | Quad records, NET rankings | Weekly |

## Database Schema

```
teams           - Team info (name, conference, coach)
ratings         - KenPom efficiency metrics
four_factors    - Offensive/defensive four factors
resume_metrics  - Quad records, NET ranking
bracket         - Tournament seedings by region
matchups        - First round game pairings
```

## Development

### Branch Strategy
- `main` - Stable, production-ready code
- `feature/*` - Individual feature development

### Adding Features
1. Create feature branch: `git checkout -b feature/your-feature`
2. Develop and test
3. Commit often with clear messages
4. Merge to main when complete

### Updating Data
```bash
# Refresh KenPom data
python scrapers/fetch_data.py

# Update bracket projections
python scrapers/import_bracket_matrix.py

# Update quad records (requires fresh CSV)
python scrapers/import_ncaa_data.py data/NCAA_Statistics.csv
```

## Roadmap

- [x] Team comparison tool
- [x] Bracket visualizer
- [x] Matchup previews
- [ ] Player cards (top contributors per team)
- [ ] Game preview generator
- [ ] Conference strength ratings
- [ ] Momentum tracker (last 10 games)
- [ ] Historical comparisons

## Contributing

Pull requests welcome! Please follow the existing code style and test thoroughly.

## License

MIT License - feel free to use and modify.

## Acknowledgments

- [KenPom](https://kenpom.com) - Advanced college basketball metrics
- [Bracket Matrix](https://bracketmatrix.com) - Tournament projection consensus
- [ESPN](https://espn.com) - Team branding assets
- [NCAA](https://ncaa.com) - Official statistics

---
