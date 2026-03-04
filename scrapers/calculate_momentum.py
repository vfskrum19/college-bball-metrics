"""
Calculate Momentum Scores for all teams
Combines game results, vs-expected performance, and rating trajectory

Run from project root:
    python scrapers/calculate_momentum.py              # Calculate for all teams
    python scrapers/calculate_momentum.py --team Duke  # Calculate for specific team
    python scrapers/calculate_momentum.py --top 20     # Show top 20 hottest teams
"""

import sys
from pathlib import Path
from datetime import datetime
import json
import argparse

# ============================================================
# DATABASE SETUP
# ============================================================
# sys.path.insert ensures Python can find utils/db.py whether
# this script is run from the project root or scrapers/ folder.
# The db utility handles SQLite (local) vs PostgreSQL (Railway)
# automatically based on the DATABASE_URL environment variable.
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from utils.db import get_db, close_db, execute, commit, db_type

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CURRENT_SEASON = 2026

WEIGHTS = {
    'win_pct': 25,
    'vs_expected': 30,
    'win_streak': 10,
    'rank_trajectory': 20,
    'margin': 15,
}


def get_team_last_n_games(db, team_id, n=10):
    """Get a team's last N completed games with scores"""
    cursor = execute(db, '''
        SELECT
            g.game_date,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score,
            g.home_pred,
            g.away_pred,
            g.home_win_prob,
            ht.name as home_name,
            at.name as away_name
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        WHERE (g.home_team_id = ? OR g.away_team_id = ?)
          AND g.home_score IS NOT NULL
        ORDER BY g.game_date DESC
        LIMIT ?
    ''', (team_id, team_id, n))
    games = cursor.fetchall()

    result = []
    for g in games:
        is_home = g['home_team_id'] == team_id

        if is_home:
            team_score = g['home_score']
            opp_score = g['away_score']
            team_pred = g['home_pred']
            opp_pred = g['away_pred']
            opponent = g['away_name']
            win_prob = g['home_win_prob']
        else:
            team_score = g['away_score']
            opp_score = g['home_score']
            team_pred = g['away_pred']
            opp_pred = g['home_pred']
            opponent = g['home_name']
            win_prob = 1 - g['home_win_prob'] if g['home_win_prob'] else None

        won = team_score > opp_score
        margin = team_score - opp_score

        vs_expected = None
        if team_pred and opp_pred:
            predicted_margin = team_pred - opp_pred
            vs_expected = margin - predicted_margin

        result.append({
            'date': g['game_date'],
            'opponent': opponent,
            'team_score': team_score,
            'opp_score': opp_score,
            'won': won,
            'margin': margin,
            'vs_expected': vs_expected,
            'win_prob': win_prob,
            'is_home': is_home
        })

    return result


def get_team_rank_trajectory(db, team_id):
    """Get team's rank change over the snapshot period"""
    cursor = execute(db, '''
        SELECT snapshot_date, rank_adj_em, adj_em
        FROM momentum_ratings
        WHERE team_id = ?
        ORDER BY snapshot_date
    ''', (team_id,))
    snapshots = cursor.fetchall()

    if len(snapshots) < 2:
        cursor = execute(db, '''
            SELECT rank_adj_em, adj_em
            FROM ratings
            WHERE team_id = ?
        ''', (team_id,))
        current = cursor.fetchone()
        if current:
            return current['rank_adj_em'], current['rank_adj_em'], 0, 0
        return None, None, 0, 0

    start = snapshots[0]
    end = snapshots[-1]
    rank_change = start['rank_adj_em'] - end['rank_adj_em']
    adj_em_change = end['adj_em'] - start['adj_em']

    return start['rank_adj_em'], end['rank_adj_em'], rank_change, adj_em_change


def calculate_win_streak(games):
    if not games:
        return 0, 0
    win_streak = 0
    loss_streak = 0
    if games[0]['won']:
        for g in games:
            if g['won']: win_streak += 1
            else: break
    else:
        for g in games:
            if not g['won']: loss_streak += 1
            else: break
    return win_streak, loss_streak


