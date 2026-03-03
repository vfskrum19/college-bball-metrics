"""
validators.py - Input validation and sanitization for the KenPom API

WHY A SEPARATE FILE?
    Validation logic is its own concern. Mixing it into route functions
    makes them long and hard to read. By centralizing it here:
    1. Every route validates inputs the same way (consistency)
    2. If you need to change a rule (e.g., max search length), you
       change it in ONE place instead of hunting through routes
    3. It's independently testable - you can write tests for these
       functions without spinning up the whole Flask app

HOW IT WORKS:
    Each validator either returns a cleaned/safe value, or raises
    a ValidationError with a clear message. The route-level decorator
    (@validate_params) catches these errors and returns a clean 400
    response to the user, so your route functions stay focused on
    their actual job: querying data and building responses.
"""

import re


# ============================================================
# CUSTOM EXCEPTION
# ============================================================
# Why a custom exception instead of just returning error dicts?
#
# Exceptions let you "bail out" of validation immediately when
# something is wrong, without needing nested if/else chains.
# The decorator at the bottom catches these and converts them
# to clean 400 JSON responses automatically.
# ============================================================

class ValidationError(Exception):
    """Raised when user input fails validation"""
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


# ============================================================
# WHITELISTS
# ============================================================
# For parameters that can only be one of a known set of values,
# we define the allowed values here. This is called "whitelisting"
# and it's the safest form of validation - instead of trying to
# guess what's dangerous and block it (blacklisting), you define
# exactly what's allowed and reject everything else.
#
# Example: if trend can only be hot/cold/rising/falling/stable,
# there's no reason to accept ANY other string. Someone sending
# trend=<script>alert(1)</script> gets a clean "invalid value"
# error instead of that string reaching your database query.
# ============================================================

VALID_TRENDS = {'hot', 'rising', 'stable', 'falling', 'cold'}

VALID_REGIONS = {'East', 'West', 'South', 'Midwest'}

VALID_SORT_FIELDS = {
    'momentum_score', 'kenpom_rank', 'name',
    'wins', 'losses', 'win_streak'
}


# ============================================================
# INDIVIDUAL VALIDATORS
# ============================================================
# Each function validates one type of input. They all follow
# the same pattern:
#   - Accept the raw value and a field name (for error messages)
#   - Return a clean, safe value if valid
#   - Raise ValidationError if invalid
#
# The field name parameter means error messages are specific:
#   "kenpom_min: must be between 1 and 363"
# instead of generic:
#   "invalid parameter"
# ============================================================

def validate_season(value, field='season'):
    """
    Validate a season year parameter.
    
    Seasons are 4-digit years in a reasonable range. There's no
    college basketball data before ~2002 in KenPom, and anything
    beyond next year is obviously invalid.
    """
    if value is None:
        return None

    try:
        season = int(value)
    except (ValueError, TypeError):
        raise ValidationError(field, 'must be a valid year')

    if season < 2002 or season > 2030:
        raise ValidationError(field, 'must be between 2002 and 2030')

    return season


def validate_team_id(value, field='team_id'):
    """
    Validate a team ID.
    
    Team IDs are positive integers. Flask's <int:team_id> in the
    URL already enforces this for path parameters, but this
    covers query parameters like ?team1=X&team2=Y where Flask
    doesn't enforce the type automatically.
    """
    if value is None:
        return None

    try:
        team_id = int(value)
    except (ValueError, TypeError):
        raise ValidationError(field, 'must be a positive integer')

    if team_id < 1:
        raise ValidationError(field, 'must be a positive integer')

    return team_id


def validate_limit(value, default=50, maximum=200, field='limit'):
    """
    Validate and clamp a limit parameter.
    
    This is the upgraded version of the clamp_limit helper we
    added in Layer 1, now with proper error messaging.
    """
    if value is None:
        return min(default, maximum)

    try:
        limit = int(value)
    except (ValueError, TypeError):
        raise ValidationError(field, 'must be a positive integer')

    if limit < 1:
        raise ValidationError(field, 'must be at least 1')

    # Silently cap at maximum rather than rejecting - this is a
    # design choice. We COULD reject limit=500 with an error, but
    # capping it is more user-friendly. The idea is: "I'll give
    # you as much as I can, up to the limit I allow."
    return min(limit, maximum)


def validate_kenpom_rank(value, field='kenpom_rank'):
    """
    Validate a KenPom rank filter.
    
    There are ~363 D1 teams, so ranks outside 1-363 make no sense.
    This prevents meaningless queries that would return empty results
    anyway, and stops abuse like ?kenpom_min=999999.
    """
    if value is None:
        return None

    try:
        rank = int(value)
    except (ValueError, TypeError):
        raise ValidationError(field, 'must be an integer')

    if rank < 1 or rank > 363:
        raise ValidationError(field, 'must be between 1 and 363')

    return rank


