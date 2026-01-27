"""
Momentum API Endpoints
Add these routes to your main Flask app (app.py)
"""

from flask import Blueprint, jsonify, request
import sqlite3
import json
from pathlib import Path

# Create blueprint - import and register in main app.py
momentum_bp = Blueprint('momentum', __name__)

DATABASE = Path(__file__).parent / 'database' / 'kenpom.db'
CURRENT_SEASON = 2026

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

@momentum_bp.route('/api/momentum/rankings')
def get_momentum_rankings():
    """Get momentum rankings with optional filters"""
    
    # Query params
    limit = request.args.get('limit', 50, type=int)
    min_games = request.args.get('min_games', 5, type=int)
    trend = request.args.get('trend')  # hot, cold, rising, falling, stable
    tournament_only = request.args.get('tournament', 'false').lower() == 'true'
    kenpom_min = request.args.get('kenpom_min', type=int)
    kenpom_max = request.args.get('kenpom_max', type=int)
    conference = request.args.get('conference')
    
    db = get_db()
    cursor = db.cursor()
    
    query = '''
        SELECT mc.*, t.name, t.conference, r.rank_adj_em as kenpom_rank, b.seed, b.region
        FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        JOIN ratings r ON mc.team_id = r.team_id
        LEFT JOIN bracket b ON mc.team_id = b.team_id
        WHERE mc.season = ?
          AND mc.games_played_l10 >= ?
    '''
    params = [CURRENT_SEASON, min_games]
    
    if trend:
        query += ' AND mc.trend_direction = ?'
        params.append(trend)
    
    if tournament_only:
        query += ' AND b.team_id IS NOT NULL'
    
    if kenpom_min is not None:
        query += ' AND r.rank_adj_em >= ?'
        params.append(kenpom_min)
    
    if kenpom_max is not None:
        query += ' AND r.rank_adj_em <= ?'
        params.append(kenpom_max)
    
    if conference:
        query += ' AND t.conference = ?'
        params.append(conference)
    
    query += ' ORDER BY mc.momentum_score DESC LIMIT ?'
    params.append(limit)
    
    teams = cursor.execute(query, params).fetchall()
    db.close()
    
    results = []
    for i, team in enumerate(teams, 1):
        results.append({
            'momentum_rank': i,
            'team_id': team['team_id'],
            'name': team['name'],
            'conference': team['conference'],
            'kenpom_rank': team['kenpom_rank'],
            'seed': team['seed'],
            'region': team['region'],
            'games_played': team['games_played_l10'],
            'wins': team['wins_l10'],
            'losses': team['losses_l10'],
            'win_streak': team['win_streak'],
            'loss_streak': team['loss_streak'],
            'avg_margin': round(team['avg_margin_l10'], 1) if team['avg_margin_l10'] else None,
            'avg_vs_expected': round(team['avg_vs_expected_l10'], 1) if team['avg_vs_expected_l10'] else None,
            'rank_change': team['rank_change_l10'],
            'momentum_score': team['momentum_score'],
            'trend': team['trend_direction'],
            'games_data': json.loads(team['games_data']) if team['games_data'] else []
        })
    
    return jsonify(results)


@momentum_bp.route('/api/momentum/team/<int:team_id>')
def get_team_momentum(team_id):
    """Get detailed momentum data for a single team"""
    
    db = get_db()
    cursor = db.cursor()
    
    team = cursor.execute('''
        SELECT mc.*, t.name, t.conference, r.rank_adj_em as kenpom_rank, 
               r.adj_em, r.adj_oe, r.adj_de, b.seed, b.region
        FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        JOIN ratings r ON mc.team_id = r.team_id
        LEFT JOIN bracket b ON mc.team_id = b.team_id
        WHERE mc.team_id = ? AND mc.season = ?
    ''', (team_id, CURRENT_SEASON)).fetchone()
    
    if not team:
        db.close()
        return jsonify({'error': 'Team not found'}), 404
    
    # Get momentum rank
    rank = cursor.execute('''
        SELECT COUNT(*) + 1 as rank
        FROM momentum_cache
        WHERE momentum_score > ? AND season = ?
    ''', (team['momentum_score'], CURRENT_SEASON)).fetchone()['rank']
    
    # Get rating trajectory
    trajectory = cursor.execute('''
        SELECT snapshot_date, rank_adj_em, adj_em
        FROM momentum_ratings
        WHERE team_id = ?
        ORDER BY snapshot_date
    ''', (team_id,)).fetchall()
    
    db.close()
    
    return jsonify({
        'team_id': team['team_id'],
        'name': team['name'],
        'conference': team['conference'],
        'kenpom_rank': team['kenpom_rank'],
        'adj_em': team['adj_em'],
        'adj_oe': team['adj_oe'],
        'adj_de': team['adj_de'],
        'seed': team['seed'],
        'region': team['region'],
        'momentum_rank': rank,
        'momentum_score': team['momentum_score'],
        'trend': team['trend_direction'],
        'games_played': team['games_played_l10'],
        'wins': team['wins_l10'],
        'losses': team['losses_l10'],
        'win_streak': team['win_streak'],
        'loss_streak': team['loss_streak'],
        'avg_margin': round(team['avg_margin_l10'], 1) if team['avg_margin_l10'] else None,
        'avg_vs_expected': round(team['avg_vs_expected_l10'], 1) if team['avg_vs_expected_l10'] else None,
        'best_win_margin': team['best_win_margin'],
        'worst_loss_margin': team['worst_loss_margin'],
        'rank_change': team['rank_change_l10'],
        'adj_em_change': round(team['adj_em_change_l10'], 2) if team['adj_em_change_l10'] else None,
        'games': json.loads(team['games_data']) if team['games_data'] else [],
        'trajectory': [{'date': t['snapshot_date'], 'rank': t['rank_adj_em'], 'adj_em': t['adj_em']} for t in trajectory]
    })