def calculate_momentum_score(team_data):
    score = 0
    games_played = team_data.get('games_played_l10', 0)
    if games_played > 0:
        win_pct = team_data.get('wins_l10', 0) / games_played
        score += win_pct * WEIGHTS['win_pct']

    avg_vs_exp = team_data.get('avg_vs_expected_l10')
    if avg_vs_exp is not None:
        vs_exp_score = (avg_vs_exp + 10) / 20 * WEIGHTS['vs_expected']
        score += max(0, min(WEIGHTS['vs_expected'], vs_exp_score))
    else:
        score += WEIGHTS['vs_expected'] / 2

    win_streak = team_data.get('win_streak', 0)
    loss_streak = team_data.get('loss_streak', 0)
    if win_streak >= 6: score += WEIGHTS['win_streak']
    elif win_streak >= 4: score += WEIGHTS['win_streak'] * 0.7
    elif win_streak >= 2: score += WEIGHTS['win_streak'] * 0.4
    elif loss_streak >= 4: score -= WEIGHTS['win_streak'] * 0.5

    rank_change = team_data.get('rank_change_l10', 0)
    rank_score = (rank_change + 20) / 40 * WEIGHTS['rank_trajectory']
    score += max(0, min(WEIGHTS['rank_trajectory'], rank_score))

    avg_margin = team_data.get('avg_margin_l10', 0)
    if avg_margin is not None:
        margin_score = (avg_margin + 15) / 30 * WEIGHTS['margin']
        score += max(0, min(WEIGHTS['margin'], margin_score))

    return round(score, 1)


def determine_trend(team_data):
    score = team_data.get('momentum_score', 50)
    win_streak = team_data.get('win_streak', 0)
    loss_streak = team_data.get('loss_streak', 0)
    avg_vs_exp = team_data.get('avg_vs_expected_l10', 0) or 0

    if score >= 75 and win_streak >= 4: return 'hot'
    elif score >= 65 and (win_streak >= 3 or avg_vs_exp >= 5): return 'rising'
    elif score <= 35 and loss_streak >= 4: return 'cold'
    elif score <= 45 and (loss_streak >= 3 or avg_vs_exp <= -5): return 'falling'
    else: return 'stable'


def calculate_team_momentum(db, team_id, team_name):
    games = get_team_last_n_games(db, team_id, n=10)
    rank_start, rank_current, rank_change, adj_em_change = get_team_rank_trajectory(db, team_id)

    wins = sum(1 for g in games if g['won'])
    losses = len(games) - wins
    margins = [g['margin'] for g in games]
    avg_margin = sum(margins) / len(margins) if margins else None
    vs_expected_values = [g['vs_expected'] for g in games if g['vs_expected'] is not None]
    avg_vs_expected = sum(vs_expected_values) / len(vs_expected_values) if vs_expected_values else None
    win_streak, loss_streak = calculate_win_streak(games)
    best_win = max([g['margin'] for g in games if g['won']], default=None)
    worst_loss = min([g['margin'] for g in games if not g['won']], default=None)
    last_game_date = games[0]['date'] if games else None

    team_data = {
        'team_id': team_id,
        'games_played_l10': len(games),
        'wins_l10': wins,
        'losses_l10': losses,
        'win_streak': win_streak,
        'loss_streak': loss_streak,
        'avg_margin_l10': avg_margin,
        'avg_vs_expected_l10': avg_vs_expected,
        'best_win_margin': best_win,
        'worst_loss_margin': worst_loss,
        'rank_change_l10': rank_change,
        'adj_em_change_l10': adj_em_change,
        'rank_start_l10': rank_start,
        'rank_current': rank_current,
        'last_game_date': last_game_date,
        'games_data': json.dumps([{
            'date': g['date'],
            'opponent': g['opponent'],
            'score': f"{g['team_score']}-{g['opp_score']}",
            'won': g['won'],
            'margin': g['margin'],
            'vs_expected': round(g['vs_expected'], 1) if g['vs_expected'] else None
        } for g in games])
    }

    team_data['momentum_score'] = calculate_momentum_score(team_data)
    team_data['trend_direction'] = determine_trend(team_data)
    return team_data


