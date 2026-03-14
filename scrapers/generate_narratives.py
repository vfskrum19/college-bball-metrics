"""
generate_narratives.py

Generates a 2-3 sentence scouting narrative for each team using the
Anthropic API. Runs as optional Step 9 in cron.py.

Design philosophy:
- Pre-compute ALL interpretive labels in Python before touching the model.
  The model's only job is natural language. It never interprets raw numbers.
- Every stat passed to the prompt includes its national context (rank or label).
- Narratives are stored in teams.narrative and served statically — never
  generated on demand.
- Graceful degradation: if a team is missing shooting stats or player data,
  the prompt builds from whatever is available.
"""

import anthropic
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db import get_db, commit, get_cursor

# ---------------------------------------------------------------------------
# Context translation — this is the most important part of the whole file.
# Every number gets a human-readable label before going to the model.
# National averages based on 2025-26 D1 season.
# ---------------------------------------------------------------------------

def tempo_label(rank):
    """KenPom adjusted tempo rank → plain English"""
    if rank is None:
        return None
    if rank <= 25:   return "one of the fastest-paced teams in the country"
    if rank <= 75:   return "an up-tempo offense"
    if rank <= 175:  return "an average-tempo offense"
    if rank <= 275:  return "a slower, more deliberate offense"
    return "one of the most half-court-oriented teams in the country"

def offense_label(rank):
    """Adjusted offensive efficiency rank → plain English"""
    if rank is None:
        return None
    if rank <= 10:   return "a historically elite offense"
    if rank <= 30:   return "an elite offense"
    if rank <= 75:   return "a top-tier offense"
    if rank <= 150:  return "an above-average offense"
    if rank <= 250:  return "a below-average offense"
    return "a struggling offense"

def defense_label(rank):
    """Adjusted defensive efficiency rank → plain English"""
    if rank is None:
        return None
    if rank <= 10:   return "a historically elite defense"
    if rank <= 30:   return "an elite defense"
    if rank <= 75:   return "a top-tier defense"
    if rank <= 150:  return "a solid defense"
    if rank <= 250:  return "a below-average defense"
    return "a liability defensively"

def three_rate_label(fg3_rate):
    """3PA/FGA → shot profile description"""
    if fg3_rate is None:
        return None
    if fg3_rate >= 0.48:  return "heavily three-point reliant"
    if fg3_rate >= 0.40:  return "three-point oriented"
    if fg3_rate >= 0.32:  return "balanced between threes and twos"
    if fg3_rate >= 0.24:  return "interior-focused"
    return "one of the most paint-dominant offenses in the country"

def ft_rate_label(ft_rate):
    """FTA/FGA → aggression at the rim"""
    if ft_rate is None:
        return None
    if ft_rate >= 0.45:  return "extremely aggressive attacking the rim"
    if ft_rate >= 0.35:  return "active at getting to the free throw line"
    if ft_rate >= 0.25:  return "average in drawing fouls"
    return "reluctant to attack the basket"

def shooting_label(pct, stat_type):
    """3PT% or FT% → quality label"""
    if pct is None:
        return None
    if stat_type == "three":
        if pct >= 39:    return "elite three-point shooting"
        if pct >= 36:    return "above-average three-point shooting"
        if pct >= 33:    return "average three-point shooting"
        return "below-average three-point shooting"
    if stat_type == "ft":
        if pct >= 78:    return "reliable free throw shooting"
        if pct >= 70:    return "average free throw shooting"
        return "poor free throw shooting"

def sos_label(rank):
    """Strength of schedule rank → context"""
    if rank is None:
        return None
    if rank <= 25:   return "one of the toughest schedules in the country"
    if rank <= 75:   return "a difficult schedule"
    if rank <= 200:  return "an average schedule"
    return "a soft schedule"

