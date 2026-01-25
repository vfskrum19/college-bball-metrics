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
    
    # Get resume metrics
    resume = db.execute(
        'SELECT * FROM resume_metrics WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
        (team_id,)
    ).fetchone()
    
    db.close()
    
    return jsonify({
        'team': dict(team) if team else None,
        'ratings': dict(ratings) if ratings else None,
        'four_factors': dict(four_factors) if four_factors else None,
        'resume': dict(resume) if resume else None
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
# ============================================================
# BRACKET API ENDPOINTS
# Add these to your backend/app.py file
# ============================================================

@app.route('/api/bracket', methods=['GET'])
def get_bracket():
    """Get full bracket with all teams and matchups"""
    season = request.args.get('season', 2026, type=int)
    
    db = get_db()
    
    # Get all bracket teams with their info
    teams = db.execute('''
        SELECT 
            b.team_id, b.seed, b.region,
            t.name, t.conference, t.logo_url, t.primary_color, t.secondary_color,
            r.adj_em, r.rank_adj_em, r.adj_oe, r.adj_de
        FROM bracket b
        JOIN teams t ON b.team_id = t.team_id
        LEFT JOIN ratings r ON b.team_id = r.team_id AND r.season = b.season
        WHERE b.season = ?
        ORDER BY b.region, b.seed
    ''', (season,)).fetchall()
    
    # Get all matchups
    matchups = db.execute('''
        SELECT 
            m.id, m.region, m.round, m.game_number, m.matchup_name,
            m.high_seed_team_id, m.low_seed_team_id
        FROM matchups m
        WHERE m.season = ?
        ORDER BY m.region, m.round, m.game_number
    ''', (season,)).fetchall()
    
    db.close()
    
    # Organize by region
    bracket_data = {
        'East': {'teams': [], 'matchups': []},
        'West': {'teams': [], 'matchups': []},
        'South': {'teams': [], 'matchups': []},
        'Midwest': {'teams': [], 'matchups': []},
        'First Four': {'matchups': []}
    }
    
    for team in teams:
        team_dict = dict(team)
        region = team_dict['region']
        if region in bracket_data:
            bracket_data[region]['teams'].append(team_dict)
    
    for matchup in matchups:
        matchup_dict = dict(matchup)
        region = matchup_dict['region']
        
        # Round 0 = First Four (play-in games)
        if matchup_dict['round'] == 0:
            bracket_data['First Four']['matchups'].append(matchup_dict)
        elif region in bracket_data:
            bracket_data[region]['matchups'].append(matchup_dict)
    
    return jsonify({
        'season': season,
        'bracket': bracket_data
    })


@app.route('/api/bracket/region/<region_name>', methods=['GET'])
def get_region(region_name):
    """Get bracket data for a specific region"""
    season = request.args.get('season', 2026, type=int)
    
    db = get_db()
    
    teams = db.execute('''
        SELECT 
            b.team_id, b.seed, b.region,
            t.name, t.conference, t.logo_url, t.primary_color, t.secondary_color,
            r.adj_em, r.rank_adj_em, r.adj_oe, r.adj_de,
            rm.quad1_wins, rm.quad1_losses, rm.quad2_wins, rm.quad2_losses
        FROM bracket b
        JOIN teams t ON b.team_id = t.team_id
        LEFT JOIN ratings r ON b.team_id = r.team_id AND r.season = b.season
        LEFT JOIN resume_metrics rm ON b.team_id = rm.team_id AND rm.season = b.season
        WHERE b.season = ? AND b.region = ?
        ORDER BY b.seed
    ''', (season, region_name)).fetchall()
    
    matchups = db.execute('''
        SELECT 
            m.id, m.region, m.round, m.game_number, m.matchup_name,
            m.high_seed_team_id, m.low_seed_team_id,
            t1.name as high_seed_name, t1.seed as high_seed,
            t2.name as low_seed_name, t2.seed as low_seed
        FROM matchups m
        JOIN bracket b1 ON m.high_seed_team_id = b1.team_id AND b1.season = m.season
        JOIN bracket b2 ON m.low_seed_team_id = b2.team_id AND b2.season = m.season
        JOIN teams t1 ON m.high_seed_team_id = t1.team_id
        JOIN teams t2 ON m.low_seed_team_id = t2.team_id
        WHERE m.season = ? AND m.region = ? AND m.round > 0
        ORDER BY m.game_number
    ''', (season, region_name)).fetchall()
    
    db.close()
    
    return jsonify({
        'region': region_name,
        'teams': [dict(t) for t in teams],
        'matchups': [dict(m) for m in matchups]
    })


@app.route('/api/bracket/first-four', methods=['GET'])
def get_first_four():
    """Get First Four play-in games"""
    season = request.args.get('season', 2026, type=int)
    
    db = get_db()
    
    matchups = db.execute('''
        SELECT 
            m.id, m.region, m.matchup_name,
            m.high_seed_team_id, m.low_seed_team_id,
            t1.name as team1_name, t1.logo_url as team1_logo,
            t2.name as team2_name, t2.logo_url as team2_logo,
            b1.seed as seed
        FROM matchups m
        JOIN teams t1 ON m.high_seed_team_id = t1.team_id
        JOIN teams t2 ON m.low_seed_team_id = t2.team_id
        JOIN bracket b1 ON m.high_seed_team_id = b1.team_id AND b1.season = m.season
        WHERE m.season = ? AND m.round = 0
        ORDER BY m.region, m.game_number
    ''', (season,)).fetchall()
    
    db.close()
    
    return jsonify({
        'first_four': [dict(m) for m in matchups]
    })


@app.route('/api/matchup/<int:matchup_id>', methods=['GET'])
def get_matchup_detail(matchup_id):
    """Get detailed comparison for a specific matchup"""
    db = get_db()
    
    matchup = db.execute('''
        SELECT * FROM matchups WHERE id = ?
    ''', (matchup_id,)).fetchone()
    
    if not matchup:
        db.close()
        return jsonify({'error': 'Matchup not found'}), 404
    
    matchup_dict = dict(matchup)
    
    # Get full team data for both teams
    teams_data = []
    for team_id in [matchup_dict['high_seed_team_id'], matchup_dict['low_seed_team_id']]:
        team = db.execute('''
            SELECT 
                t.*, b.seed, b.region,
                r.adj_em, r.rank_adj_em, r.adj_oe, r.rank_adj_oe, 
                r.adj_de, r.rank_adj_de, r.adj_tempo,
                rm.quad1_wins, rm.quad1_losses, rm.quad2_wins, rm.quad2_losses,
                rm.quad3_wins, rm.quad3_losses, rm.quad4_wins, rm.quad4_losses
            FROM teams t
            JOIN bracket b ON t.team_id = b.team_id
            LEFT JOIN ratings r ON t.team_id = r.team_id AND r.season = b.season
            LEFT JOIN resume_metrics rm ON t.team_id = rm.team_id AND rm.season = b.season
            WHERE t.team_id = ?
        ''', (team_id,)).fetchone()
        
        teams_data.append(dict(team) if team else None)
    
    db.close()
    
    return jsonify({
        'matchup': matchup_dict,
        'team1': teams_data[0],
        'team2': teams_data[1]
    })

# Player API Endpoints
# Add these to backend/app.py

@app.route('/api/team/<int:team_id>/players', methods=['GET'])
def get_team_players(team_id):
    """Get players for a team with their stats and roles"""
    db = get_db()
    
    players = db.execute('''
        SELECT 
            p.player_id,
            p.name,
            p.position,
            p.jersey_number,
            p.height,
            p.weight,
            p.headshot_url,
            ps.games_played,
            ps.minutes_pct,
            ps.ppg,
            ps.rpg,
            ps.apg,
            ps.fg_pct,
            ps.three_pct,
            ps.ft_pct,
            ps.efg_pct,
            ps.usage_pct,
            ps.per,
            ps.ts_pct,
            ps.bpm,
            ps.obpm,
            ps.dbpm,
            ps.ws,
            ps.ws_40,
            tr.role,
            tr.role_reason,
            tr.display_order
        FROM players p
        LEFT JOIN player_stats ps ON p.player_id = ps.player_id AND p.season = ps.season
        LEFT JOIN team_roles tr ON p.player_id = tr.player_id AND p.season = tr.season
        WHERE p.team_id = ? AND p.season = 2026
        ORDER BY tr.display_order ASC, ps.ppg DESC
    ''', (team_id,)).fetchall()
    
    db.close()
    
    return jsonify({
        'players': [dict(p) for p in players]
    })


@app.route('/api/team/<int:team_id>/players/key', methods=['GET'])
def get_key_players(team_id):
    """Get only star and x_factor for a team (for bracket matchup preview)"""
    db = get_db()
    
    players = db.execute('''
        SELECT 
            p.player_id,
            p.name,
            p.position,
            p.jersey_number,
            p.height,
            p.weight,
            p.headshot_url,
            ps.ppg,
            ps.rpg,
            ps.apg,
            ps.three_pct,
            ps.usage_pct,
            ps.bpm,
            ps.per,
            ps.ts_pct,
            tr.role,
            tr.role_reason
        FROM players p
        LEFT JOIN player_stats ps ON p.player_id = ps.player_id AND p.season = ps.season
        LEFT JOIN team_roles tr ON p.player_id = tr.player_id AND p.season = tr.season
        WHERE p.team_id = ? AND p.season = 2026
        AND tr.role IN ('star', 'x_factor')
        ORDER BY tr.display_order ASC
    ''', (team_id,)).fetchall()
    
    db.close()
    
    return jsonify({
        'players': [dict(p) for p in players]
    })


@app.route('/api/player/<int:player_id>', methods=['GET'])
def get_player(player_id):
    """Get full details for a single player"""
    db = get_db()
    
    player = db.execute('''
        SELECT 
            p.*,
            ps.*,
            tr.role,
            tr.role_reason,
            t.name as team_name,
            t.logo_url as team_logo,
            t.primary_color as team_color
        FROM players p
        LEFT JOIN player_stats ps ON p.player_id = ps.player_id AND p.season = ps.season
        LEFT JOIN team_roles tr ON p.player_id = tr.player_id AND p.season = tr.season
        LEFT JOIN teams t ON p.team_id = t.team_id AND p.season = t.season
        WHERE p.player_id = ?
    ''', (player_id,)).fetchone()
    
    db.close()
    
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    
    return jsonify(dict(player))

if __name__ == '__main__':
    # Check if database exists
    if not DATABASE.exists():
        print(f"ERROR: Database not found at {DATABASE}")
        print("Run: python setup.py")
        exit(1)
    
    print(f"Using database: {DATABASE}")
    print("Starting Flask server on http://localhost:5000")
    app.run(debug=True, port=5000)