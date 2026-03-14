"""
Daily cron job for KenPom app data updates.

Railway schedule: 0 10 * * *  (6:00am ET = 10:00am UTC)

Run manually:
    python cron.py            # Full run
    python cron.py --dry-run  # Print steps without executing
"""

import os
import sys
import argparse
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# ENVIRONMENT FLAGS
# ============================================================
# BRACKET_FINALIZED — set to "true" in Railway on Selection Sunday
# once the real bracket is revealed. Until then, Bracket Matrix
# projected field is imported daily. Once true, bracket import
# is skipped (the real bracket doesn't change after it's set).
# ============================================================
BRACKET_FINALIZED = os.getenv("BRACKET_FINALIZED", "false").lower() == "true"


# ============================================================
# PIPELINE STEPS
# ============================================================

def run_fetch_data():
    from scrapers.fetch_data import full_sync
    full_sync()

def run_fetch_games():
    from scrapers.fetch_games import fetch_games_range
    fetch_games_range(days_back=3)

def run_import_bracket():
    from scrapers.import_bracket_matrix import generate_bracket
    result = generate_bracket()
    if not result:
        raise RuntimeError("Bracket Matrix returned no data — site may be down or field not yet projected")

def run_fetch_momentum_ratings():
    from scrapers.fetch_momentum_ratings import fetch_yesterday_snapshot
    fetch_yesterday_snapshot()

def run_fetch_game_scores():
    from scrapers.fetch_game_scores_espn import update_scores_from_espn
    update_scores_from_espn()

def run_calculate_momentum():
    from scrapers.calculate_momentum import update_momentum_cache
    count = update_momentum_cache()
    if count == 0:
        raise RuntimeError("Momentum cache returned 0 teams — likely a data dependency failure upstream")

def run_contenders():
    from scrapers.fetch_historical_four_factors import calculate_current_contenders
    results = calculate_current_contenders()
    if not results:
        raise RuntimeError("Contender calculation returned no results")

def run_fetch_shooting_stats():
    # ── Why optional? ─────────────────────────────────────────────────────────
    # ESPN's stats endpoint is unofficial and could change format or go down.
    # A failure here shouldn't tank the whole pipeline — KenPom ratings,
    # momentum scores, and bracket data are all unaffected by shooting stats.
    # The worst case if this fails: shooting section shows stale data from the
    # previous day's run, which is fine.
    # ─────────────────────────────────────────────────────────────────────────
    from scrapers.fetch_espn_shooting_stats import fetch_shooting_stats
    success = fetch_shooting_stats()
    if not success:
        raise RuntimeError("ESPN shooting stats returned 0 teams updated — API may be down or format changed")

def run_generate_narratives():
    # ── Why optional? ─────────────────────────────────────────────────────────
    # Narrative generation calls the Anthropic API for every team (~365 calls).
    # A failure here — API outage, rate limit, billing issue — shouldn't block
    # ratings, momentum, or bracket data from updating. Worst case: narratives
    # show stale text from the previous run, which is acceptable.
    # ─────────────────────────────────────────────────────────────────────────
    from scrapers.generate_narratives import run_generate_narratives as _run
    _run()


# ============================================================
# PIPELINE DEFINITION
# ============================================================

def build_steps():
    steps = [
        ("Fetch KenPom data (ratings, teams, four factors)", run_fetch_data,             False),
        ("Fetch game predictions (Fanmatch, last 3 days)",   run_fetch_games,            False),
    ]

    if not BRACKET_FINALIZED:
        steps.append(
        ("Import projected bracket (Bracket Matrix)",        run_import_bracket,         True))
    else:
        print("ℹ BRACKET_FINALIZED=true — skipping bracket import")

    steps += [
        ("Fetch rating snapshots (momentum trajectory)",     run_fetch_momentum_ratings, False),
        ("Fetch game scores (ESPN)",                         run_fetch_game_scores,      False),
        ("Calculate momentum scores",                        run_calculate_momentum,     False),
        ("Update championship contender scores",             run_contenders,             True),
        ("Fetch ESPN shooting stats (3PT%, FT%)",            run_fetch_shooting_stats,   True),
        # ("Generate team narratives (Anthropic)",             run_generate_narratives,    True),
    ]

    return steps


# ============================================================
# MAIN RUNNER
# ============================================================

def run_pipeline(dry_run=False):
    start_time = datetime.now()
    steps = build_steps()

    print(f"\n{'='*60}")
    print(f"KenPom Daily Update")
    print(f"Started:            {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Bracket finalized:  {BRACKET_FINALIZED}")
    print(f"Steps:              {len(steps)}")
    print(f"{'='*60}\n")

    results = []  # (name, success, is_optional, error_msg)

    for step_name, step_fn, is_optional in steps:
        tag = "[optional]" if is_optional else "[required]"
        print(f"\n▶ {tag} {step_name}")
        print("-" * 55)

        if dry_run:
            print("  [DRY RUN] skipped")
            results.append((step_name, True, is_optional, None))
            continue

        try:
            step_fn()
            results.append((step_name, True, is_optional, None))
            print(f"✓ Done")
        except Exception as e:
            error_msg = traceback.format_exc()
            results.append((step_name, False, is_optional, error_msg))
            status = "⚠ OPTIONAL STEP FAILED" if is_optional else "❌ REQUIRED STEP FAILED"
            print(f"{status}: {e}")
            print(error_msg)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    elapsed = (datetime.now() - start_time).seconds
    minutes, seconds = divmod(elapsed, 60)

    print(f"\n{'='*60}")
    print(f"Pipeline finished — {minutes}m {seconds}s")
    print(f"{'='*60}")

    for name, success, is_optional, _ in results:
        if success:
            icon = "✓"
        elif is_optional:
            icon = "⚠"
        else:
            icon = "❌"
        print(f"  {icon} {name}")

    required_failures = [(name, err) for name, success, is_optional, err
                         in results if not success and not is_optional]
    optional_failures  = [name for name, success, is_optional, _
                          in results if not success and is_optional]

    if required_failures:
        print(f"\n❌ {len(required_failures)} required step(s) failed")
        sys.exit(1)
    elif optional_failures:
        print(f"\n⚠ Optional step(s) failed: {', '.join(optional_failures)}")
    else:
        print(f"\n✅ All steps completed successfully :)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KenPom daily data pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print steps without executing anything")
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run)