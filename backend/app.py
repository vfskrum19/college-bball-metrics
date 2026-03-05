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
try:
    # Production: Gunicorn loads app as backend.app module
    from backend.validators import (
        validate_season, validate_team_id, validate_limit,
        validate_kenpom_rank, validate_min_games, validate_trend,
        validate_region, validate_search_query, validate_conference,
        validate_boolean, validate_params
    )
except ImportError:
    # Local dev: running python backend/app.py directly
    from validators import (
        validate_season, validate_team_id, validate_limit,
        validate_kenpom_rank, validate_min_games, validate_trend,
        validate_region, validate_search_query, validate_conference,
        validate_boolean, validate_params
    )

# ============================================================
# LAYER 3 ADDITION: Rate limiting
# ============================================================
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

# ============================================================
# DATABASE: PostgreSQL in production, SQLite locally
# ============================================================
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
        import psycopg2.pool
    except ImportError:
        print("ERROR: psycopg2 not installed but DATABASE_URL is set.")
        print("Run: pip install psycopg2-binary")
        raise

# ============================================================
# CONFIGURATION
# ============================================================

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'
CURRENT_SEASON = 2026


class Config:
    DATABASE_PATH = DATABASE
    CURRENT_SEASON = CURRENT_SEASON
    MAX_RESULTS_LIMIT = 200
    RATELIMIT_DEFAULT = "100/minute;10/second"
    RATELIMIT_STORAGE_URL = "memory://"
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

    frontend_dist = PROJECT_ROOT / 'frontend' / 'dist'
    app = Flask(__name__,
                static_folder=str(frontend_dist / 'assets'),
                static_url_path='/assets')

    app.config.from_object(config_map.get(config_name, DevelopmentConfig))

    # ============================================================
    # CORS
    # ============================================================
    frontend_url = os.environ.get('FRONTEND_URL')

    if frontend_url:
        CORS(app, origins=[frontend_url], supports_credentials=True)
        app.logger.info(f"CORS restricted to: {frontend_url}")
    else:
        CORS(app, origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:4173",
        ])

    # ============================================================
    # LAYER 3: Initialize rate limiter
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

    def limit(limit_string):
        if limiter:
            return limiter.limit(limit_string)
        else:
            def decorator(f):
                return f
            return decorator

    # --- Logging ---
    if not app.debug:
        log_path = PROJECT_ROOT / 'logs'
        log_path.mkdir(exist_ok=True)
        handler = logging.FileHandler(str(log_path / 'app_errors.log'))
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(handler)

    # ============================================================
    # DATABASE CONNECTION MANAGEMENT
    # ============================================================

    if USE_POSTGRES:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=DATABASE_URL
        )

        def get_db():
            if 'db' not in g:
                conn = connection_pool.getconn()
                conn.autocommit = True
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                g.db = conn
                g.db_cursor = cursor
            return g.db

        def query_db(sql, params=None):
            get_db()
            pg_sql = sql.replace('?', '%s')
            g.db_cursor.execute(pg_sql, params or [])
            try:
                rows = g.db_cursor.fetchall()
                return rows
            except psycopg2.ProgrammingError:
                return []

        @app.teardown_appcontext
        def close_db(exception):
            cursor = g.pop('db_cursor', None)
            conn = g.pop('db', None)
            if cursor:
                cursor.close()
            if conn:
                connection_pool.putconn(conn)

    else:
        def get_db():
            if 'db' not in g:
                g.db = sqlite3.connect(str(app.config['DATABASE_PATH']))
                g.db.row_factory = sqlite3.Row
            return g.db

        def query_db(sql, params=None):
            db = get_db()
            cursor = db.execute(sql, params or [])
            return cursor.fetchall()

        @app.teardown_appcontext
        def close_db(exception):
            db = g.pop('db', None)
            if db is not None:
                db.close()

    # --- Error handlers ---

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

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please slow down.',
            'retry_after': e.description
        }), 429

    # ============================================================
    # ROUTES
    # ============================================================

    @app.route('/')
    def serve_index():
        return send_from_directory(str(frontend_dist), 'index.html')

    @app.route('/<path:path>')
    def serve_spa(path):
        file_path = frontend_dist / path
        if file_path.exists():
            return send_from_directory(str(frontend_dist), path)
        return send_from_directory(str(frontend_dist), 'index.html')

    # --- Team endpoints ---

    @app.route('/api/teams', methods=['GET'])
    @validate_params
    def get_teams():
        conference = validate_conference(request.args.get('conference'))
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

        if conference:
            teams = query_db(
                'SELECT * FROM teams WHERE conference = ? AND season = ? ORDER BY name',
                (conference, season)
            )
        else:
            teams = query_db(
                'SELECT * FROM teams WHERE season = ? ORDER BY name',
                (season,)
            )

        return jsonify([dict(team) for team in teams])

    @app.route('/api/conferences', methods=['GET'])
    @validate_params
    def get_conferences():
        season = validate_season(request.args.get('season')) or CURRENT_SEASON
        conferences = query_db(
            'SELECT DISTINCT conference FROM teams WHERE season = ? ORDER BY conference',
            (season,)
        )
        return jsonify([conf['conference'] for conf in conferences if conf['conference']])

    @app.route('/api/team/<int:team_id>/ratings', methods=['GET'])
    @validate_params
    def get_team_ratings(team_id):
        team = query_db('SELECT * FROM teams WHERE team_id = ?', (team_id,))

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        ratings = query_db(
            'SELECT * FROM ratings WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
            (team_id,)
        )
        four_factors = query_db(
            'SELECT * FROM four_factors WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
            (team_id,)
        )

        try:
            resume = query_db(
                'SELECT * FROM resume_metrics WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
                (team_id,)
            )
        except Exception:
            resume = []

        return jsonify({
            'team': dict(team[0]) if team else None,
            'ratings': dict(ratings[0]) if ratings else None,
            'four_factors': dict(four_factors[0]) if four_factors else None,
            'resume': dict(resume[0]) if resume else None
        })

    @app.route('/api/compare', methods=['GET'])
    @validate_params
    def compare_teams():
        team1_id = validate_team_id(request.args.get('team1'), field='team1')
        team2_id = validate_team_id(request.args.get('team2'), field='team2')

        if not team1_id or not team2_id:
            return jsonify({'error': 'Both team1 and team2 parameters required'}), 400

        teams_data = []
        for team_id in [team1_id, team2_id]:
            team = query_db('SELECT * FROM teams WHERE team_id = ?', (team_id,))
            ratings = query_db(
                'SELECT * FROM ratings WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
                (team_id,)
            )
            four_factors = query_db(
                'SELECT * FROM four_factors WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
                (team_id,)
            )

            try:
                resume = query_db(
                    'SELECT * FROM resume_metrics WHERE team_id = ? ORDER BY updated_at DESC LIMIT 1',
                    (team_id,)
                )
            except Exception:
                resume = []

            teams_data.append({
                'team': dict(team[0]) if team else None,
                'ratings': dict(ratings[0]) if ratings else None,
                'four_factors': dict(four_factors[0]) if four_factors else None,
                'resume': dict(resume[0]) if resume else None
            })

        return jsonify({'team1': teams_data[0], 'team2': teams_data[1]})

    @app.route('/api/team/<int:team_id>/history', methods=['GET'])
    @validate_params
    def get_team_history(team_id):
        history = query_db(
            '''SELECT archive_date, adj_em, rank_adj_em, adj_oe, adj_de, adj_tempo
               FROM ratings_archive
               WHERE team_id = ?
               ORDER BY archive_date ASC''',
            (team_id,)
        )
        return jsonify([dict(row) for row in history])

    @app.route('/api/search', methods=['GET'])
    @limit("30/minute")
    @validate_params
    def search_teams():
        query = validate_search_query(request.args.get('q'))
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

        if not query:
            return jsonify([])

        teams = query_db(
            '''SELECT t.*, r.rank_adj_em, r.adj_em
               FROM teams t
               LEFT JOIN ratings r ON t.team_id = r.team_id
               WHERE t.name LIKE ? AND t.season = ?
               ORDER BY t.name
               LIMIT 20''',
            (f'%{query}%', season)
        )
        return jsonify([dict(team) for team in teams])

    @app.route('/api/status', methods=['GET'])
    def get_status():
        team_count = query_db('SELECT COUNT(*) as count FROM teams')[0]['count']
        last_update = query_db('SELECT MAX(updated_at) as last_update FROM ratings')[0]['last_update']
        return jsonify({
            'teams_count': team_count,
            'last_update': last_update,
            'status': 'online',
            'database': 'postgresql' if USE_POSTGRES else 'sqlite'
        })

    # ============================================================
    # SHOOTING STATS ENDPOINT
    # ============================================================
    # Returns ESPN-sourced shooting data for a team.
    # This is what we use on team cards instead of KenPom Four Factors —
    # 3PT% and FT% are freely available from ESPN and are better
    # tournament-predictive metrics for public display anyway.
    #
    # Requires fetch_espn_shooting_stats.py to have been run first
    # to populate the shooting columns on the teams table.
    # ============================================================

    @app.route('/api/team/<int:team_id>/shooting', methods=['GET'])
    @validate_params
    def get_team_shooting(team_id):
        team = query_db(
            '''SELECT team_id, name, fg3_pct, fg3_made, fg3_att,
                      ft_pct, ft_made, ft_att, opp_fg3_pct, ft_rate,
                      shooting_updated_at
               FROM teams WHERE team_id = ?''',
            (team_id,)
        )

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        t = dict(team[0])

        # If the scraper hasn't run yet for this team, return a clear
        # indicator rather than a bunch of nulls. Frontend shows a
        # "Stats loading..." state instead of a broken section.
        if t.get('fg3_pct') is None:
            return jsonify({
                'team_id': team_id,
                'shooting': None,
                'message': 'Shooting stats not yet available — run fetch_espn_shooting_stats.py'
            }), 200

        return jsonify({
            'team_id': team_id,
            'shooting': {
                'three_point': {
                    'pct':  t['fg3_pct'],
                    'made': t['fg3_made'],
                    'att':  t['fg3_att'],
                },
                'free_throw': {
                    'pct':  t['ft_pct'],
                    'made': t['ft_made'],
                    'att':  t['ft_att'],
                },
                # Defensive discipline — how well they limit opponent 3PT looks
                'opp_fg3_pct': t['opp_fg3_pct'],
                # FTA/FGA ratio — measures how aggressively they attack the rim,
                # not just whether they make FTs once they get there
                'ft_rate':     t['ft_rate'],
                'updated_at':  t['shooting_updated_at'],
            }
        })

    # ============================================================
    # RESUME GAMES ENDPOINT (Quality Wins / Notable Losses)
    # ============================================================
    # This is the "ESPN bracket breakdown" style resume section.
    # Returns top wins sorted by opponent quality and worst losses,
    # each with home/away context, date, score, and opponent logo.
    #
    # Why a separate endpoint from /ratings?
    #   The query is a UNION across games joined to opponent teams
    #   and resume_metrics. It's heavier than a simple table lookup
    #   and only needed when the resume section is rendered — keeping
    #   it separate means /ratings stays fast for everything else.
    #
    # Defaults: 5 quality wins, 3 notable losses — matches ESPN's
    # bracket breakdown style. Callers can override via query params.
    # ============================================================

    @app.route('/api/team/<int:team_id>/resume-games', methods=['GET'])
    @validate_params
    def get_resume_games(team_id):
        # Safe integer parsing with capped maximums so callers
        # can't request 500 games and hammer the DB
        try:
            wins_limit   = min(int(request.args.get('wins_limit',   5)), 10)
            losses_limit = min(int(request.args.get('losses_limit', 3)),  8)
        except ValueError:
            wins_limit, losses_limit = 5, 3

        team = query_db(
            'SELECT team_id, name FROM teams WHERE team_id = ?',
            (team_id,)
        )

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        # ── Quality Wins ──────────────────────────────────────────
        # UNION handles both cases: our team as home OR away.
        # We join to the opponent's resume_metrics to get their NET
        # rank — lower rank = more impressive win, so we sort ASC.
        # NULLS LAST keeps teams without NET data at the bottom.
        quality_wins_sql = '''
            SELECT
                g.game_id,
                g.game_date,
                opp.team_id   AS opp_team_id,
                opp.name      AS opp_name,
                opp.logo_url  AS opp_logo,
                'vs'          AS location,
                g.home_score  AS team_score,
                g.away_score  AS opp_score,
                r.net_rank    AS opp_net_rank
            FROM games g
            JOIN teams opp ON opp.team_id = g.away_team_id
            LEFT JOIN resume_metrics r ON r.team_id = g.away_team_id
            WHERE g.home_team_id = ?
              AND g.home_score IS NOT NULL
              AND g.home_score > g.away_score

            UNION ALL

            SELECT
                g.game_id,
                g.game_date,
                opp.team_id   AS opp_team_id,
                opp.name      AS opp_name,
                opp.logo_url  AS opp_logo,
                '@'           AS location,
                g.away_score  AS team_score,
                g.home_score  AS opp_score,
                r.net_rank    AS opp_net_rank
            FROM games g
            JOIN teams opp ON opp.team_id = g.home_team_id
            LEFT JOIN resume_metrics r ON r.team_id = g.home_team_id
            WHERE g.away_team_id = ?
              AND g.away_score IS NOT NULL
              AND g.away_score > g.home_score

            ORDER BY opp_net_rank ASC NULLS LAST
            LIMIT ?
        '''

        # ── Notable Losses ────────────────────────────────────────
        # Same structure, flipped win/loss condition.
        # "Bad loss" label applied in Python below — a loss to a
        # team ranked outside top 100 NET is flagged is_bad_loss=True.
        notable_losses_sql = '''
            SELECT
                g.game_id,
                g.game_date,
                opp.team_id   AS opp_team_id,
                opp.name      AS opp_name,
                opp.logo_url  AS opp_logo,
                'vs'          AS location,
                g.home_score  AS team_score,
                g.away_score  AS opp_score,
                r.net_rank    AS opp_net_rank
            FROM games g
            JOIN teams opp ON opp.team_id = g.away_team_id
            LEFT JOIN resume_metrics r ON r.team_id = g.away_team_id
            WHERE g.home_team_id = ?
              AND g.home_score IS NOT NULL
              AND g.home_score < g.away_score

            UNION ALL

            SELECT
                g.game_id,
                g.game_date,
                opp.team_id   AS opp_team_id,
                opp.name      AS opp_name,
                opp.logo_url  AS opp_logo,
                '@'           AS location,
                g.away_score  AS team_score,
                g.home_score  AS opp_score,
                r.net_rank    AS opp_net_rank
            FROM games g
            JOIN teams opp ON opp.team_id = g.home_team_id
            LEFT JOIN resume_metrics r ON r.team_id = g.home_team_id
            WHERE g.away_team_id = ?
              AND g.away_score IS NOT NULL
              AND g.away_score < g.home_score

            ORDER BY opp_net_rank ASC NULLS LAST
            LIMIT ?
        '''

        def format_game(row):
            r = dict(row)
            return {
                'game_id':  r['game_id'],
                'date':     r['game_date'],
                'opponent': {
                    'id':       r['opp_team_id'],
                    'name':     r['opp_name'],
                    'logo':     r['opp_logo'],
                    'net_rank': r['opp_net_rank'],
                },
                'location': r['location'],  # "vs" (home) or "@" (away)
                'score': {
                    'team':     r['team_score'],
                    'opponent': r['opp_score'],
                },
            }

        wins_rows   = query_db(quality_wins_sql,   (team_id, team_id, wins_limit))
        losses_rows = query_db(notable_losses_sql, (team_id, team_id, losses_limit))

        quality_wins   = [format_game(r) for r in wins_rows]
        notable_losses = [format_game(r) for r in losses_rows]

        # Flag bad losses — lost to a team ranked outside top 100 NET
        for loss in notable_losses:
            net = loss['opponent']['net_rank']
            loss['is_bad_loss'] = (net is not None and net > 100)

        return jsonify({
            'team_id':       team_id,
            'team_name':     dict(team[0])['name'],
            'quality_wins':  quality_wins,
            'notable_losses': notable_losses,
        })

    # ============================================================
    # BRACKET API ENDPOINTS
    # ============================================================

    @app.route('/api/bracket', methods=['GET'])
    @limit("60/minute")
    @validate_params
    def get_bracket():
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

        teams = query_db('''
            SELECT
                b.team_id, b.seed, b.region,
                t.name, t.conference, t.logo_url, t.primary_color, t.secondary_color,
                r.adj_em, r.rank_adj_em, r.adj_oe, r.adj_de
            FROM bracket b
            JOIN teams t ON b.team_id = t.team_id
            LEFT JOIN ratings r ON b.team_id = r.team_id AND r.season = b.season
            WHERE b.season = ?
            ORDER BY b.region, b.seed
        ''', (season,))

        matchups = query_db('''
            SELECT
                m.id, m.region, m.round, m.game_number, m.matchup_name,
                m.high_seed_team_id, m.low_seed_team_id
            FROM matchups m
            WHERE m.season = ?
            ORDER BY m.region, m.round, m.game_number
        ''', (season,))

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

        return jsonify({'season': season, 'bracket': bracket_data})

    @app.route('/api/bracket/region/<region_name>', methods=['GET'])
    @validate_params
    def get_region(region_name):
        region_name = validate_region(region_name)
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

        teams = query_db('''
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
        ''', (season, region_name))

        matchups = query_db('''
            SELECT
                m.id, m.region, m.round, m.game_number, m.matchup_name,
                m.high_seed_team_id, m.low_seed_team_id,
                t1.name as high_seed_name, b1.seed as high_seed,
                t2.name as low_seed_name, b2.seed as low_seed
            FROM matchups m
            JOIN bracket b1 ON m.high_seed_team_id = b1.team_id AND b1.season = m.season
            JOIN bracket b2 ON m.low_seed_team_id = b2.team_id AND b2.season = m.season
            JOIN teams t1 ON m.high_seed_team_id = t1.team_id
            JOIN teams t2 ON m.low_seed_team_id = t2.team_id
            WHERE m.season = ? AND m.region = ? AND m.round > 0
            ORDER BY m.game_number
        ''', (season, region_name))

        return jsonify({
            'region': region_name,
            'teams': [dict(t) for t in teams],
            'matchups': [dict(m) for m in matchups]
        })

    @app.route('/api/bracket/first-four', methods=['GET'])
    @validate_params
    def get_first_four():
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

        matchups = query_db('''
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
        ''', (season,))

        return jsonify({'first_four': [dict(m) for m in matchups]})

    @app.route('/api/matchup/<int:matchup_id>', methods=['GET'])
    @validate_params
    def get_matchup_detail(matchup_id):
        matchup = query_db('SELECT * FROM matchups WHERE id = ?', (matchup_id,))

        if not matchup:
            return jsonify({'error': 'Matchup not found'}), 404

        matchup_dict = dict(matchup[0])

        teams_data = []
        for team_id in [matchup_dict['high_seed_team_id'], matchup_dict['low_seed_team_id']]:
            team = query_db('''
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
            ''', (team_id,))
            teams_data.append(dict(team[0]) if team else None)

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
        players = query_db('''
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
        ''', (team_id, CURRENT_SEASON))

        return jsonify({'players': [dict(p) for p in players]})

    @app.route('/api/team/<int:team_id>/players/key', methods=['GET'])
    @validate_params
    def get_key_players(team_id):
        players = query_db('''
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
        ''', (team_id, CURRENT_SEASON))

        return jsonify({'players': [dict(p) for p in players]})

    @app.route('/api/player/<int:player_id>', methods=['GET'])
    @validate_params
    def get_player(player_id):
        player = query_db('''
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
        ''', (player_id,))

        if not player:
            return jsonify({'error': 'Player not found'}), 404

        return jsonify(dict(player[0]))

    # ============================================================
    # MOMENTUM TRACKER API ENDPOINTS
    # ============================================================

    @app.route('/api/momentum/rankings')
    @limit("30/minute")
    @validate_params
    def get_momentum_rankings():
        max_limit = app.config.get('MAX_RESULTS_LIMIT', 200)
        limit_val = validate_limit(request.args.get('limit'), default=50, maximum=max_limit)
        min_games = validate_min_games(request.args.get('min_games'))
        trend = validate_trend(request.args.get('trend'))
        tournament_only = validate_boolean(request.args.get('tournament'))
        kenpom_min = validate_kenpom_rank(request.args.get('kenpom_min'), field='kenpom_min')
        kenpom_max = validate_kenpom_rank(request.args.get('kenpom_max'), field='kenpom_max')
        conference = validate_conference(request.args.get('conference'))

        sql = '''
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
            sql += ' AND mc.trend_direction = ?'
            params.append(trend)
        if tournament_only:
            sql += ' AND b.team_id IS NOT NULL'
        if kenpom_min is not None:
            sql += ' AND r.rank_adj_em >= ?'
            params.append(kenpom_min)
        if kenpom_max is not None:
            sql += ' AND r.rank_adj_em <= ?'
            params.append(kenpom_max)
        if conference:
            sql += ' AND t.conference = ?'
            params.append(conference)

        sql += ' ORDER BY mc.momentum_score DESC LIMIT ?'
        params.append(limit_val)

        teams = query_db(sql, params)

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
        team = query_db('''
            SELECT mc.*, t.name, t.conference, t.logo_url, r.rank_adj_em as kenpom_rank,
                   r.adj_em, r.adj_oe, r.adj_de, b.seed, b.region
            FROM momentum_cache mc
            JOIN teams t ON mc.team_id = t.team_id
            JOIN ratings r ON mc.team_id = r.team_id
            LEFT JOIN bracket b ON mc.team_id = b.team_id
            WHERE mc.team_id = ? AND mc.season = ?
        ''', (team_id, CURRENT_SEASON))

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        team = team[0]

        rank = query_db('''
            SELECT COUNT(*) + 1 as rank
            FROM momentum_cache
            WHERE momentum_score > ? AND season = ?
        ''', (team['momentum_score'], CURRENT_SEASON))[0]['rank']

        trajectory = query_db('''
            SELECT snapshot_date, rank_adj_em, adj_em
            FROM momentum_ratings
            WHERE team_id = ?
            ORDER BY snapshot_date
        ''', (team_id,))

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
        max_limit = app.config.get('MAX_RESULTS_LIMIT', 200)
        limit_val = validate_limit(request.args.get('limit'), default=12, maximum=max_limit)
        min_games = validate_min_games(request.args.get('min_games'))

        underdogs = query_db('''
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
        ''', (CURRENT_SEASON, min_games))

        upset_candidates = []

        for team in underdogs:
            seed = team['seed']
            region = team['region']
            opponent_seed = 17 - seed

            opponent = query_db('''
                SELECT mc.*, t.name, t.logo_url, r.rank_adj_em as kenpom_rank, b.seed
                FROM bracket b
                JOIN teams t ON b.team_id = t.team_id
                JOIN ratings r ON b.team_id = r.team_id
                LEFT JOIN momentum_cache mc ON b.team_id = mc.team_id
                WHERE b.region = ? AND b.seed = ?
            ''', (region, opponent_seed))

            if not opponent:
                continue

            opponent = opponent[0]
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
        return jsonify(upset_candidates[:limit_val])

    @app.route('/api/momentum/vulnerable')
    @validate_params
    def get_vulnerable_favorites():
        max_limit = app.config.get('MAX_RESULTS_LIMIT', 200)
        limit_val = validate_limit(request.args.get('limit'), default=15, maximum=max_limit)
        min_games = validate_min_games(request.args.get('min_games'))

        teams = query_db('''
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
        ''', (CURRENT_SEASON, min_games, limit_val))

        return jsonify([{
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
        } for team in teams])

    @app.route('/api/momentum/conferences')
    def get_momentum_conferences():
        conferences = query_db('''
            SELECT DISTINCT t.conference
            FROM teams t
            WHERE t.season = ?
            ORDER BY t.conference
        ''', (CURRENT_SEASON,))
        return jsonify([c['conference'] for c in conferences])

    # ============================================================
    # CONTENDERS ENDPOINT
    # ============================================================

    @app.route('/api/contenders', methods=['GET'])
    @validate_params
    def get_contenders():
        season = validate_season(request.args.get('season')) or CURRENT_SEASON

        contenders = query_db('''
            SELECT cs.*, t.name, t.conference, t.logo_url,
                   t.primary_color, t.secondary_color,
                   r.rank_adj_em, r.adj_em, r.adj_oe, r.adj_de,
                   b.seed, b.region
            FROM contender_scores cs
            JOIN teams t ON cs.team_id = t.team_id
            LEFT JOIN ratings r ON cs.team_id = r.team_id AND r.season = cs.season
            LEFT JOIN bracket b ON cs.team_id = b.team_id AND b.season = cs.season
            WHERE cs.season = ?
            ORDER BY cs.contender_score DESC
        ''', (season,))

        return jsonify([dict(c) for c in contenders])

    return app


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == '__main__':
    app = create_app()

    if not USE_POSTGRES and not DATABASE.exists():
        print(f"ERROR: Database not found at {DATABASE}")
        print("Run: python setup.py")
        exit(1)

    db_type = "PostgreSQL" if USE_POSTGRES else f"SQLite ({DATABASE})"
    print(f"Using database: {db_type}")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print("Starting Flask server on http://localhost:5000")
    app.run(port=5000)