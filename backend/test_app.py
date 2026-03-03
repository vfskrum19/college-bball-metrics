"""
test_app.py - Automated tests for the KenPom API

HOW TO RUN:
    pip install pytest
    pytest test_app.py -v

WHAT THIS TESTS:
    - Basic endpoint functionality (do routes return expected data?)
    - Input validation (do bad inputs get rejected properly?)
    - Edge cases (empty results, missing resources)
    - Error handling (do errors return clean JSON, not tracebacks?)

WHY WRITE TESTS?
    Tests are code that checks your code. Instead of manually hitting
    endpoints with curl every time you make a change, you run:
    
        pytest test_app.py
    
    In 2 seconds you know if everything still works. When you add a
    feature next month and accidentally break something else, the
    tests catch it immediately instead of you discovering it in
    production when a user complains.

WHAT'S A FIXTURE?
    Fixtures are pytest's way of sharing setup code between tests.
    The @pytest.fixture decorator marks a function that creates
    something tests need (like a test client). When a test function
    has a parameter with the same name as a fixture, pytest
    automatically calls the fixture and passes the result in.

WHAT'S A TEST CLIENT?
    Flask's test client lets you make fake HTTP requests without
    running a real server. It's fast (no network overhead) and
    isolated (each test gets a fresh client). You call methods like
    client.get('/api/teams') and get back a response object with
    .status_code, .json, etc.
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path so we can import app and validators
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from validators import (
    ValidationError, validate_season, validate_team_id,
    validate_limit, validate_kenpom_rank, validate_trend,
    validate_region, validate_search_query, validate_min_games
)


# ============================================================
# FIXTURES
# ============================================================
# Fixtures run before tests to set things up. The 'client'
# fixture creates a test client that every test can use.
# ============================================================

@pytest.fixture
def app():
    """Create application for testing"""
    # Create app with testing config
    # You could add a TestingConfig class in app.py for test-specific settings
    app = create_app('development')
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client for the app
    
    The test client lets us make requests without running a server.
    Each test gets a fresh client, so tests don't affect each other.
    """
    return app.test_client()


# ============================================================
# BASIC ENDPOINT TESTS
# ============================================================
# These verify that endpoints exist and return expected shapes.
# They're the foundation - if these fail, something is very wrong.
# ============================================================

class TestBasicEndpoints:
    """Test that basic endpoints return expected responses"""
    
    def test_status_endpoint(self, client):
        """GET /api/status should return database status"""
        response = client.get('/api/status')
        
        # Should succeed
        assert response.status_code == 200
        
        # Should be valid JSON
        data = response.get_json()
        assert data is not None
        
        # Should have expected fields
        assert 'status' in data
        assert 'teams_count' in data
        assert 'last_update' in data
        assert data['status'] == 'online'
    
    def test_teams_endpoint(self, client):
        """GET /api/teams should return list of teams"""
        response = client.get('/api/teams')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should be a list
        assert isinstance(data, list)
        
        # If there's data, check the shape
        if len(data) > 0:
            team = data[0]
            assert 'name' in team or 'team_id' in team
    
    def test_conferences_endpoint(self, client):
        """GET /api/conferences should return list of conference names"""
        response = client.get('/api/conferences')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # Should be a list of strings
        assert isinstance(data, list)
        if len(data) > 0:
            assert isinstance(data[0], str)
    
    def test_search_empty_query(self, client):
        """GET /api/search with no query should return empty list"""
        response = client.get('/api/search')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data == []
    
    def test_search_with_query(self, client):
        """GET /api/search?q=duke should return matching teams"""
        response = client.get('/api/search?q=duke')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)