def validate_min_games(value, default=5, field='min_games'):
    """
    Validate minimum games filter.
    
    Teams play ~30 regular season games. A min_games of 0 is
    technically valid (show all teams), but anything over 35
    would filter out everyone, which is probably a mistake.
    """
    if value is None:
        return default

    try:
        min_games = int(value)
    except (ValueError, TypeError):
        raise ValidationError(field, 'must be a positive integer')

    if min_games < 0 or min_games > 35:
        raise ValidationError(field, 'must be between 0 and 35')

    return min_games


def validate_trend(value, field='trend'):
    """
    Validate a trend direction filter.
    
    This is a whitelist check - the value MUST be one of the
    known trend categories, or None (no filter). Anything else
    gets rejected outright.
    """
    if value is None or value == '':
        return None

    cleaned = value.strip().lower()

    if cleaned not in VALID_TRENDS:
        allowed = ', '.join(sorted(VALID_TRENDS))
        raise ValidationError(field, f'must be one of: {allowed}')

    return cleaned


def validate_region(value, field='region'):
    """
    Validate a bracket region name.
    
    Only four valid regions exist. This also prevents path
    traversal attempts through the URL - someone can't pass
    region_name=../../etc/passwd because it's not in the whitelist.
    """
    if value is None:
        return None

    # Regions are title-cased in the database
    cleaned = value.strip().title()

    if cleaned not in VALID_REGIONS:
        allowed = ', '.join(sorted(VALID_REGIONS))
        raise ValidationError(field, f'must be one of: {allowed}')

    return cleaned


def validate_search_query(value, max_length=100, field='q'):
    """
    Validate and sanitize a search query string.
    
    This is the most security-sensitive validator because search
    strings are freeform text that goes into a LIKE query. We:
    
    1. Strip whitespace (basic cleanup)
    2. Enforce a maximum length (prevents someone sending a 
       10,000 character string to make your LIKE query slow)
    3. Remove SQL wildcard characters that the user shouldn't
       be injecting manually (% and _). Your code already adds
       the % wildcards for the LIKE pattern - we don't want
       user-supplied ones changing the pattern behavior.
    
    Note: SQL injection is already prevented by parameterized
    queries. This is defense-in-depth - extra protection even
    though the primary defense is solid.
    """
    if value is None:
        return ''

    cleaned = value.strip()

    if len(cleaned) > max_length:
        raise ValidationError(field, f'must be {max_length} characters or fewer')

    if len(cleaned) < 1:
        return ''

    # Remove SQL LIKE wildcards that could alter query behavior.
    # Your code wraps the search in %...% already - user-supplied
    # % or _ would change what the pattern matches.
    cleaned = cleaned.replace('%', '').replace('_', '')

    return cleaned


def validate_conference(value, field='conference'):
    """
    Validate a conference name filter.
    
    We can't whitelist conferences easily since they could change
    (realignment, etc.), so instead we just enforce reasonable
    length and strip dangerous characters. The database query
    is parameterized, so the main risk is someone sending
    absurdly long strings.
    """
    if value is None or value == '':
        return None

    cleaned = value.strip()

    if len(cleaned) > 50:
        raise ValidationError(field, 'must be 50 characters or fewer')

    return cleaned


def validate_boolean(value, field='boolean'):
    """
    Validate a boolean query parameter.
    
    HTML/URLs don't have a native boolean type, so people send
    strings like 'true', 'false', '1', '0', 'yes', 'no'. This
    normalizes all of those to Python True/False.
    """
    if value is None:
        return False

    return value.strip().lower() in ('true', '1', 'yes')


# ============================================================
# DECORATOR: VALIDATE_PARAMS
# ============================================================
# This isn't a validator itself - it's a safety net. You wrap
# a route function with @validate_params and it catches any
# ValidationError raised by the validators above, converting
# it to a clean 400 JSON response.
#
# Without this, you'd need try/except in every single route.
# With it, your routes just call validators normally and any
# failure automatically becomes a proper error response.
#
# Usage:
#   @app.route('/api/something')
#   @validate_params
#   def my_route():
#       limit = validate_limit(request.args.get('limit'))
#       ...
# ============================================================

from functools import wraps
from flask import jsonify


def validate_params(f):
    """Decorator that catches ValidationError and returns 400 JSON"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            return jsonify({
                'error': 'Validation error',
                'field': e.field,
                'message': e.message
            }), 400
    return decorated