def momentum_label(team):
    """Build a momentum sentence from recent game data."""
    trend = team.get('trend_direction')
    wins = team.get('wins_l10')
    losses = team.get('losses_l10')
    win_streak = team.get('win_streak', 0) or 0
    loss_streak = team.get('loss_streak', 0) or 0
    rank_change = team.get('rank_change_l10', 0) or 0

    if wins is None:
        return None

    record = f"{wins}-{losses} in their last {wins + losses} games"

    if win_streak >= 6:
        return f"riding a {win_streak}-game win streak ({record}), rising {abs(rank_change)} spots in the rankings"
    if win_streak >= 4:
        return f"on a {win_streak}-game win streak ({record})"
    if win_streak >= 2:
        return f"winners of {win_streak} straight ({record})"
    if loss_streak >= 4:
        return f"struggling down the stretch, having lost {loss_streak} of their last {loss_streak + min(wins,2)} games"
    if loss_streak >= 2:
        return f"dropped {loss_streak} of their last {loss_streak + min(wins,3)} entering March"
    # Only use rank change framing if record doesn't tell a better story
    win_pct = wins / (wins + losses) if (wins + losses) > 0 else 0
    if rank_change >= 15 and win_pct >= 0.6:
        return f"one of the hottest teams in the country over the last month ({record}, up {rank_change} in the rankings)"
    if rank_change <= -15 and win_pct < 0.5:
        return f"trending in the wrong direction ({record}, down {abs(rank_change)} spots recently)"
    return f"{record} heading into the tournament"

def bpm_label(bpm):
    """Box Plus/Minus → impact label"""
    if bpm is None:
        return None
    if bpm >= 12:   return "an All-American caliber impact"
    if bpm >= 8:    return "a high-major star-level impact"
    if bpm >= 5:    return "a quality starter impact"
    if bpm >= 2:    return "a solid contributor impact"
    return "a rotation-level impact"

def usage_label(usage_pct):
    """Usage % → role on offense"""
    if usage_pct is None:
        return None
    if usage_pct >= 30:  return "primary ball handler and first option"
    if usage_pct >= 25:  return "featured offensive option"
    if usage_pct >= 20:  return "secondary scorer"
    return "role player"

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def get_team_data(db, team_id):
    """Fetch all team-level data needed for narrative generation."""
    cur = get_cursor(db)

    cur.execute("""
        SELECT
            t.name, t.conference,
            r.adj_em, r.adj_oe, r.adj_de, r.adj_tempo,
            r.rank_adj_oe, r.rank_adj_de, r.rank_adj_tempo,
            r.rank_adj_em AS kenpom_rank,
            rm.net_rank, rm.quad1_wins, rm.quad1_losses,
            rm.quad2_wins, rm.quad2_losses,
            rm.quad3_wins, rm.quad3_losses,
            rm.sor_rank,
            t.fg3_rate, t.ft_rate, t.fg3_pct, t.ft_pct,
            mc.wins_l10, mc.losses_l10, mc.win_streak,
            mc.loss_streak, mc.trend_direction,
            mc.avg_vs_expected_l10, mc.rank_change_l10,
            mc.games_data
        FROM teams t
        LEFT JOIN ratings r ON t.team_id = r.team_id
        LEFT JOIN resume_metrics rm ON t.team_id = rm.team_id
        LEFT JOIN momentum_cache mc ON t.team_id = mc.team_id
        WHERE t.team_id = %s
    """, (team_id,))

    row = cur.fetchone()
    if not row:
        return None

    team = dict(row)

    # Cast numeric fields — RealDictCursor can return these as strings
    int_fields = [
        'kenpom_rank', 'net_rank', 'rank_adj_oe', 'rank_adj_de', 'rank_adj_tempo',
        'quad1_wins', 'quad1_losses', 'quad2_wins', 'quad2_losses',
        'quad3_wins', 'quad3_losses', 'sor_rank',
        'wins_l10', 'losses_l10', 'win_streak', 'loss_streak', 'rank_change_l10',
    ]
    float_fields = [
        'adj_em', 'adj_oe', 'adj_de', 'adj_tempo',
        'fg3_rate', 'ft_rate', 'fg3_pct', 'ft_pct',
        'avg_vs_expected_l10',
    ]
    for f in int_fields:
        if team.get(f) is not None:
            try: team[f] = int(team[f])
            except (ValueError, TypeError): team[f] = None
    for f in float_fields:
        if team.get(f) is not None:
            try: team[f] = float(team[f])
            except (ValueError, TypeError): team[f] = None

    # Enrich recent games with opponent NET ranks
    team['notable_wins'] = []
    team['recent_loss'] = None

    if team.get('games_data'):
        import json
        try:
            games = json.loads(team['games_data']) if isinstance(team['games_data'], str) else team['games_data']
        except (json.JSONDecodeError, TypeError):
            games = []

        # Look up NET ranks for all opponents in one query
        opponent_names = [g['opponent'] for g in games]
        if opponent_names:
            placeholders = ','.join(['%s'] * len(opponent_names))
            cur.execute(f"""
                SELECT t2.name, rm2.net_rank
                FROM teams t2
                LEFT JOIN resume_metrics rm2 ON t2.team_id = rm2.team_id
                WHERE t2.name = ANY(%s)
            """, (opponent_names,))
            net_lookup = {row['name']: row['net_rank'] for row in cur.fetchall()}

            # Tag each game with opponent NET rank
            for g in games:
                g['opp_net'] = net_lookup.get(g['opponent'])

            # Best win = lowest NET rank opponent they beat
            wins = [g for g in games if g['won'] and g.get('opp_net')]
            if wins:
                best_win = min(wins, key=lambda g: g['opp_net'])
                if best_win['opp_net'] <= 50:  # Only mention if opponent was top 50
                    team['notable_wins'] = [best_win]

            # Most recent loss
            losses = [g for g in games if not g['won']]
            if losses:
                team['recent_loss'] = losses[0]  # Already sorted most recent first

    return team