class TestMomentumEndpoints:
    """Test momentum tracker endpoints"""
    
    def test_momentum_rankings(self, client):
        """GET /api/momentum/rankings should return ranked teams"""
        response = client.get('/api/momentum/rankings')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        
        # Check shape if we have data
        if len(data) > 0:
            team = data[0]
            assert 'momentum_rank' in team
            assert 'name' in team
            assert 'momentum_score' in team
    
    def test_momentum_with_filters(self, client):
        """GET /api/momentum/rankings with filters should work"""
        response = client.get('/api/momentum/rankings?trend=hot&limit=10')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) <= 10
    
    def test_momentum_conferences(self, client):
        """GET /api/momentum/conferences should return list"""
        response = client.get('/api/momentum/conferences')
        
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)


# ============================================================
# VALIDATION TESTS
# ============================================================
# These verify that bad input gets rejected with proper errors.
# This is where Layer 2 (input validation) proves its worth.
# ============================================================

class TestInputValidation:
    """Test that invalid input is properly rejected"""
    
    def test_invalid_season_rejected(self, client):
        """Invalid season should return 400"""
        response = client.get('/api/teams?season=notanumber')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert data['field'] == 'season'
    
    def test_season_out_of_range_rejected(self, client):
        """Season outside valid range should return 400"""
        response = client.get('/api/teams?season=1900')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_invalid_trend_rejected(self, client):
        """Invalid trend value should return 400"""
        response = client.get('/api/momentum/rankings?trend=invalid')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert data['field'] == 'trend'
    
    def test_valid_trends_accepted(self, client):
        """Valid trend values should work"""
        for trend in ['hot', 'cold', 'rising', 'falling', 'stable']:
            response = client.get(f'/api/momentum/rankings?trend={trend}')
            assert response.status_code == 200, f"Trend '{trend}' should be valid"
    
    def test_kenpom_rank_out_of_range(self, client):
        """KenPom rank outside 1-363 should return 400"""
        response = client.get('/api/momentum/rankings?kenpom_min=500')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_search_query_too_long(self, client):
        """Search query over 100 chars should return 400"""
        long_query = 'a' * 150
        response = client.get(f'/api/search?q={long_query}')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_limit_is_capped(self, client):
        """Limit should be capped at MAX_RESULTS_LIMIT"""
        response = client.get('/api/momentum/rankings?limit=9999')
        
        # Should succeed (limit gets capped, not rejected)
        assert response.status_code == 200
        data = response.get_json()
        
        # Should have at most MAX_RESULTS_LIMIT (200) results
        assert len(data) <= 200
    
    def test_invalid_region_rejected(self, client):
        """Invalid region name should return 400"""
        response = client.get('/api/bracket/region/InvalidRegion')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_nonexistent_team(self, client):
        """Requesting non-existent team should return 404"""
        response = client.get('/api/team/999999/ratings')
        
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
    
    def test_nonexistent_player(self, client):
        """Requesting non-existent player should return 404"""
        response = client.get('/api/player/999999')
        
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
    
    def test_nonexistent_matchup(self, client):
        """Requesting non-existent matchup should return 404"""
        response = client.get('/api/matchup/999999')
        
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
    
    def test_compare_missing_params(self, client):
        """Compare without both teams should return 400"""
        response = client.get('/api/compare?team1=1')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_limit_zero_or_negative(self, client):
        """Limit of 0 or negative should be handled"""
        # Limit of 0 should either error or return empty
        response = client.get('/api/momentum/rankings?limit=0')
        # We clamp to minimum of 1, so this should work
        assert response.status_code in [200, 400]


# ============================================================
# VALIDATOR UNIT TESTS
# ============================================================
# These test the validator functions directly, not through HTTP.
# Faster and more precise - you can test exact error messages.
# ============================================================

