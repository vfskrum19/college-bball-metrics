from flask import Flask, jsonify, request, send_from_directory, g
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os
import json
import logging
from pathlib import Path

# ============================================================
# LAYER 2 ADDITION: Import validators
# ============================================================
from validators import (
    validate_season, validate_team_id, validate_limit,
    validate_kenpom_rank, validate_min_games, validate_trend,
    validate_region, validate_search_query, validate_conference,
    validate_boolean, validate_params
)

# ============================================================
# LAYER 3 ADDITION: Rate limiting
# ============================================================
# Flask-Limiter tracks how many requests each client makes and
# blocks them temporarily if they exceed the limits. This
# protects against:
#   - Bots scraping your entire dataset
#   - Accidental infinite loops in someone's code
#   - Intentional denial-of-service attempts
#   - Generally being a good citizen if you ever share this
#
# Install: pip install Flask-Limiter
#
# How limits work:
#   "100/minute" = 100 requests per 60-second sliding window
#   "5/second" = 5 requests per 1-second sliding window
#   Multiple limits can stack: "100/minute;5/second" means
#   both must pass for the request to go through.
# ============================================================
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

# ============================================================
# CONFIGURATION (Layer 1 - unchanged)
# ============================================================

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'
CURRENT_SEASON = 2026


class Config:
    """Base configuration - shared across all environments"""
    DATABASE_PATH = DATABASE
    CURRENT_SEASON = CURRENT_SEASON
    MAX_RESULTS_LIMIT = 200
    
    # --------------------------------------------------------
    # LAYER 3: Rate limiting configuration
    # --------------------------------------------------------
    # These values balance protection against abuse while not
    # annoying legitimate users. Adjust based on your usage:
    #   - If you're the only user: these are very generous
    #   - If you share it publicly: you might tighten them
    #
    # Format: "count/period" where period is second/minute/hour/day
    # Multiple limits separated by semicolons all must pass.
    # --------------------------------------------------------
    
    # Default limit for all endpoints (fallback)
    RATELIMIT_DEFAULT = "100/minute;10/second"
    
    # Storage: 'memory://' is fine for single-server setups.
    # For multiple servers, you'd use 'redis://localhost:6379'
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Include this header in responses so clients know their limits
    RATELIMIT_HEADERS_ENABLED = True


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__,
                static_folder=str(FRONTEND_DIR / 'static'),
                static_url_path='/static')

    app.config.from_object(config_map.get(config_name, DevelopmentConfig))
    CORS(app)

    # ============================================================
    # LAYER 3: Initialize rate limiter
    # ============================================================
    # The limiter uses the client's IP address to track requests.
    # Each IP gets its own bucket of allowed requests per window.
    #
    # Why check LIMITER_AVAILABLE? If someone hasn't installed
    # flask-limiter yet, the app still runs — just without rate
    # limiting. This makes development easier (one less dependency
    # to install immediately) while still being protected in prod.
    # ============================================================
    if LIMITER_AVAILABLE:
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=[app.config.get('RATELIMIT_DEFAULT', '100/minute')],
            storage_uri=app.config.get('RATELIMIT_STORAGE_URL', 'memory://'),
            headers_enabled=app.config.get('RATELIMIT_HEADERS_ENABLED', True)
        )
    else:
        limiter = None
        app.logger.warning(
            "Flask-Limiter not installed. Rate limiting disabled. "
            "Run: pip install Flask-Limiter"
        )

    # --------------------------------------------------------
    # Helper: Apply rate limit only if limiter is available
    # --------------------------------------------------------
    # This lets us decorate routes with @limit("30/minute") and
    # have it work whether flask-limiter is installed or not.
    # In production you'd always have it installed, but this
    # makes local development more forgiving.
    # --------------------------------------------------------
    def limit(limit_string):
        """Apply rate limit if limiter is available, otherwise no-op"""
        if limiter:
            return limiter.limit(limit_string)
        else:
            # Return a no-op decorator
            def decorator(f):
                return f
            return decorator

    # --- Logging (Layer 1 - unchanged) ---
    if not app.debug:
        log_path = PROJECT_ROOT / 'logs'
        log_path.mkdir(exist_ok=True)
        handler = logging.FileHandler(str(log_path / 'app_errors.log'))
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(handler)

    # --- Database connection management (Layer 1 - unchanged) ---

    def get_db():
        if 'db' not in g:
            g.db = sqlite3.connect(str(app.config['DATABASE_PATH']))
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(exception):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    # --- Error handlers (Layer 1 - unchanged) ---

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad request',
            'message': str(error.description) if hasattr(error, 'description') else str(error)
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Internal server error: {error}')
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.error(f'Unhandled exception: {error}', exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500

    # --------------------------------------------------------
    # LAYER 3: Rate limit exceeded handler (429)
    # --------------------------------------------------------
    # When someone exceeds their rate limit, they get this
    # response. The Retry-After header tells them how many
    # seconds to wait before trying again. Well-behaved clients
    # (and your frontend) should respect this.
    # --------------------------------------------------------
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please slow down.',
            'retry_after': e.description
        }), 429

    # ============================================================
    # ROUTES - Now with input validation (Layer 2)
    # ============================================================
    # WHAT CHANGED:
    #   - @validate_params decorator on routes that take user input.
    #     This catches any ValidationError and returns a clean 400.
    #   - Raw request.args.get() calls replaced with validate_*()
    #     functions that check type, range, and allowed values.
    #   - Search query gets sanitized (length cap, wildcard removal)
    #   - Trend/region get whitelist-checked
    #   - Numeric params get range-checked
    #
    # WHAT DIDN'T CHANGE:
    #   - All SQL queries are identical
    #   - All response shapes are identical
    #   - Your frontend won't notice any difference (it sends
    #     valid data already). Only bad/malicious input gets rejected.
    # ============================================================

    @app.route('/')
    def serve_index():
        """Serve the main index.html file"""
        return send_from_directory(str(FRONTEND_DIR), 'index.html')

    # --- Team endpoints ---

    @app.route('/api/teams', methods=['GET'])
    @validate_params
    def get_teams():
        """Get all teams, optionally filtered by conference"""
        conference = validate_conference(request.args.get('conference'))
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

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

        return jsonify([dict(team) for team in teams])

    @app.route('/api/conferences', methods=['GET'])
    @validate_params
    def get_conferences():
        """Get list of conferences"""
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

        db = get_db()
        conferences = db.execute(
            'SELECT DISTINCT conference FROM teams WHERE season = ? ORDER BY conference',
            (season,)
        ).fetchall()

        return jsonify([conf['conference'] for conf in conferences if conf['conference']])

    @app.route('/api/team/<int:team_id>/ratings', methods=['GET'])
    @validate_params
    def get_team_ratings(team_id):
        """Get current ratings for a specific team"""
        db = get_db()

        team = db.execute(
            'SELECT * FROM teams WHERE team_id = ?',
            (team_id,)
        ).fetchone()

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        ratings = db.execute(
            'SELECT * FROM ratings WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
            (team_id,)
        ).fetchone()

        four_factors = db.execute(
            'SELECT * FROM four_factors WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
            (team_id,)
        ).fetchone()

        try:
            resume = db.execute(
                'SELECT * FROM resume_metrics WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
                (team_id,)
            ).fetchone()
        except sqlite3.OperationalError:
            resume = None

        return jsonify({
            'team': dict(team) if team else None,
            'ratings': dict(ratings) if ratings else None,
            'four_factors': dict(four_factors) if four_factors else None,
            'resume': dict(resume) if resume else None
        })

    @app.route('/api/compare', methods=['GET'])
    @validate_params
    def compare_teams():
        """Compare two teams side by side"""
        # --------------------------------------------------
        # LAYER 2: validate_team_id checks that these are
        # positive integers. Before, passing ?team1=abc would
        # silently return None (Flask's type=int behavior),
        # which then hit the "both required" check. That
        # still worked, but now the error message is specific:
        #   {"field": "team1", "message": "must be a positive integer"}
        # instead of the generic:
        #   {"error": "Both team1 and team2 parameters required"}
        # --------------------------------------------------
        team1_id = validate_team_id(request.args.get('team1'), field='team1')
        team2_id = validate_team_id(request.args.get('team2'), field='team2')

        if not team1_id or not team2_id:
            return jsonify({'error': 'Both team1 and team2 parameters required'}), 400

        db = get_db()

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

            try:
                resume = db.execute(
                    'SELECT * FROM resume_metrics WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
                    (team_id,)
                ).fetchone()
            except sqlite3.OperationalError:
                resume = None

            teams_data.append({
                'team': dict(team) if team else None,
                'ratings': dict(ratings) if ratings else None,
                'four_factors': dict(four_factors) if four_factors else None,
                'resume': dict(resume) if resume else None
            })

        return jsonify({
            'team1': teams_data[0],
            'team2': teams_data[1]
        })

    @app.route('/api/team/<int:team_id>/history', methods=['GET'])
    @validate_params
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

        return jsonify([dict(row) for row in history])

    @app.route('/api/search', methods=['GET'])
    @limit("30/minute")
    @validate_params
    def search_teams():
        """Search teams by name
        
        Rate limit: 30/minute (stricter than default)
        Search endpoints are common abuse targets - bots will
        try every possible query string to scrape data. The
        LIKE query can also be expensive on large tables.
        """
        # --------------------------------------------------
        # LAYER 2: validate_search_query does three things:
        #   1. Caps length at 100 chars (was unlimited)
        #   2. Strips SQL wildcards % and _ from user input
        #   3. Returns clean empty string if blank
        # --------------------------------------------------
        query = validate_search_query(request.args.get('q'))
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

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

        return jsonify([dict(team) for team in teams])

    @app.route('/api/status', methods=['GET'])
    def get_status():
        """Get database status and last update time"""
        db = get_db()

        team_count = db.execute('SELECT COUNT(*) as count FROM teams').fetchone()['count']
        last_update = db.execute(
            'SELECT MAX(updated_at) as last_update FROM ratings'
        ).fetchone()['last_update']

        return jsonify({
            'teams_count': team_count,
            'last_update': last_update,
            'status': 'online'
        })

    # ============================================================
    # BRACKET API ENDPOINTS
    # ============================================================

    @app.route('/api/bracket', methods=['GET'])
    @limit("60/minute")
    @validate_params
    def get_bracket():
        """Get full bracket with all teams and matchups"""
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

        db = get_db()

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

        matchups = db.execute('''
            SELECT
                m.id, m.region, m.round, m.game_number, m.matchup_name,
                m.high_seed_team_id, m.low_seed_team_id
            FROM matchups m
            WHERE m.season = ?
            ORDER BY m.region, m.round, m.game_number
        ''', (season,)).fetchall()

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
            if matchup_dict['round'] == 0:
                bracket_data['First Four']['matchups'].append(matchup_dict)
            elif region in bracket_data:
                bracket_data[region]['matchups'].append(matchup_dict)

        return jsonify({
            'season': season,
            'bracket': bracket_data
        })

    @app.route('/api/bracket/region/<region_name>', methods=['GET'])
    @validate_params
    def get_region(region_name):
        """Get bracket data for a specific region"""
        # --------------------------------------------------
        # LAYER 2: validate_region whitelist-checks the region
        # name. Before, someone could pass any string as the
        # region (including path traversal attempts). Now it
        # must be East, West, South, or Midwest.
        # --------------------------------------------------
        region_name = validate_region(region_name)
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

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

        return jsonify({
            'region': region_name,
            'teams': [dict(t) for t in teams],
            'matchups': [dict(m) for m in matchups]
        })

    @app.route('/api/bracket/first-four', methods=['GET'])
    @validate_params
    def get_first_four():
        """Get First Four play-in games"""
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

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

        return jsonify({
            'first_four': [dict(m) for m in matchups]
        })

    @app.route('/api/matchup/<int:matchup_id>', methods=['GET'])
    @validate_params
    def get_matchup_detail(matchup_id):
        """Get detailed comparison for a specific matchup"""
        db = get_db()

        matchup = db.execute('''
            SELECT * FROM matchups WHERE id = ?
        ''', (matchup_id,)).fetchone()

        if not matchup:
            return jsonify({'error': 'Matchup not found'}), 404

        matchup_dict = dict(matchup)

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

        return jsonify({
            'matchup': matchup_dict,
            'team1': teams_data[0],
            'team2': teams_data[1]
        })

    # ============================================================
    # PLAYER API ENDPOINTS
    # ============================================================

    @app.route('/api/team/<int:team_id>/players', methods=['GET'])
    @validate_params
    def get_team_players(team_id):
        """Get players for a team with their stats and roles"""
        db = get_db()

        players = db.execute('''
            SELECT
                p.player_id, p.name, p.position, p.jersey_number,
                p.height, p.weight, p.headshot_url,
                ps.games_played, ps.minutes_pct, ps.ppg, ps.rpg, ps.apg,
                ps.fg_pct, ps.three_pct, ps.ft_pct, ps.efg_pct,
                ps.usage_pct, ps.per, ps.ts_pct, ps.bpm, ps.obpm, ps.dbpm,
                ps.ws, ps.ws_40,
                tr.role, tr.role_reason, tr.display_order
            FROM players p
            LEFT JOIN player_stats ps ON p.player_id = ps.player_id AND p.season = ps.season
            LEFT JOIN team_roles tr ON p.player_id = tr.player_id AND p.season = tr.season
            WHERE p.team_id = ? AND p.season = ?
            ORDER BY tr.display_order ASC, ps.ppg DESC
        ''', (team_id, CURRENT_SEASON)).fetchall()

        return jsonify({
            'players': [dict(p) for p in players]
        })

    @app.route('/api/team/<int:team_id>/players/key', methods=['GET'])
    @validate_params
    def get_key_players(team_id):
        """Get only star and x_factor for a team (for bracket matchup preview)"""
        db = get_db()

        players = db.execute('''
            SELECT
                p.player_id, p.name, p.position, p.jersey_number,
                p.height, p.weight, p.headshot_url,
                ps.ppg, ps.rpg, ps.apg, ps.three_pct,
                ps.usage_pct, ps.bpm, ps.per, ps.ts_pct,
                tr.role, tr.role_reason
            FROM players p
            LEFT JOIN player_stats ps ON p.player_id = ps.player_id AND p.season = ps.season
            LEFT JOIN team_roles tr ON p.player_id = tr.player_id AND p.season = tr.season
            WHERE p.team_id = ? AND p.season = ?
            AND tr.role IN ('star', 'x_factor')
            ORDER BY tr.display_order ASC
        ''', (team_id, CURRENT_SEASON)).fetchall()

        return jsonify({
            'players': [dict(p) for p in players]
        })

    @app.route('/api/player/<int:player_id>', methods=['GET'])
    @validate_params
    def get_player(player_id):
        """Get full details for a single player"""
        db = get_db()

        player = db.execute('''
            SELECT
                p.*, ps.*,
                tr.role, tr.role_reason,
                t.name as team_name, t.logo_url as team_logo,
                t.primary_color as team_color
            FROM players p
            LEFT JOIN player_stats ps ON p.player_id = ps.player_id AND p.season = ps.season
            LEFT JOIN team_roles tr ON p.player_id = tr.player_id AND p.season = tr.season
            LEFT JOIN teams t ON p.team_id = t.team_id AND p.season = t.season
            WHERE p.player_id = ?
        ''', (player_id,)).fetchone()

        if not player:
            return jsonify({'error': 'Player not found'}), 404

        return jsonify(dict(player))

    # ============================================================
    # MOMENTUM TRACKER API ENDPOINTS
    # ============================================================

    @app.route('/api/momentum/rankings')
    @limit("30/minute")
    @validate_params
    def get_momentum_rankings():
        """Get momentum rankings with optional filters
        
        Rate limit: 30/minute (stricter than default)
        This endpoint is heavier than most - it joins multiple tables
        and supports many filter combinations. Tighter limits prevent
        someone from hammering it with different filter combos.
        """

        # --------------------------------------------------
        # LAYER 2: Every parameter is now validated.
        #
        # Before (what someone could send):
        #   ?limit=999999&min_games=-1&trend=<script>&kenpom_min=DROP
        #
        # After (what actually reaches your query):
        #   limit capped at 200, min_games 0-35, trend must be
        #   in whitelist, kenpom_rank must be 1-363.
        #   Anything else -> 400 with specific error message.
        # --------------------------------------------------
        max_limit = app.config.get('MAX_RESULTS_LIMIT', 200)
        limit = validate_limit(request.args.get('limit'), default=50, maximum=max_limit)
        min_games = validate_min_games(request.args.get('min_games'))
        trend = validate_trend(request.args.get('trend'))
        tournament_only = validate_boolean(request.args.get('tournament'))
        kenpom_min = validate_kenpom_rank(request.args.get('kenpom_min'), field='kenpom_min')
        kenpom_max = validate_kenpom_rank(request.args.get('kenpom_max'), field='kenpom_max')
        conference = validate_conference(request.args.get('conference'))

        db = get_db()

        query = '''
            SELECT mc.*, t.name, t.conference, t.logo_url, r.rank_adj_em as kenpom_rank, b.seed, b.region
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

        teams = db.execute(query, params).fetchall()

        results = []
        for i, team in enumerate(teams, 1):
            results.append({
                'momentum_rank': i,
                'team_id': team['team_id'],
                'name': team['name'],
                'conference': team['conference'],
                'logo_url': team['logo_url'],
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

    @app.route('/api/momentum/team/<int:team_id>')
    @validate_params
    def get_team_momentum(team_id):
        """Get detailed momentum data for a single team"""

        db = get_db()

        team = db.execute('''
            SELECT mc.*, t.name, t.conference, t.logo_url, r.rank_adj_em as kenpom_rank,
                   r.adj_em, r.adj_oe, r.adj_de, b.seed, b.region
            FROM momentum_cache mc
            JOIN teams t ON mc.team_id = t.team_id
            JOIN ratings r ON mc.team_id = r.team_id
            LEFT JOIN bracket b ON mc.team_id = b.team_id
            WHERE mc.team_id = ? AND mc.season = ?
        ''', (team_id, CURRENT_SEASON)).fetchone()

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        rank = db.execute('''
            SELECT COUNT(*) + 1 as rank
            FROM momentum_cache
            WHERE momentum_score > ? AND season = ?
        ''', (team['momentum_score'], CURRENT_SEASON)).fetchone()['rank']

        trajectory = db.execute('''
            SELECT snapshot_date, rank_adj_em, adj_em
            FROM momentum_ratings
            WHERE team_id = ?
            ORDER BY snapshot_date
        ''', (team_id,)).fetchall()

        return jsonify({
            'team_id': team['team_id'],
            'name': team['name'],
            'conference': team['conference'],
            'logo_url': team['logo_url'],
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

    @app.route('/api/momentum/upsets')
    @limit("30/minute")
    @validate_params
    def get_upset_candidates():
        """Get first-round upset candidates (seeds 10-15)"""

        max_limit = app.config.get('MAX_RESULTS_LIMIT', 200)
        limit = validate_limit(request.args.get('limit'), default=12, maximum=max_limit)
        min_games = validate_min_games(request.args.get('min_games'))

        db = get_db()

        underdogs = db.execute('''
            SELECT mc.*, t.name, t.conference, t.logo_url, r.rank_adj_em as kenpom_rank,
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

            opponent = db.execute('''
                SELECT mc.*, t.name, t.logo_url, r.rank_adj_em as kenpom_rank, b.seed
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
                    'logo_url': team['logo_url'],
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
                        'logo_url': opponent['logo_url'],
                        'seed': opponent_seed,
                        'kenpom_rank': opponent['kenpom_rank'],
                        'momentum_score': opp_momentum,
                        'slumping': opp_slumping
                    },
                    'momentum_diff': round(momentum_diff, 1),
                    'upset_score': round(upset_score, 1)
                })

        upset_candidates.sort(key=lambda x: x['upset_score'], reverse=True)

        return jsonify(upset_candidates[:limit])

    @app.route('/api/momentum/vulnerable')
    @validate_params
    def get_vulnerable_favorites():
        """Get top seeds (1-6) with low momentum - upset targets"""

        max_limit = app.config.get('MAX_RESULTS_LIMIT', 200)
        limit = validate_limit(request.args.get('limit'), default=15, maximum=max_limit)
        min_games = validate_min_games(request.args.get('min_games'))

        db = get_db()

        teams = db.execute('''
            SELECT mc.*, t.name, t.conference, t.logo_url, r.rank_adj_em as kenpom_rank, b.seed, b.region
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

        results = []
        for team in teams:
            results.append({
                'team_id': team['team_id'],
                'name': team['name'],
                'logo_url': team['logo_url'],
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

    @app.route('/api/momentum/conferences')
    def get_momentum_conferences():
        """Get list of all conferences for filtering"""

        db = get_db()

        conferences = db.execute('''
            SELECT DISTINCT t.conference
            FROM teams t
            WHERE t.season = ?
            ORDER BY t.conference
        ''', (CURRENT_SEASON,)).fetchall()

        return jsonify([c['conference'] for c in conferences])

    # Return the configured app
    return app


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == '__main__':
    app = create_app()

    if not DATABASE.exists():
        print(f"ERROR: Database not found at {DATABASE}")
        print("Run: python setup.py")
        exit(1)

    print(f"Using database: {DATABASE}")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print("Starting Flask server on http://localhost:5000")
    app.run(port=5000)