def get_player_data(db, team_id):
    """Fetch top players with stats and roles."""
    cur = get_cursor(db)

    cur.execute("""
        SELECT
            p.name, p.position, p.year,
            ps.ppg, ps.rpg, ps.apg,
            ps.efg_pct, ps.three_pct, ps.ft_pct,
            ps.usage_pct, ps.bpm, ps.per,
            ps.blk_pct, ps.stl_pct, ps.ast_pct,
            tr.role, tr.role_reason, tr.display_order
        FROM players p
        JOIN player_stats ps ON p.player_id = ps.player_id
        LEFT JOIN team_roles tr ON p.player_id = tr.player_id
            AND p.team_id = tr.team_id
        WHERE p.team_id = %s
        ORDER BY tr.display_order ASC NULLS LAST, ps.ppg DESC
        LIMIT 4
    """, (team_id,))

    players = [dict(row) for row in cur.fetchall()]

    float_fields = ['ppg','rpg','apg','efg_pct','three_pct','ft_pct',
                    'usage_pct','bpm','per','blk_pct','stl_pct','ast_pct']
    for p in players:
        for f in float_fields:
            if p.get(f) is not None:
                try: p[f] = float(p[f])
                except (ValueError, TypeError): p[f] = None
    return players

# ---------------------------------------------------------------------------
# Context builder — translates raw numbers into labeled facts for the prompt
# ---------------------------------------------------------------------------

