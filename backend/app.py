from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)  # Enable CORS for React frontend

DATABASE = 'kenpom.db'

@app.route('/')
def serve_index():
    """Serve the main index.html file"""
    return send_from_directory('.', 'index.html')

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize the database with schema"""
    db = get_db()
    cursor = db.cursor()
    
    # Teams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            conference TEXT,
            coach TEXT,
            arena TEXT,
            arena_city TEXT,
            arena_state TEXT,
            season INTEGER,
            primary_color TEXT,
            secondary_color TEXT,
            logo_url TEXT
        )
    ''')
    
    # Current ratings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            data_through TEXT,
            wins INTEGER,
            losses INTEGER,
            adj_em REAL,
            rank_adj_em INTEGER,
            adj_oe REAL,
            rank_adj_oe INTEGER,
            adj_de REAL,
            rank_adj_de INTEGER,
            tempo REAL,
            rank_tempo INTEGER,
            adj_tempo REAL,
            rank_adj_tempo INTEGER,
            luck REAL,
            rank_luck INTEGER,
            sos REAL,
            rank_sos INTEGER,
            ncsos REAL,
            rank_ncsos INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Four factors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS four_factors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            data_through TEXT,
            efg_pct REAL,
            rank_efg_pct INTEGER,
            to_pct REAL,
            rank_to_pct INTEGER,
            or_pct REAL,
            rank_or_pct INTEGER,
            ft_rate REAL,
            rank_ft_rate INTEGER,
            defg_pct REAL,
            rank_defg_pct INTEGER,
            dto_pct REAL,
            rank_dto_pct INTEGER,
            dor_pct REAL,
            rank_dor_pct INTEGER,
            dft_rate REAL,
            rank_dft_rate INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    # Archive ratings table for historical tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season INTEGER,
            archive_date TEXT,
            is_preseason BOOLEAN,
            adj_em REAL,
            rank_adj_em INTEGER,
            adj_oe REAL,
            rank_adj_oe INTEGER,
            adj_de REAL,
            rank_adj_de INTEGER,
            adj_tempo REAL,
            rank_adj_tempo INTEGER,
            FOREIGN KEY (team_id) REFERENCES teams (team_id)
        )
    ''')
    
    db.commit()
    db.close()
    print("Database initialized successfully!")

# API Endpoints

@app.route('/api/teams', methods=['GET'])
def get_teams():
    """Get all teams, optionally filtered by conference"""
    conference = request.args.get('conference')
    season = request.args.get('season', 2026)
    
    db = get_db()
    if conference:
        teams = db.execute(
            'SELECT * FROM teams WHERE conference = ? AND season = ? ORDER BY name',
            (conference, season)
        ).fetchall()
    else:
        teams = db.execute(
            'SELECT * FROM teams WHERE season = ? ORDER BY name',
            (season,)
        ).fetchall()
    
    db.close()
    return jsonify([dict(team) for team in teams])

@app.route('/api/conferences', methods=['GET'])
def get_conferences():
    """Get list of conferences"""
    season = request.args.get('season', 2026)
    
    db = get_db()
    conferences = db.execute(
        'SELECT DISTINCT conference FROM teams WHERE season = ? ORDER BY conference',
        (season,)
    ).fetchall()
    
    db.close()
    return jsonify([conf['conference'] for conf in conferences if conf['conference']])

@app.route('/api/team/<int:team_id>/ratings', methods=['GET'])
def get_team_ratings(team_id):
    """Get current ratings for a specific team"""
    db = get_db()
    
    # Get team info
    team = db.execute(
        'SELECT * FROM teams WHERE team_id = ?',
        (team_id,)
    ).fetchone()
    
    if not team:
        db.close()
        return jsonify({'error': 'Team not found'}), 404
    
    # Get latest ratings
    ratings = db.execute(
        'SELECT * FROM ratings WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
        (team_id,)
    ).fetchone()
    
    # Get four factors
    four_factors = db.execute(
        'SELECT * FROM four_factors WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
        (team_id,)
    ).fetchone()
    
    db.close()
    
    return jsonify({
        'team': dict(team) if team else None,
        'ratings': dict(ratings) if ratings else None,
        'four_factors': dict(four_factors) if four_factors else None
    })

@app.route('/api/compare', methods=['GET'])
def compare_teams():
    """Compare two teams side by side"""
    team1_id = request.args.get('team1', type=int)
    team2_id = request.args.get('team2', type=int)
    
    if not team1_id or not team2_id:
        return jsonify({'error': 'Both team1 and team2 parameters required'}), 400
    
    db = get_db()
    
    # Get data for both teams
    teams_data = []
    for team_id in [team1_id, team2_id]:
        team = db.execute('SELECT * FROM teams WHERE team_id = ?', (team_id,)).fetchone()
        ratings = db.execute(
            'SELECT * FROM ratings WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
            (team_id,)
        ).fetchone()
        four_factors = db.execute(
            'SELECT * FROM four_factors WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
            (team_id,)
        ).fetchone()
        resume = db.execute(
            'SELECT * FROM resume_metrics WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
            (team_id,)
        ).fetchone()
        
        teams_data.append({
            'team': dict(team) if team else None,
            'ratings': dict(ratings) if ratings else None,
            'four_factors': dict(four_factors) if four_factors else None,
            'resume': dict(resume) if resume else None
        })
    
    db.close()
    
    return jsonify({
        'team1': teams_data[0],
        'team2': teams_data[1]
    })

@app.route('/api/team/<int:team_id>/history', methods=['GET'])
def get_team_history(team_id):
    """Get historical ratings for a team throughout the season"""
    db = get_db()
    
    history = db.execute(
        '''SELECT archive_date, adj_em, rank_adj_em, adj_oe, adj_de, adj_tempo
           FROM ratings_archive 
           WHERE team_id = ? 
           ORDER BY archive_date ASC''',
        (team_id,)
    ).fetchall()
    
    db.close()
    
    return jsonify([dict(row) for row in history])

@app.route('/api/search', methods=['GET'])
def search_teams():
    """Search teams by name"""
    query = request.args.get('q', '').strip()
    season = request.args.get('season', 2026)
    
    if not query:
        return jsonify([])
    
    db = get_db()
    teams = db.execute(
        '''SELECT t.*, r.rank_adj_em, r.adj_em
           FROM teams t
           LEFT JOIN ratings r ON t.team_id = r.team_id
           WHERE t.name LIKE ? AND t.season = ?
           ORDER BY t.name
           LIMIT 20''',
        (f'%{query}%', season)
    ).fetchall()
    
    db.close()
    
    return jsonify([dict(team) for team in teams])

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get database status and last update time"""
    db = get_db()
    
    team_count = db.execute('SELECT COUNT(*) as count FROM teams').fetchone()['count']
    last_update = db.execute(
        'SELECT MAX(updated_at) as last_update FROM ratings'
    ).fetchone()['last_update']
    
    db.close()
    
    return jsonify({
        'teams_count': team_count,
        'last_update': last_update,
        'status': 'online'
    })

if __name__ == '__main__':
    # Initialize database if it doesn't exist
    if not os.path.exists(DATABASE):
        print("Creating database...")
        init_db()
    
    print("Starting Flask server on http://localhost:5000")
    app.run(debug=True, port=5000)