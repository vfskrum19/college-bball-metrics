"""
Calculate Momentum Scores for all teams
Combines game results, vs-expected performance, and rating trajectory

Run from project root:
    python scrapers/calculate_momentum.py              # Calculate for all teams
    python scrapers/calculate_momentum.py --team Duke  # Calculate for specific team
    python scrapers/calculate_momentum.py --top 20     # Show top 20 hottest teams
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import sqlite3
from datetime import datetime, timedelta
import json
import argparse

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'
CURRENT_SEASON = 2026

# Momentum calculation weights
WEIGHTS = {
    'win_pct': 25,           # Win percentage in last 10 games (0-25 points)
    'vs_expected': 30,       # Performance vs KenPom predictions (0-30 points)
    'win_streak': 10,        # Current win streak bonus (0-10 points)
    'rank_trajectory': 20,   # Rank improvement over period (0-20 points)
    'margin': 15,            # Average margin of victory (0-15 points)
}

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def get_team_last_n_games(cursor, team_id, n=10):
    """
    Get a team's last N games with scores
    Returns list of game dicts with actual and predicted results
    """
    games = cursor.execute('''
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
    ''', (team_id, team_id, n)).fetchall()
    
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
        
        # Calculate vs expected
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

def get_team_rank_trajectory(cursor, team_id, days_back=30):
    """
    Get team's rank change over a period using momentum_ratings snapshots
    Returns (start_rank, current_rank, rank_change, adj_em_change)
    """
    # Get earliest and latest snapshots
    snapshots = cursor.execute('''
        SELECT snapshot_date, rank_adj_em, adj_em
        FROM momentum_ratings
        WHERE team_id = ?
        ORDER BY snapshot_date
    ''', (team_id,)).fetchall()
    
    if len(snapshots) < 2:
        # Fall back to current ratings
        current = cursor.execute('''
            SELECT rank_adj_em, adj_em
            FROM ratings
            WHERE team_id = ?
        ''', (team_id,)).fetchone()
        
        if current:
            return current['rank_adj_em'], current['rank_adj_em'], 0, 0
        return None, None, 0, 0
    
    start = snapshots[0]
    end = snapshots[-1]
    
    rank_change = start['rank_adj_em'] - end['rank_adj_em']  # Positive = improved
    adj_em_change = end['adj_em'] - start['adj_em']  # Positive = improved
    
    return start['rank_adj_em'], end['rank_adj_em'], rank_change, adj_em_change

def calculate_win_streak(games):
    """Calculate current win/loss streak from games list (most recent first)"""
    if not games:
        return 0, 0
    
    win_streak = 0
    loss_streak = 0
    
    # Check if currently on a win streak
    if games[0]['won']:
        for g in games:
            if g['won']:
                win_streak += 1
            else:
                break
    else:
        for g in games:
            if not g['won']:
                loss_streak += 1
            else:
                break
    
    return win_streak, loss_streak

def calculate_momentum_score(team_data):
    """
    Calculate composite momentum score (0-100)
    
    team_data should contain:
    - wins_l10, losses_l10
    - avg_vs_expected
    - win_streak, loss_streak
    - rank_change
    - avg_margin
    """
    score = 0
    
    # 1. Win percentage (0-25 points)
    games_played = team_data.get('games_played_l10', 0)
    if games_played > 0:
        win_pct = team_data.get('wins_l10', 0) / games_played
        score += win_pct * WEIGHTS['win_pct']
    
    # 2. Vs Expected performance (0-30 points)
    # Average of +10 or better = full points, -10 or worse = 0 points
    avg_vs_exp = team_data.get('avg_vs_expected_l10')
    if avg_vs_exp is not None:
        # Scale: -10 = 0 points, 0 = 15 points, +10 = 30 points
        vs_exp_score = (avg_vs_exp + 10) / 20 * WEIGHTS['vs_expected']
        vs_exp_score = max(0, min(WEIGHTS['vs_expected'], vs_exp_score))
        score += vs_exp_score
    else:
        # If no vs_expected data, give neutral score
        score += WEIGHTS['vs_expected'] / 2
    
    # 3. Win streak bonus (0-10 points)
    win_streak = team_data.get('win_streak', 0)
    loss_streak = team_data.get('loss_streak', 0)
    if win_streak >= 6:
        score += WEIGHTS['win_streak']
    elif win_streak >= 4:
        score += WEIGHTS['win_streak'] * 0.7
    elif win_streak >= 2:
        score += WEIGHTS['win_streak'] * 0.4
    elif loss_streak >= 4:
        score -= WEIGHTS['win_streak'] * 0.5  # Penalty for long losing streak
    
    # 4. Rank trajectory (0-20 points)
    # Improving 20+ spots = full points, dropping 20+ = 0
    rank_change = team_data.get('rank_change_l10', 0)
    rank_score = (rank_change + 20) / 40 * WEIGHTS['rank_trajectory']
    rank_score = max(0, min(WEIGHTS['rank_trajectory'], rank_score))
    score += rank_score
    
    # 5. Average margin (0-15 points)
    # +15 or better = full points, -15 or worse = 0
    avg_margin = team_data.get('avg_margin_l10', 0)
    if avg_margin is not None:
        margin_score = (avg_margin + 15) / 30 * WEIGHTS['margin']
        margin_score = max(0, min(WEIGHTS['margin'], margin_score))
        score += margin_score
    
    return round(score, 1)

def determine_trend(team_data):
    """Determine trend direction based on data"""
    score = team_data.get('momentum_score', 50)
    win_streak = team_data.get('win_streak', 0)
    loss_streak = team_data.get('loss_streak', 0)
    rank_change = team_data.get('rank_change_l10', 0)
    avg_vs_exp = team_data.get('avg_vs_expected_l10', 0) or 0
    
    if score >= 75 and win_streak >= 4:
        return 'hot'
    elif score >= 65 and (win_streak >= 3 or avg_vs_exp >= 5):
        return 'rising'
    elif score <= 35 and loss_streak >= 4:
        return 'cold'
    elif score <= 45 and (loss_streak >= 3 or avg_vs_exp <= -5):
        return 'falling'
    else:
        return 'stable'

def calculate_team_momentum(cursor, team_id, team_name):
    """Calculate full momentum data for a single team"""
    
    # Get last 10 games
    games = get_team_last_n_games(cursor, team_id, n=10)
    
    # Get rank trajectory
    rank_start, rank_current, rank_change, adj_em_change = get_team_rank_trajectory(cursor, team_id)
    
    # Calculate stats from games
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
    
    # Build team data dict
    team_data = {
        'team_id': team_id,
        'team_name': team_name,
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
    
    # Calculate momentum score
    team_data['momentum_score'] = calculate_momentum_score(team_data)
    team_data['trend_direction'] = determine_trend(team_data)
    
    return team_data

def update_momentum_cache(season=CURRENT_SEASON):
    """Calculate and cache momentum scores for all teams"""
    
    print(f"\n{'='*60}")
    print("Calculating Momentum Scores")
    print(f"{'='*60}\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # Get all teams
    teams = cursor.execute('''
        SELECT t.team_id, t.name, r.rank_adj_em
        FROM teams t
        JOIN ratings r ON t.team_id = r.team_id
        WHERE t.season = ?
        ORDER BY r.rank_adj_em
    ''', (season,)).fetchall()
    
    print(f"Calculating momentum for {len(teams)} teams...\n")
    
    # Clear existing cache
    cursor.execute('DELETE FROM momentum_cache WHERE season = ?', (season,))
    
    calculated = 0
    skipped = 0
    
    for i, team in enumerate(teams):
        team_id = team['team_id']
        team_name = team['name']
        
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(teams)} teams...")
        
        try:
            team_data = calculate_team_momentum(cursor, team_id, team_name)
            
            # Skip teams with no games
            if team_data['games_played_l10'] == 0:
                skipped += 1
                continue
            
            # Insert into cache
            cursor.execute('''
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
                team_data['games_played_l10'],
                team_data['wins_l10'],
                team_data['losses_l10'],
                team_data['win_streak'],
                team_data['loss_streak'],
                team_data['avg_margin_l10'],
                team_data['avg_vs_expected_l10'],
                team_data['best_win_margin'],
                team_data['worst_loss_margin'],
                team_data['rank_change_l10'],
                team_data['adj_em_change_l10'],
                team_data['rank_start_l10'],
                team_data['rank_current'],
                team_data['momentum_score'],
                team_data['trend_direction'],
                team_data['last_game_date'],
                team_data['games_data']
            ))
            calculated += 1
            
        except Exception as e:
            print(f"  ⚠ Error calculating {team_name}: {e}")
            skipped += 1
    
    db.commit()
    db.close()
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Teams calculated: {calculated}")
    print(f"  Teams skipped (no games): {skipped}")
    print(f"{'='*60}\n")
    
    return calculated

def show_top_teams(n=20, trend_filter=None, min_games=5, tournament_only=False, 
                   kenpom_range=None, seed_range=None, conference=None):
    """Display top N teams by momentum score with various filters"""
    
    db = get_db()
    cursor = db.cursor()
    
    query = '''
        SELECT mc.*, t.name, t.conference, r.rank_adj_em as kenpom_rank, b.seed
        FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        JOIN ratings r ON mc.team_id = r.team_id
        LEFT JOIN bracket b ON mc.team_id = b.team_id
        WHERE mc.season = ?
          AND mc.games_played_l10 >= ?
    '''
    params = [CURRENT_SEASON, min_games]
    
    if trend_filter:
        query += ' AND mc.trend_direction = ?'
        params.append(trend_filter)
    
    if tournament_only:
        query += ' AND b.team_id IS NOT NULL'
    
    if kenpom_range:
        query += ' AND r.rank_adj_em >= ? AND r.rank_adj_em <= ?'
        params.extend(kenpom_range)
    
    if seed_range:
        query += ' AND b.seed >= ? AND b.seed <= ?'
        params.extend(seed_range)
    
    if conference:
        query += ' AND t.conference = ?'
        params.append(conference)
    
    query += ' ORDER BY mc.momentum_score DESC LIMIT ?'
    params.append(n)
    
    teams = cursor.execute(query, params).fetchall()
    db.close()
    
    if not teams:
        print("No teams found matching criteria. Check filters or run calculate_momentum.py first.")
        return
    
    # Build dynamic title
    title = f"Top {n} Teams by Momentum"
    filters = []
    if trend_filter:
        filters.append(trend_filter)
    if tournament_only:
        filters.append("tournament")
    if kenpom_range:
        filters.append(f"KP #{kenpom_range[0]}-{kenpom_range[1]}")
    if seed_range:
        filters.append(f"seeds {seed_range[0]}-{seed_range[1]}")
    if conference:
        filters.append(conference)
    if filters:
        title += f" ({', '.join(filters)})"
    
    # Determine if we should show seed column
    show_seed = tournament_only or seed_range
    
    print(f"\n{'='*95}")
    print(title)
    print(f"{'='*95}")
    
    if show_seed:
        print(f"{'Rank':<5} {'Team':<22} {'Seed':<5} {'KP#':<5} {'Record':<8} {'Streak':<8} {'vsExp':<8} {'RkChg':<8} {'Score':<8} {'Trend':<6}")
    else:
        print(f"{'Rank':<5} {'Team':<22} {'KP#':<5} {'Record':<8} {'Streak':<8} {'vsExp':<8} {'RkChg':<8} {'Score':<8} {'Trend':<6}")
    print("-" * 95)
    
    for i, team in enumerate(teams, 1):
        record = f"{team['wins_l10']}-{team['losses_l10']}"
        
        if team['win_streak'] > 0:
            streak = f"W{team['win_streak']}"
        elif team['loss_streak'] > 0:
            streak = f"L{team['loss_streak']}"
        else:
            streak = "-"
        
        vs_exp = f"{team['avg_vs_expected_l10']:+.1f}" if team['avg_vs_expected_l10'] else "N/A"
        rk_chg = f"{team['rank_change_l10']:+d}" if team['rank_change_l10'] else "0"
        kp_rank = f"#{team['kenpom_rank']}" if team['kenpom_rank'] else "N/A"
        seed = f"({team['seed']})" if team['seed'] else ""
        
        trend_icons = {
            'hot': '🔥',
            'rising': '📈',
            'stable': '➡️',
            'falling': '📉',
            'cold': '🧊'
        }
        trend = trend_icons.get(team['trend_direction'], '')
        
        if show_seed:
            print(f"{i:<5} {team['name']:<22} {seed:<5} {kp_rank:<5} {record:<8} {streak:<8} {vs_exp:<8} {rk_chg:<8} {team['momentum_score']:<8.1f} {trend}")
        else:
            print(f"{i:<5} {team['name']:<22} {kp_rank:<5} {record:<8} {streak:<8} {vs_exp:<8} {rk_chg:<8} {team['momentum_score']:<8.1f} {trend}")
    
    print(f"{'='*95}\n")

def show_upset_candidates(n=12, min_games=5, min_upset_score=35):
    """
    Show teams with high upset potential
    Limited to seeds 10-15 (true underdogs, excluding 16s which rarely upset)
    Shows opponent context and matchup factors
    """
    db = get_db()
    cursor = db.cursor()
    
    # Get tournament teams with momentum data (seeds 10-15 only - no 16s)
    underdogs = cursor.execute('''
        SELECT mc.*, t.name, t.conference, r.rank_adj_em as kenpom_rank, 
               b.seed, b.region,
               ff.efg_pct, ff.to_pct, ff.or_pct, ff.ft_rate,
               r.adj_tempo
        FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        JOIN ratings r ON mc.team_id = r.team_id
        JOIN bracket b ON mc.team_id = b.team_id
        LEFT JOIN four_factors ff ON mc.team_id = ff.team_id
        WHERE mc.season = ?
          AND mc.games_played_l10 >= ?
          AND b.seed >= 10 AND b.seed <= 15
        ORDER BY mc.momentum_score DESC
    ''', (CURRENT_SEASON, min_games)).fetchall()
    
    if not underdogs:
        print("No tournament underdogs found. Make sure bracket is populated.")
        db.close()
        return
    
    # For each underdog, find their likely first-round opponent
    upset_candidates = []
    
    for team in underdogs:
        seed = team['seed']
        region = team['region']
        
        # Calculate opponent seed (1v16, 2v15, 3v14, etc.)
        opponent_seed = 17 - seed
        
        # Find the opponent
        opponent = cursor.execute('''
            SELECT mc.*, t.name, t.conference, r.rank_adj_em as kenpom_rank,
                   b.seed, ff.efg_pct, ff.to_pct, ff.or_pct, ff.ft_rate,
                   r.adj_tempo
            FROM bracket b
            JOIN teams t ON b.team_id = t.team_id
            JOIN ratings r ON b.team_id = r.team_id
            LEFT JOIN momentum_cache mc ON b.team_id = mc.team_id
            LEFT JOIN four_factors ff ON b.team_id = ff.team_id
            WHERE b.region = ? AND b.seed = ?
        ''', (region, opponent_seed)).fetchone()
        
        if not opponent:
            continue
        
        # Calculate matchup-based upset score
        momentum = team['momentum_score'] or 50
        vs_expected = team['avg_vs_expected_l10'] or 0
        rank_change = team['rank_change_l10'] or 0
        win_streak = team['win_streak'] or 0
        
        opp_momentum = opponent['momentum_score'] or 50
        opp_vs_expected = opponent['avg_vs_expected_l10'] or 0
        
        # Momentum differential (positive = underdog has better momentum)
        momentum_diff = momentum - opp_momentum
        
        # Is opponent slumping?
        opp_slumping = opp_momentum < 50 or opp_vs_expected < -2
        
        # Tempo analysis - slow teams can neutralize athletic advantages
        underdog_tempo = team['adj_tempo'] or 68
        opp_tempo = opponent['adj_tempo'] or 68
        tempo_advantage = underdog_tempo < 66  # Slow tempo can level playing field
        
        # Upset potential formula
        upset_score = (
            momentum * 0.35 +                      # Base momentum (35%)
            (vs_expected + 10) * 1.5 +             # Beating expectations (scaled)
            momentum_diff * 0.5 +                  # Momentum edge over opponent
            min(rank_change, 30) * 0.4 +           # Rising trajectory
            win_streak * 2 +                       # Win streak bonus
            (15 if opp_slumping else 0) +          # Bonus if opponent is cold
            (10 if tempo_advantage else 0)         # Tempo advantage bonus
        )
        
        upset_candidates.append({
            **dict(team),
            'opponent_name': opponent['name'],
            'opponent_seed': opponent_seed,
            'opponent_momentum': opp_momentum,
            'opponent_vs_exp': opp_vs_expected,
            'opp_slumping': opp_slumping,
            'momentum_diff': momentum_diff,
            'upset_score': round(upset_score, 1)
        })
    
    db.close()
    
    # Sort by upset score and filter by minimum
    upset_candidates.sort(key=lambda x: x['upset_score'], reverse=True)
    upset_candidates = [c for c in upset_candidates if c['upset_score'] >= min_upset_score]
    upset_candidates = upset_candidates[:n]
    
    if not upset_candidates:
        print("No strong upset candidates found meeting the criteria.")
        return
    
    print(f"\n{'='*115}")
    print(f"🎯 Top {len(upset_candidates)} First Round Upset Candidates (Seeds 10-15)")
    print(f"{'='*115}")
    print(f"{'Rank':<4} {'Underdog':<18} {'Seed':<5} {'vs Opponent':<18} {'Momentum':<12} {'vsExp':<8} {'MomDiff':<8} {'Upset':<7} {'Alert':<12}")
    print("-" * 115)
    
    for i, team in enumerate(upset_candidates, 1):
        matchup = f"({team['seed']}) vs ({team['opponent_seed']})"
        mom_comparison = f"{team['momentum_score']:.0f} vs {team['opponent_momentum']:.0f}"
        vs_exp = f"{team['avg_vs_expected_l10']:+.1f}" if team['avg_vs_expected_l10'] else "N/A"
        mom_diff = f"{team['momentum_diff']:+.1f}"
        
        # Alert flags
        alerts = []
        if team['opp_slumping']:
            alerts.append("⚠️OPP COLD")
        if team['win_streak'] and team['win_streak'] >= 5:
            alerts.append(f"🔥W{team['win_streak']}")
        if team['rank_change_l10'] and team['rank_change_l10'] >= 20:
            alerts.append("📈RISING")
        
        alert_str = " ".join(alerts) if alerts else ""
        
        print(f"{i:<4} {team['name']:<18} {matchup:<5} {team['opponent_name']:<18} {mom_comparison:<12} {vs_exp:<8} {mom_diff:<8} {team['upset_score']:<7.1f} {alert_str}")
    
    print(f"{'='*115}")
    print("📊 MomDiff = Underdog momentum minus Opponent momentum (positive = edge)")
    print("⚠️  OPP COLD = Opponent has momentum < 50 or negative vs-expected")
    print(f"{'='*115}\n")


def show_vulnerable_favorites(n=15, min_games=5):
    """
    Show top seeds that might be vulnerable to upsets
    High seeds with low momentum or negative vs-expected
    """
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
    ''', (CURRENT_SEASON, min_games, n)).fetchall()
    
    db.close()
    
    if not teams:
        print("No tournament teams found.")
        return
    
    print(f"\n{'='*100}")
    print(f"⚠️  Vulnerable Favorites (Top 6 Seeds with Low Momentum)")
    print(f"{'='*100}")
    print(f"{'Rank':<5} {'Team':<22} {'Seed':<5} {'Region':<8} {'Record':<8} {'vsExp':<8} {'RkChg':<8} {'Score':<8} {'Trend':<6}")
    print("-" * 100)
    
    for i, team in enumerate(teams, 1):
        record = f"{team['wins_l10']}-{team['losses_l10']}"
        seed = f"({team['seed']})" if team['seed'] else ""
        region = team['region'][:6] if team['region'] else ""
        vs_exp = f"{team['avg_vs_expected_l10']:+.1f}" if team['avg_vs_expected_l10'] else "N/A"
        rk_chg = f"{team['rank_change_l10']:+d}" if team['rank_change_l10'] else "0"
        
        trend_icons = {
            'hot': '🔥',
            'rising': '📈',
            'stable': '➡️',
            'falling': '📉',
            'cold': '🧊'
        }
        trend = trend_icons.get(team['trend_direction'], '')
        
        print(f"{i:<5} {team['name']:<22} {seed:<5} {region:<8} {record:<8} {vs_exp:<8} {rk_chg:<8} {team['momentum_score']:<8.1f} {trend}")
    
    print(f"{'='*100}")
    print("💡 These favored teams are slumping - consider picking against them in early rounds")
    print(f"{'='*100}\n")


def show_team_detail(team_name):
    """Show detailed momentum breakdown for a specific team"""
    
    db = get_db()
    cursor = db.cursor()
    
    # Find team
    team = cursor.execute('''
        SELECT mc.*, t.name, t.conference
        FROM momentum_cache mc
        JOIN teams t ON mc.team_id = t.team_id
        WHERE t.name LIKE ? AND mc.season = ?
    ''', (f'%{team_name}%', CURRENT_SEASON)).fetchone()
    
    if not team:
        print(f"Team '{team_name}' not found in momentum cache")
        db.close()
        return
    
    # Get rank among all teams
    rank = cursor.execute('''
        SELECT COUNT(*) + 1 as rank
        FROM momentum_cache
        WHERE momentum_score > ? AND season = ?
    ''', (team['momentum_score'], CURRENT_SEASON)).fetchone()['rank']
    
    db.close()
    
    trend_icons = {
        'hot': '🔥 HOT',
        'rising': '📈 RISING',
        'stable': '➡️ STABLE',
        'falling': '📉 FALLING',
        'cold': '🧊 COLD'
    }
    
    print(f"\n{'='*60}")
    print(f"{team['name']} - Momentum Analysis")
    print(f"{'='*60}")
    print(f"  Conference: {team['conference']}")
    print(f"  Momentum Rank: #{rank}")
    print(f"  Momentum Score: {team['momentum_score']:.1f}/100")
    print(f"  Trend: {trend_icons.get(team['trend_direction'], team['trend_direction'])}")
    
    print(f"\n  Last 10 Games:")
    print(f"    Record: {team['wins_l10']}-{team['losses_l10']}")
    if team['win_streak'] > 0:
        print(f"    Current Streak: W{team['win_streak']}")
    elif team['loss_streak'] > 0:
        print(f"    Current Streak: L{team['loss_streak']}")
    print(f"    Avg Margin: {team['avg_margin_l10']:+.1f}" if team['avg_margin_l10'] else "    Avg Margin: N/A")
    print(f"    vs Expected: {team['avg_vs_expected_l10']:+.1f}" if team['avg_vs_expected_l10'] else "    vs Expected: N/A")
    
    print(f"\n  Rating Trajectory:")
    print(f"    Rank Change: {team['rank_change_l10']:+d}" if team['rank_change_l10'] else "    Rank Change: 0")
    print(f"    Start Rank: #{team['rank_start_l10']}" if team['rank_start_l10'] else "    Start Rank: N/A")
    print(f"    Current Rank: #{team['rank_current']}" if team['rank_current'] else "    Current Rank: N/A")
    print(f"    AdjEM Change: {team['adj_em_change_l10']:+.2f}" if team['adj_em_change_l10'] else "    AdjEM Change: N/A")
    
    # Show recent games
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
    parser.add_argument('--team', type=str, help='Show detail for specific team')
    parser.add_argument('--top', type=int, default=20, help='Show top N teams (default: 20)')
    parser.add_argument('--min-games', type=int, default=5, help='Minimum games played (default: 5)')
    parser.add_argument('--hot', action='store_true', help='Show only hot teams')
    parser.add_argument('--cold', action='store_true', help='Show only cold teams')
    parser.add_argument('--calculate', action='store_true', help='Recalculate all momentum scores')
    
    # New filter options
    parser.add_argument('--tournament', action='store_true', help='Only show tournament teams')
    parser.add_argument('--kenpom', type=str, help='KenPom rank range (e.g., 50-150 for mid-majors)')
    parser.add_argument('--seeds', type=str, help='Seed range (e.g., 10-16 for underdogs)')
    parser.add_argument('--conference', type=str, help='Filter by conference (e.g., SEC, B12)')
    
    # Special rankings
    parser.add_argument('--upsets', action='store_true', help='Show upset candidates (bracket busters)')
    parser.add_argument('--vulnerable', action='store_true', help='Show vulnerable favorites')
    
    args = parser.parse_args()
    
    # Parse range arguments
    kenpom_range = None
    if args.kenpom:
        try:
            parts = args.kenpom.split('-')
            kenpom_range = (int(parts[0]), int(parts[1]))
        except:
            print("Invalid --kenpom format. Use: --kenpom 50-150")
            exit(1)
    
    seed_range = None
    if args.seeds:
        try:
            parts = args.seeds.split('-')
            seed_range = (int(parts[0]), int(parts[1]))
        except:
            print("Invalid --seeds format. Use: --seeds 10-16")
            exit(1)
    
    # Recalculate if requested or if showing general rankings
    if args.calculate or (args.team is None and not args.hot and not args.cold 
                          and not args.upsets and not args.vulnerable
                          and not args.tournament and not kenpom_range 
                          and not seed_range and not args.conference):
        update_momentum_cache()
    
    # Show appropriate output
    if args.team:
        show_team_detail(args.team)
    elif args.upsets:
        show_upset_candidates(args.top, min_games=args.min_games)
    elif args.vulnerable:
        show_vulnerable_favorites(args.top, min_games=args.min_games)
    elif args.hot:
        show_top_teams(args.top, trend_filter='hot', min_games=args.min_games,
                      tournament_only=args.tournament, kenpom_range=kenpom_range,
                      seed_range=seed_range, conference=args.conference)
    elif args.cold:
        show_top_teams(args.top, trend_filter='cold', min_games=args.min_games,
                      tournament_only=args.tournament, kenpom_range=kenpom_range,
                      seed_range=seed_range, conference=args.conference)
    else:
        show_top_teams(args.top, min_games=args.min_games,
                      tournament_only=args.tournament, kenpom_range=kenpom_range,
                      seed_range=seed_range, conference=args.conference)