def build_team_context(team, players):
    """
    Build a structured context block from team + player data.
    All numbers are accompanied by their interpretation.
    Returns a string ready to embed in the prompt.
    """
    lines = []

    # Team identity
    lines.append(f"Team: {team['name']} ({team['conference']})")
    lines.append(f"KenPom rank: #{team['kenpom_rank']}" if team.get('kenpom_rank') else "")
    lines.append(f"NET rank: #{team['net_rank']}" if team.get('net_rank') else "")

    # Offensive / defensive identity
    if team.get('rank_adj_oe'):
        lines.append(f"Offense: {offense_label(team['rank_adj_oe'])} (#{team['rank_adj_oe']} nationally, {team['adj_oe']:.1f} points per 100 possessions)")
    if team.get('rank_adj_de'):
        lines.append(f"Defense: {defense_label(team['rank_adj_de'])} (#{team['rank_adj_de']} nationally, {team['adj_de']:.1f} points allowed per 100 possessions)")

    # Pace
    if team.get('rank_adj_tempo'):
        lines.append(f"Pace: {tempo_label(team['rank_adj_tempo'])} (#{team['rank_adj_tempo']} in tempo)")

    # Shot profile
    if team.get('fg3_rate'):
        lines.append(f"Shot profile: {three_rate_label(team['fg3_rate'])} ({team['fg3_rate']*100:.1f}% of shots are threes)")
    if team.get('ft_rate'):
        lines.append(f"Rim aggression: {ft_rate_label(team['ft_rate'])} (FT rate: {team['ft_rate']*100:.1f}%)")
    if team.get('fg3_pct'):
        lines.append(f"Three-point shooting: {shooting_label(team['fg3_pct'], 'three')} ({team['fg3_pct']:.1f}%)")

    # Resume
    q1 = f"{team.get('quad1_wins', 0)}-{team.get('quad1_losses', 0)}" if team.get('quad1_wins') is not None else None
    q2 = f"{team.get('quad2_wins', 0)}-{team.get('quad2_losses', 0)}" if team.get('quad2_wins') is not None else None
    q3 = f"{team.get('quad3_wins', 0)}-{team.get('quad3_losses', 0)}" if team.get('quad3_wins') is not None else None
    if q1:
        lines.append(f"Resume: {q1} in Quad 1 games, {q2} in Quad 2 games, {q3} in Quad 3/4 games")
    if team.get('sor_rank'):
        lines.append(f"Strength of record: #{team['sor_rank']} nationally")

    # Momentum / recent form
    m = momentum_label(team)
    if m:
        # Append best recent win if available
        notable = team.get('notable_wins', [])
        loss = team.get('recent_loss')
        if notable:
            w = notable[0]
            net_str = f" (#{w['opp_net']} NET)" if w.get('opp_net') else ""
            lines.append(f"Recent form: {m}, including a win over {w['opponent']}{net_str}")
        else:
            lines.append(f"Recent form: {m}")
        if loss:
            net_str = f" (#{loss['opp_net']} NET)" if loss.get('opp_net') else ""
            lines.append(f"Most recent loss: to {loss['opponent']}{net_str}, {loss['score']}")

    # Players
    if players:
        lines.append("\nKey players:")
        for p in players:
            role = p.get('role', 'contributor')
            role_tag = f"[{role.upper()}]" if role else "[CONTRIBUTOR]"
            position = p.get('position', '')
            is_big = position in ('C', 'F')

            # Basic stats
            stat_parts = []
            if p.get('ppg'):     stat_parts.append(f"{p['ppg']:.1f} PPG")
            if p.get('rpg'):     stat_parts.append(f"{p['rpg']:.1f} RPG")
            if p.get('apg'):     stat_parts.append(f"{p['apg']:.1f} APG")

            # Only mention 3PT if they're actually a meaningful three-point shooter
            # Gate: must attempt at least ~2 per game (approx fg3_att/games > 1.8)
            # We don't have fg3_att per game directly, so use fg3_rate as proxy:
            # if three_pct exists and is above 30% and they're a guard/wing, include it
            if p.get('three_pct') and not is_big and p['three_pct'] > 0.30:
                stat_parts.append(f"{p['three_pct']*100:.1f}% from three")
            elif p.get('three_pct') and is_big and p['three_pct'] > 0.36:
                # Only mention for bigs if they're genuinely stretch threats
                stat_parts.append(f"{p['three_pct']*100:.1f}% from three (stretch big)")

            if p.get('efg_pct'):
                stat_parts.append(f"{p['efg_pct']*100:.1f}% eFG")

            # Impact — position-aware framing
            impact_parts = []
            if p.get('bpm') is not None:
                impact_parts.append(f"BPM {p['bpm']:+.1f} ({bpm_label(p['bpm'])})")
            if p.get('usage_pct'):
                impact_parts.append(f"{p['usage_pct']:.1f}% usage ({usage_label(p['usage_pct'])})")

            # Defensive tags — framed by position
            if p.get('blk_pct') and p['blk_pct'] >= 4.0:
                if is_big:
                    impact_parts.append(f"elite rim protector ({p['blk_pct']:.1f}% blk rate)")
                else:
                    impact_parts.append(f"shot-altering wing ({p['blk_pct']:.1f}% blk rate)")
            if p.get('stl_pct') and p['stl_pct'] >= 2.5:
                if is_big:
                    impact_parts.append(f"active in passing lanes ({p['stl_pct']:.1f}% stl rate)")
                else:
                    impact_parts.append(f"disruptive perimeter defender ({p['stl_pct']:.1f}% stl rate)")

            player_line = f"  {p['name']} ({position}, {p.get('year','')}) {role_tag}"
            if stat_parts:
                player_line += f" — {', '.join(stat_parts)}"
            if impact_parts:
                player_line += f" — {', '.join(impact_parts)}"

            lines.append(player_line)

    return "\n".join(line for line in lines if line)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You write concise, accurate scouting narratives for college basketball teams heading into March Madness.