class TestValidatorFunctions:
    """Test validator functions directly"""
    
    def test_validate_season_valid(self):
        """Valid seasons should pass"""
        assert validate_season('2024') == 2024
        assert validate_season('2026') == 2026
        assert validate_season(2025) == 2025
        assert validate_season(None) is None
    
    def test_validate_season_invalid(self):
        """Invalid seasons should raise ValidationError"""
        with pytest.raises(ValidationError) as exc:
            validate_season('notanumber')
        assert exc.value.field == 'season'
        
        with pytest.raises(ValidationError):
            validate_season('1900')  # Too old
        
        with pytest.raises(ValidationError):
            validate_season('2050')  # Too far future
    
    def test_validate_team_id_valid(self):
        """Valid team IDs should pass"""
        assert validate_team_id('123') == 123
        assert validate_team_id(456) == 456
        assert validate_team_id(None) is None
    
    def test_validate_team_id_invalid(self):
        """Invalid team IDs should raise ValidationError"""
        with pytest.raises(ValidationError):
            validate_team_id('notanumber')
        
        with pytest.raises(ValidationError):
            validate_team_id('-5')
        
        with pytest.raises(ValidationError):
            validate_team_id('0')
    
    def test_validate_limit_clamping(self):
        """Limits should be clamped to valid range"""
        assert validate_limit(None, default=50) == 50
        assert validate_limit('10') == 10
        assert validate_limit('500', maximum=200) == 200  # Capped
        assert validate_limit('0') == 1  # Minimum is 1
    
    def test_validate_trend_whitelist(self):
        """Only valid trends should pass"""
        assert validate_trend('hot') == 'hot'
        assert validate_trend('HOT') == 'hot'  # Case insensitive
        assert validate_trend(None) is None
        assert validate_trend('') is None
        
        with pytest.raises(ValidationError):
            validate_trend('invalid')
    
    def test_validate_region_whitelist(self):
        """Only valid regions should pass"""
        assert validate_region('East') == 'East'
        assert validate_region('east') == 'East'  # Normalized
        assert validate_region('WEST') == 'West'
        
        with pytest.raises(ValidationError):
            validate_region('InvalidRegion')
    
    def test_validate_search_query_sanitization(self):
        """Search queries should be sanitized"""
        # Normal queries pass through
        assert validate_search_query('Duke') == 'Duke'
        
        # Wildcards are stripped
        assert validate_search_query('Duke%') == 'Duke'
        assert validate_search_query('%Duke%') == 'Duke'
        assert validate_search_query('Du_ke') == 'Duke'
        
        # Empty/None returns empty string
        assert validate_search_query(None) == ''
        assert validate_search_query('') == ''
        
        # Too long raises error
        with pytest.raises(ValidationError):
            validate_search_query('a' * 150)
    
    def test_validate_kenpom_rank_range(self):
        """KenPom ranks must be 1-363"""
        assert validate_kenpom_rank('1') == 1
        assert validate_kenpom_rank('363') == 363
        assert validate_kenpom_rank(None) is None
        
        with pytest.raises(ValidationError):
            validate_kenpom_rank('0')
        
        with pytest.raises(ValidationError):
            validate_kenpom_rank('400')
    
    def test_validate_min_games_range(self):
        """Min games must be 0-35"""
        assert validate_min_games(None) == 5  # Default
        assert validate_min_games('0') == 0
        assert validate_min_games('35') == 35
        
        with pytest.raises(ValidationError):
            validate_min_games('-1')
        
        with pytest.raises(ValidationError):
            validate_min_games('50')


# ============================================================
# ERROR HANDLING TESTS
# ============================================================
# Verify that errors return clean JSON, not raw tracebacks.
# ============================================================

class TestErrorHandling:
    """Test that errors are handled gracefully"""
    
    def test_404_is_json(self, client):
        """404 errors should return JSON, not HTML"""
        response = client.get('/api/nonexistent/endpoint')
        
        assert response.status_code == 404
        assert response.content_type == 'application/json'
        data = response.get_json()
        assert 'error' in data
    
    def test_400_has_details(self, client):
        """400 errors should include field and message"""
        response = client.get('/api/teams?season=invalid')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'field' in data
        assert 'message' in data


# ============================================================
# RUNNING THE TESTS
# ============================================================
# You can run these with:
#   pytest test_app.py -v          # Verbose output
#   pytest test_app.py -v -x       # Stop on first failure
#   pytest test_app.py::TestInputValidation  # Run one class
#   pytest test_app.py -k "search"  # Run tests matching "search"
# ============================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