@momentum_bp.route('/api/momentum/upsets')
def get_upset_candidates():
    """Get first-round upset candidates (seeds 10-15)"""
    
    limit = request.args.get('limit', 12, type=int)
    min_games = request.args.get('min_games', 5, type=int)
    
    db = get_db()
    cursor = db.cursor()
    
    # Get underdogs (seeds 10-15)
    underdogs = cursor.execute('''
        SELECT mc.*, t.name, t.conference, r.rank_adj_em as kenpom_rank, 
               b.seed, b.region, r.adj_tempo
        FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        JOIN ratings r ON mc.team_id = r.team_id
        JOIN bracket b ON mc.team_id = b.team_id
        WHERE mc.season = ?
          AND mc.games_played_l10 >= ?
          AND b.seed >= 10 AND b.seed <= 15
        ORDER BY mc.momentum_score DESC
    ''', (CURRENT_SEASON, min_games)).fetchall()
    
    upset_candidates = []
    
    for team in underdogs:
        seed = team['seed']
        region = team['region']
        opponent_seed = 17 - seed
        
        # Find opponent
        opponent = cursor.execute('''
            SELECT mc.*, t.name, r.rank_adj_em as kenpom_rank, b.seed
            FROM bracket b
            JOIN teams t ON b.team_id = t.team_id
            JOIN ratings r ON b.team_id = r.team_id
            LEFT JOIN momentum_cache mc ON b.team_id = mc.team_id
            WHERE b.region = ? AND b.seed = ?
        ''', (region, opponent_seed)).fetchone()
        
        if not opponent:
            continue
        
        momentum = team['momentum_score'] or 50
        opp_momentum = opponent['momentum_score'] or 50
        vs_expected = team['avg_vs_expected_l10'] or 0
        opp_vs_expected = opponent['avg_vs_expected_l10'] or 0
        rank_change = team['rank_change_l10'] or 0
        win_streak = team['win_streak'] or 0
        
        momentum_diff = momentum - opp_momentum
        opp_slumping = opp_momentum < 50 or (opp_vs_expected and opp_vs_expected < -2)
        
        # Upset score calculation
        upset_score = (
            momentum * 0.35 +
            (vs_expected + 10) * 1.5 +
            momentum_diff * 0.5 +
            min(rank_change, 30) * 0.4 +
            win_streak * 2 +
            (15 if opp_slumping else 0)
        )
        
        if upset_score >= 35:
            upset_candidates.append({
                'team_id': team['team_id'],
                'name': team['name'],
                'seed': seed,
                'region': region,
                'kenpom_rank': team['kenpom_rank'],
                'momentum_score': momentum,
                'wins': team['wins_l10'],
                'losses': team['losses_l10'],
                'win_streak': win_streak,
                'avg_vs_expected': round(vs_expected, 1) if vs_expected else None,
                'rank_change': rank_change,
                'trend': team['trend_direction'],
                'opponent': {
                    'name': opponent['name'],
                    'seed': opponent_seed,
                    'kenpom_rank': opponent['kenpom_rank'],
                    'momentum_score': opp_momentum,
                    'slumping': opp_slumping
                },
                'momentum_diff': round(momentum_diff, 1),
                'upset_score': round(upset_score, 1)
            })
    
    db.close()
    
    # Sort by upset score
    upset_candidates.sort(key=lambda x: x['upset_score'], reverse=True)
    
    return jsonify(upset_candidates[:limit])


@momentum_bp.route('/api/momentum/vulnerable')
def get_vulnerable_favorites():
    """Get top seeds (1-6) with low momentum - upset targets"""
    
    limit = request.args.get('limit', 15, type=int)
    min_games = request.args.get('min_games', 5, type=int)
    
    db = get_db()
    cursor = db.cursor()
    
    teams = cursor.execute('''
        SELECT mc.*, t.name, t.conference, r.rank_adj_em as kenpom_rank, b.seed, b.region
        FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        JOIN ratings r ON mc.team_id = r.team_id
        JOIN bracket b ON mc.team_id = b.team_id
        WHERE mc.season = ?
          AND mc.games_played_l10 >= ?
          AND b.seed <= 6
        ORDER BY mc.momentum_score ASC
        LIMIT ?
    ''', (CURRENT_SEASON, min_games, limit)).fetchall()
    
    db.close()
    
    results = []
    for team in teams:
        results.append({
            'team_id': team['team_id'],
            'name': team['name'],
            'seed': team['seed'],
            'region': team['region'],
            'kenpom_rank': team['kenpom_rank'],
            'conference': team['conference'],
            'momentum_score': team['momentum_score'],
            'wins': team['wins_l10'],
            'losses': team['losses_l10'],
            'win_streak': team['win_streak'],
            'loss_streak': team['loss_streak'],
            'avg_vs_expected': round(team['avg_vs_expected_l10'], 1) if team['avg_vs_expected_l10'] else None,
            'rank_change': team['rank_change_l10'],
            'trend': team['trend_direction']
        })
    
    return jsonify(results)


@momentum_bp.route('/api/momentum/conferences')
def get_conferences():
    """Get list of all conferences for filtering"""
    
    db = get_db()
    cursor = db.cursor()
    
    conferences = cursor.execute('''
        SELECT DISTINCT t.conference
        FROM teams t
        WHERE t.season = ?
        ORDER BY t.conference
    ''', (CURRENT_SEASON,)).fetchall()
    
    db.close()
    
    return jsonify([c['conference'] for c in conferences])