Rules:
- Exactly 2-3 sentences. No more.
- Always mention at least one player by name with a specific stat.
- Ground every claim in the data provided. Do not invent facts or use vague praise.
- Use plain basketball language. Avoid jargon unless it clearly fits.
- Tempo descriptions must match the rank provided (low tempo rank = slow team, high tempo rank = fast team).
- Do NOT start with the team name as the first word.
- Do NOT start the narrative with a player name.
- Vary your sentence openings — do not start with "With", "Led by", or "[Team]'s".
- If recent form data is provided, weave it into the narrative naturally — don't just append it.
- Defensive tags are position-specific: a center with a high block rate is a rim protector, not a perimeter defender.
- Tone: confident, analytical, like a quality ESPN bracketologist — not a hype piece, not dry stats recitation.
- Do not draw strategic conclusions from single data points (e.g. one win does not prove a team "rises to the occasion").
- Do not editorialize beyond what the data supports — no unsupported predictions about tournament outcomes.
- Avoid overused phrases: "juggernaut", "potent", "dangerous", "proven their mettle", "rise to the occasion", "phenom", "versatile", "epitomizes".
- No bullet points, no headers. Pure prose."""

def build_prompt(context_block):
    return f"""Here is the structured data for this team:

{context_block}

Write a 2-3 sentence scouting narrative for this team based strictly on the data above."""

# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_narrative(context_block, api_key, retries=3):
    """Call the Anthropic API and return the narrative string.
    Creates a fresh client each call — avoids stale SSL connections.
    Retries up to 3 times with backoff on transient failures.
    """
    import os
    for attempt in range(retries):
        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_prompt(context_block)}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            if attempt < retries - 1:
                wait = 5 * (attempt + 1)
                print(f"    Attempt {attempt+1} failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------

def ensure_narrative_column(db):
    """Add narrative column to teams table if it doesn't exist."""
    cur = get_cursor(db)
    cur.execute("""
        ALTER TABLE teams ADD COLUMN IF NOT EXISTS narrative TEXT
    """)
    cur.execute("""
        ALTER TABLE teams ADD COLUMN IF NOT EXISTS narrative_updated_at TEXT
    """)
    commit(db)