def update_momentum_cache(season=CURRENT_SEASON):
    print(f"\n{'='*60}")
    print(f"Calculating Momentum Scores [{db_type()}]")
    print(f"{'='*60}\n")

    db = get_db()
    teams = execute(db, '''
        SELECT t.team_id, t.name, r.rank_adj_em
        FROM teams t
        JOIN ratings r ON t.team_id = r.team_id
        WHERE t.season = ?
        ORDER BY r.rank_adj_em
    ''', (season,)).fetchall()

    print(f"Calculating momentum for {len(teams)} teams...\n")
    execute(db, 'DELETE FROM momentum_cache WHERE season = ?', (season,))

    calculated = 0
    skipped = 0

    for i, team in enumerate(teams):
        team_id = team['team_id']
        team_name = team['name']

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(teams)} teams...")

        try:
            team_data = calculate_team_momentum(db, team_id, team_name)

            if team_data['games_played_l10'] == 0:
                skipped += 1
                continue

            execute(db, '''
                INSERT INTO momentum_cache (
                    team_id, season, calculated_at,
                    games_played_l10, wins_l10, losses_l10,
                    win_streak, loss_streak,
                    avg_margin_l10, avg_vs_expected_l10,
                    best_win_margin, worst_loss_margin,
                    rank_change_l10, adj_em_change_l10,
                    rank_start_l10, rank_current,
                    momentum_score, trend_direction,
                    last_game_date, games_data
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                team_id, season, datetime.now().isoformat(),
                team_data['games_played_l10'], team_data['wins_l10'], team_data['losses_l10'],
                team_data['win_streak'], team_data['loss_streak'],
                team_data['avg_margin_l10'], team_data['avg_vs_expected_l10'],
                team_data['best_win_margin'], team_data['worst_loss_margin'],
                team_data['rank_change_l10'], team_data['adj_em_change_l10'],
                team_data['rank_start_l10'], team_data['rank_current'],
                team_data['momentum_score'], team_data['trend_direction'],
                team_data['last_game_date'], team_data['games_data']
            ))
            calculated += 1

        except Exception as e:
            print(f"  ⚠ Error calculating {team_name}: {e}")
            skipped += 1

    commit(db)
    close_db(db)

    print(f"\n{'='*60}")
    print(f"  Teams calculated: {calculated}")
    print(f"  Teams skipped (no games): {skipped}")
    print(f"{'='*60}\n")
    return calculated


def show_top_teams(n=20, trend_filter=None, min_games=5, tournament_only=False,
                   kenpom_range=None, seed_range=None, conference=None):
    db = get_db()
    query = '''
        SELECT mc.*, t.name, t.conference, r.rank_adj_em as kenpom_rank, b.seed
        FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        JOIN ratings r ON mc.team_id = r.team_id
        LEFT JOIN bracket b ON mc.team_id = b.team_id
        WHERE mc.season = ? AND mc.games_played_l10 >= ?
    '''
    params = [CURRENT_SEASON, min_games]
    if trend_filter: query += ' AND mc.trend_direction = ?'; params.append(trend_filter)
    if tournament_only: query += ' AND b.team_id IS NOT NULL'
    if kenpom_range: query += ' AND r.rank_adj_em >= ? AND r.rank_adj_em <= ?'; params.extend(kenpom_range)
    if seed_range: query += ' AND b.seed >= ? AND b.seed <= ?'; params.extend(seed_range)
    if conference: query += ' AND t.conference = ?'; params.append(conference)
    query += ' ORDER BY mc.momentum_score DESC LIMIT ?'
    params.append(n)

    teams = execute(db, query, params).fetchall()
    close_db(db)

    if not teams:
        print("No teams found. Check filters or run calculate_momentum.py first.")
        return

    trend_icons = {'hot': '🔥', 'rising': '📈', 'stable': '➡️', 'falling': '📉', 'cold': '🧊'}
    print(f"\n{'='*95}\nTop {n} Teams by Momentum\n{'='*95}")
    print(f"{'Rank':<5} {'Team':<22} {'KP#':<5} {'Record':<8} {'Streak':<8} {'vsExp':<8} {'RkChg':<8} {'Score':<8} {'Trend':<6}")
    print("-" * 95)

    for i, team in enumerate(teams, 1):
        record = f"{team['wins_l10']}-{team['losses_l10']}"
        streak = f"W{team['win_streak']}" if team['win_streak'] > 0 else (f"L{team['loss_streak']}" if team['loss_streak'] > 0 else "-")
        vs_exp = f"{team['avg_vs_expected_l10']:+.1f}" if team['avg_vs_expected_l10'] else "N/A"
        rk_chg = f"{team['rank_change_l10']:+d}" if team['rank_change_l10'] else "0"
        kp_rank = f"#{team['kenpom_rank']}" if team['kenpom_rank'] else "N/A"
        print(f"{i:<5} {team['name']:<22} {kp_rank:<5} {record:<8} {streak:<8} {vs_exp:<8} {rk_chg:<8} {team['momentum_score']:<8.1f} {trend_icons.get(team['trend_direction'], '')}")

    print(f"{'='*95}\n")


def show_team_detail(team_name):
    db = get_db()
    team = execute(db, '''
        SELECT mc.*, t.name, t.conference FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        WHERE t.name LIKE ? AND mc.season = ?
    ''', (f'%{team_name}%', CURRENT_SEASON)).fetchone()

    if not team:
        print(f"Team '{team_name}' not found")
        close_db(db)
        return

    rank = execute(db, 'SELECT COUNT(*) + 1 as rank FROM momentum_cache WHERE momentum_score > ? AND season = ?',
                   (team['momentum_score'], CURRENT_SEASON)).fetchone()['rank']
    close_db(db)

    print(f"\n{'='*60}\n{team['name']} - Momentum Analysis\n{'='*60}")
    print(f"  Rank: #{rank}  Score: {team['momentum_score']:.1f}/100  L10: {team['wins_l10']}-{team['losses_l10']}")

    if team['games_data']:
        games = json.loads(team['games_data'])
        print(f"\n  Recent Games:")
        for g in games[:5]:
            result = "W" if g['won'] else "L"
            vs_exp = f"({g['vs_expected']:+.1f})" if g['vs_expected'] else ""
            print(f"    {g['date']}: {result} vs {g['opponent']} {g['score']} {vs_exp}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Calculate momentum scores')
    parser.add_argument('--team', type=str)
    parser.add_argument('--top', type=int, default=20)
    parser.add_argument('--min-games', type=int, default=5)
    parser.add_argument('--hot', action='store_true')
    parser.add_argument('--cold', action='store_true')
    parser.add_argument('--calculate', action='store_true')
    parser.add_argument('--tournament', action='store_true')
    parser.add_argument('--kenpom', type=str)
    parser.add_argument('--seeds', type=str)
    parser.add_argument('--conference', type=str)
    args = parser.parse_args()

    kenpom_range = None
    if args.kenpom:
        parts = args.kenpom.split('-')
        kenpom_range = (int(parts[0]), int(parts[1]))

    seed_range = None
    if args.seeds:
        parts = args.seeds.split('-')
        seed_range = (int(parts[0]), int(parts[1]))

    if args.calculate or (args.team is None and not args.hot and not args.cold
                          and not args.tournament and not kenpom_range
                          and not seed_range and not args.conference):
        update_momentum_cache()

    if args.team:
        show_team_detail(args.team)
    else:
        trend = 'hot' if args.hot else ('cold' if args.cold else None)
        show_top_teams(args.top, trend_filter=trend, min_games=args.min_games,
                       tournament_only=args.tournament, kenpom_range=kenpom_range,
                       seed_range=seed_range, conference=args.conference)