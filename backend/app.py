from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os
from pathlib import Path

# Get paths relative to this file
BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'

app = Flask(__name__, 
            static_folder=str(FRONTEND_DIR / 'static'),
            static_url_path='/static')
CORS(app)

@app.route('/')
def serve_index():
    """Serve the main index.html file"""
    return send_from_directory(str(FRONTEND_DIR), 'index.html')

def get_db():
    """Get database connection"""
    db = sqlite3.connect(str(DATABASE))
    db.row_factory = sqlite3.Row
    return db

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
        
        # Check if resume_metrics table exists
        try:
            resume = db.execute(
                'SELECT * FROM resume_metrics WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
                (team_id,)
            ).fetchone()
        except:
            resume = None
        
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
    # Check if database exists
    if not DATABASE.exists():
        print(f"ERROR: Database not found at {DATABASE}")
        print("Run: python setup.py")
        exit(1)
    
    print(f"Using database: {DATABASE}")
    print("Starting Flask server on http://localhost:5000")
    app.run(debug=True, port=5000)