def save_narrative(db, team_id, narrative):
    cur = get_cursor(db)
    cur.execute("""
        UPDATE teams
        SET narrative = %s,
            narrative_updated_at = NOW()::TEXT
        WHERE team_id = %s
    """, (narrative, team_id))
    commit(db)

# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_generate_narratives(team_ids=None, dry_run=False):
    """
    Generate narratives for all teams (or a subset if team_ids provided).
    Uses a thread pool for parallel API calls — ~5x faster than sequential.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

    # Fetch team list with a short-lived connection
    db = get_db()
    if not dry_run:
        ensure_narrative_column(db)
    cur = get_cursor(db)
    if team_ids:
        placeholders = ",".join(["%s"] * len(team_ids))
        cur.execute(f"SELECT team_id, name FROM teams WHERE team_id IN ({placeholders})", team_ids)
    else:
        cur.execute("""
            SELECT team_id, name FROM teams
            WHERE narrative IS NULL OR narrative = ''
            ORDER BY name
        """)
    teams = cur.fetchall()
    db.close()

    total = len(teams)
    success, skipped, failed = 0, 0, 0
    print(f"  {total} teams need narratives")

    def process_team(row):
        team_id = row['team_id']
        team_name = row['name']
        db = get_db()
        try:
            team = get_team_data(db, team_id)
            if not team:
                return ('skip', team_name, None, None)

            players = get_player_data(db, team_id)
            context = build_team_context(team, players)
            narrative = generate_narrative(context, api_key)

            if not dry_run:
                save_narrative(db, team_id, narrative)

            return ('ok', team_name, context, narrative)

        except Exception as e:
            return ('fail', team_name, None, str(e))
        finally:
            db.close()

    # dry_run processes one at a time for clean output
    # full run uses 5 workers for parallel API calls
    max_workers = 1 if dry_run else 3

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, row in enumerate(teams):
            futures[executor.submit(process_team, row)] = i
            if not dry_run:
                time.sleep(0.5)

        completed = 0
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            status, team_name = result[0], result[1]

            if status == 'skip':
                print(f"  [{completed}/{total}] SKIP {team_name} — no team data")
                skipped += 1
            elif status == 'ok':
                context, narrative = result[2], result[3]
                if dry_run:
                    print(f"\n{'='*60}")
                    print(f"TEAM: {team_name}")
                    print(f"{'='*60}")
                    print("CONTEXT SENT TO MODEL:")
                    print(context)
                    print("\nGENERATED NARRATIVE:")
                    print(narrative)
                else:
                    print(f"  [{completed}/{total}] OK  {team_name}")
                success += 1
            elif status == 'fail':
                print(f"  [{completed}/{total}] FAIL {team_name}: {result[3]}")
                failed += 1

    print(f"\nDone — {success} generated, {skipped} skipped, {failed} failed")
    if failed > 0:
        raise RuntimeError(f"{failed} narratives failed to generate")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print context + narrative without writing to DB")
    parser.add_argument("--team", type=str,
                        help="Test a single team by name (implies --dry-run)")
    args = parser.parse_args()

    if args.team:
        db = get_db()
        cur = get_cursor(db)
        cur.execute("SELECT team_id, name FROM teams WHERE name ILIKE %s LIMIT 1", (args.team,))
        exact = cur.fetchone()
        if exact:
            db.close()
            run_generate_narratives(team_ids=[exact['team_id']], dry_run=True)
        else:
            cur.execute("SELECT team_id, name FROM teams WHERE name ILIKE %s LIMIT 5", (f"%{args.team}%",))
            rows = cur.fetchall()
            db.close()
            if not rows:
                print(f"Team not found: {args.team}")
                sys.exit(1)
            if len(rows) > 1:
                print(f"Multiple matches for '{args.team}' — be more specific:")
                for row in rows:
                    print(f"  {row['name']}")
                sys.exit(1)
            run_generate_narratives(team_ids=[rows[0]['team_id']], dry_run=True)
    else:
        run_generate_narratives(dry_run=args.dry_run)