import { useState, useEffect } from 'react';
import './MomentumTracker.css';

const API_BASE = 'http://localhost:5000';

// Trend icons
const TREND_ICONS = {
  hot: '🔥',
  rising: '📈',
  stable: '➡️',
  falling: '📉',
  cold: '🧊'
};

const TREND_COLORS = {
  hot: '#ff6b6b',
  rising: '#4ade80',
  stable: '#888888',
  falling: '#fbbf24',
  cold: '#60a5fa'
};

function MomentumTracker() {
  const [activeTab, setActiveTab] = useState('rankings');
  const [rankings, setRankings] = useState([]);
  const [upsetCandidates, setUpsetCandidates] = useState([]);
  const [vulnerableFavorites, setVulnerableFavorites] = useState([]);
  const [conferences, setConferences] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTeam, setSelectedTeam] = useState(null);
  
  // Filters
  const [filters, setFilters] = useState({
    trend: '',
    tournament: false,
    kenpomMin: '',
    kenpomMax: '',
    conference: '',
    limit: 50
  });

  // Fetch conferences on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/momentum/conferences`)
      .then(res => res.json())
      .then(data => setConferences(data))
      .catch(err => console.error('Error fetching conferences:', err));
  }, []);

  // Fetch data based on active tab
  useEffect(() => {
    setLoading(true);
    setError(null);
    
    let url;
    if (activeTab === 'rankings') {
      const params = new URLSearchParams();
      params.append('limit', filters.limit);
      params.append('min_games', 5);
      if (filters.trend) params.append('trend', filters.trend);
      if (filters.tournament) params.append('tournament', 'true');
      if (filters.kenpomMin) params.append('kenpom_min', filters.kenpomMin);
      if (filters.kenpomMax) params.append('kenpom_max', filters.kenpomMax);
      if (filters.conference) params.append('conference', filters.conference);
      url = `${API_BASE}/api/momentum/rankings?${params}`;
    } else if (activeTab === 'upsets') {
      url = `${API_BASE}/api/momentum/upsets?limit=12`;
    } else if (activeTab === 'vulnerable') {
      url = `${API_BASE}/api/momentum/vulnerable?limit=15`;
    }
    
    fetch(url)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch data');
        return res.json();
      })
      .then(data => {
        if (activeTab === 'rankings') setRankings(data);
        else if (activeTab === 'upsets') setUpsetCandidates(data);
        else if (activeTab === 'vulnerable') setVulnerableFavorites(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [activeTab, filters]);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleTeamClick = (team) => {
    setSelectedTeam(team);
  };

  const closeTeamCard = () => {
    setSelectedTeam(null);
  };

  return (
    <div className="momentum-tracker">
      <header className="momentum-header">
        <h1>🏀 Momentum Tracker</h1>
        <p className="subtitle">Track who's hot, who's cold, and find your bracket busters</p>
      </header>

      {/* Tabs */}
      <div className="momentum-tabs">
        <button 
          className={`tab ${activeTab === 'rankings' ? 'active' : ''}`}
          onClick={() => setActiveTab('rankings')}
        >
          📊 Rankings
        </button>
        <button 
          className={`tab ${activeTab === 'upsets' ? 'active' : ''}`}
          onClick={() => setActiveTab('upsets')}
        >
          🎯 Upset Candidates
        </button>
        <button 
          className={`tab ${activeTab === 'vulnerable' ? 'active' : ''}`}
          onClick={() => setActiveTab('vulnerable')}
        >
          ⚠️ Vulnerable Favorites
        </button>
      </div>

      {/* Filters (only for rankings tab) */}
      {activeTab === 'rankings' && (
        <div className="momentum-filters">
          <div className="filter-group">
            <label>Trend</label>
            <select 
              value={filters.trend} 
              onChange={(e) => handleFilterChange('trend', e.target.value)}
            >
              <option value="">All</option>
              <option value="hot">🔥 Hot</option>
              <option value="rising">📈 Rising</option>
              <option value="stable">➡️ Stable</option>
              <option value="falling">📉 Falling</option>
              <option value="cold">🧊 Cold</option>
            </select>
          </div>
          
          <div className="filter-group">
            <label>Conference</label>
            <select 
              value={filters.conference} 
              onChange={(e) => handleFilterChange('conference', e.target.value)}
            >
              <option value="">All Conferences</option>
              {conferences.map(conf => (
                <option key={conf} value={conf}>{conf}</option>
              ))}
            </select>
          </div>
          
          <div className="filter-group">
            <label>KenPom Range</label>
            <div className="range-inputs">
              <input 
                type="number" 
                placeholder="Min" 
                value={filters.kenpomMin}
                onChange={(e) => handleFilterChange('kenpomMin', e.target.value)}
              />
              <span>-</span>
              <input 
                type="number" 
                placeholder="Max" 
                value={filters.kenpomMax}
                onChange={(e) => handleFilterChange('kenpomMax', e.target.value)}
              />
            </div>
          </div>
          
          <div className="filter-group checkbox">
            <label>
              <input 
                type="checkbox" 
                checked={filters.tournament}
                onChange={(e) => handleFilterChange('tournament', e.target.checked)}
              />
              Tournament Teams Only
            </label>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="momentum-content">
        {loading && <div className="loading">Loading momentum data...</div>}
        {error && <div className="error">Error: {error}</div>}
        
        {!loading && !error && activeTab === 'rankings' && (
          <RankingsTable rankings={rankings} onTeamClick={handleTeamClick} />
        )}
        
        {!loading && !error && activeTab === 'upsets' && (
          <UpsetCandidatesTable candidates={upsetCandidates} onTeamClick={handleTeamClick} />
        )}
        
        {!loading && !error && activeTab === 'vulnerable' && (
          <VulnerableFavoritesTable teams={vulnerableFavorites} onTeamClick={handleTeamClick} />
        )}
      </div>

      {/* Team Card Modal */}
      {selectedTeam && (
        <TeamCardModal team={selectedTeam} onClose={closeTeamCard} />
      )}
    </div>
  );
}

// Simple TeamLogo component - just uses logo_url from API
function TeamLogo({ logoUrl, teamName, size = 32 }) {
  const [imgError, setImgError] = useState(false);
  
  if (imgError || !logoUrl) {
    // Fallback to first letter
    return (
      <div 
        className="team-logo-fallback"
        style={{ 
          width: size, 
          height: size, 
          minWidth: size,
          borderRadius: '50%',
          background: '#3a3a4a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: size * 0.45,
          fontWeight: 'bold',
          color: '#a0a0a0'
        }}
      >
        {teamName?.charAt(0) || '?'}
      </div>
    );
  }
  
  return (
    <img 
      src={logoUrl}
      alt={`${teamName} logo`}
      className="team-logo"
      style={{ width: size, height: size, minWidth: size, objectFit: 'contain' }}
      onError={() => setImgError(true)}
    />
  );
}

function RankingsTable({ rankings, onTeamClick }) {
  if (!rankings.length) {
    return <div className="no-data">No teams match the current filters</div>;
  }

  return (
    <div className="table-container">
      <table className="momentum-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th>KP#</th>
            <th>Record</th>
            <th>Streak</th>
            <th>vs Exp</th>
            <th>Rk Chg</th>
            <th>Score</th>
            <th>Trend</th>
          </tr>
        </thead>
        <tbody>
          {rankings.map((team, idx) => (
            <tr key={team.team_id} onClick={() => onTeamClick(team)} className="clickable-row">
              <td className="rank">{idx + 1}</td>
              <td className="team-name">
                <div className="team-name-inner">
                  <TeamLogo logoUrl={team.logo_url} teamName={team.name} size={28} />
                  <div className="team-name-text">
                    <span className="name">{team.name}</span>
                    <span className="conference">{team.conference}</span>
                  </div>
                  {team.seed && <span className="seed">({team.seed})</span>}
                </div>
              </td>
              <td className="kenpom">#{team.kenpom_rank}</td>
              <td className="record">{team.wins}-{team.losses}</td>
              <td className="streak">
                {team.win_streak > 0 && <span className="win-streak">W{team.win_streak}</span>}
                {team.loss_streak > 0 && <span className="loss-streak">L{team.loss_streak}</span>}
                {!team.win_streak && !team.loss_streak && '-'}
              </td>
              <td className={`vs-exp ${team.avg_vs_expected >= 0 ? 'positive' : 'negative'}`}>
                {team.avg_vs_expected !== null ? (team.avg_vs_expected >= 0 ? '+' : '') + team.avg_vs_expected.toFixed(1) : 'N/A'}
              </td>
              <td className={`rank-change ${team.rank_change > 0 ? 'positive' : team.rank_change < 0 ? 'negative' : ''}`}>
                {team.rank_change > 0 ? '+' : ''}{team.rank_change || 0}
              </td>
              <td className="score">{team.momentum_score.toFixed(1)}</td>
              <td className="trend" style={{ color: TREND_COLORS[team.trend] }}>
                {TREND_ICONS[team.trend]}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UpsetCandidatesTable({ candidates, onTeamClick }) {
  if (!candidates.length) {
    return <div className="no-data">No upset candidates found</div>;
  }

  return (
    <div className="upset-section">
      <div className="section-intro">
        <h2>🎯 First Round Upset Candidates</h2>
        <p>Seeds 10-15 with high momentum facing potentially vulnerable opponents</p>
      </div>
      
      <div className="table-container">
        <table className="momentum-table upsets-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Underdog</th>
              <th>Matchup</th>
              <th>vs</th>
              <th>Opponent</th>
              <th>Momentum</th>
              <th>vs Exp</th>
              <th>Mom Diff</th>
              <th>Upset Score</th>
              <th>Alerts</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((team, idx) => (
              <tr key={team.team_id} onClick={() => onTeamClick(team)} className="clickable-row">
                <td className="rank">{idx + 1}</td>
                <td className="team-name">
                  <div className="team-name-inner">
                    <TeamLogo logoUrl={team.logo_url} teamName={team.name} size={28} />
                    <div className="team-name-text">
                      <span className="name">{team.name}</span>
                      <span className="region">{team.region}</span>
                    </div>
                  </div>
                </td>
                <td className="matchup">({team.seed}) vs ({team.opponent.seed})</td>
                <td className="vs-arrow">→</td>
                <td className="opponent-cell">
                  <div className="opponent-inner">
                    <TeamLogo logoUrl={team.opponent.logo_url} teamName={team.opponent.name} size={24} />
                    <span className="opponent-name">{team.opponent.name}</span>
                  </div>
                </td>
                <td className="momentum-comparison">
                  <span className="team-mom">{team.momentum_score.toFixed(0)}</span>
                  <span className="vs">vs</span>
                  <span className="opp-mom">{team.opponent.momentum_score.toFixed(0)}</span>
                </td>
                <td className={`vs-exp ${team.avg_vs_expected >= 0 ? 'positive' : 'negative'}`}>
                  {team.avg_vs_expected !== null ? (team.avg_vs_expected >= 0 ? '+' : '') + team.avg_vs_expected.toFixed(1) : 'N/A'}
                </td>
                <td className={`mom-diff ${team.momentum_diff >= 0 ? 'positive' : 'negative'}`}>
                  {team.momentum_diff >= 0 ? '+' : ''}{team.momentum_diff.toFixed(1)}
                </td>
                <td className="upset-score">{team.upset_score.toFixed(1)}</td>
                <td className="alerts">
                  {team.opponent.slumping && <span className="alert opp-cold" title="Opponent is slumping">⚠️</span>}
                  {team.win_streak >= 5 && <span className="alert hot-streak" title={`${team.win_streak} game win streak`}>🔥</span>}
                  {team.rank_change >= 20 && <span className="alert rising" title="Rising in rankings">📈</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="legend">
        <span><strong>Mom Diff</strong> = Underdog momentum minus Opponent momentum</span>
        <span>⚠️ = Opponent is cold (momentum &lt; 50 or negative vs-expected)</span>
        <span>🔥 = 5+ game win streak</span>
        <span>📈 = Rising 20+ spots in rankings</span>
      </div>
    </div>
  );
}

function VulnerableFavoritesTable({ teams, onTeamClick }) {
  if (!teams.length) {
    return <div className="no-data">No vulnerable favorites found</div>;
  }

  return (
    <div className="vulnerable-section">
      <div className="section-intro">
        <h2>⚠️ Vulnerable Favorites</h2>
        <p>Top 6 seeds with low momentum - potential upset targets</p>
      </div>
      
      <div className="table-container">
        <table className="momentum-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Team</th>
              <th>Seed</th>
              <th>Region</th>
              <th>Record</th>
              <th>Streak</th>
              <th>vs Exp</th>
              <th>Rk Chg</th>
              <th>Score</th>
              <th>Trend</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((team, idx) => (
              <tr key={team.team_id} className="vulnerable-row clickable-row" onClick={() => onTeamClick(team)}>
                <td className="rank">{idx + 1}</td>
                <td className="team-name">
                  <div className="team-name-inner">
                    <TeamLogo logoUrl={team.logo_url} teamName={team.name} size={28} />
                    <div className="team-name-text">
                      <span className="name">{team.name}</span>
                      <span className="conference">{team.conference}</span>
                    </div>
                  </div>
                </td>
                <td className="seed-cell">({team.seed})</td>
                <td className="region-cell">{team.region}</td>
                <td className="record">{team.wins}-{team.losses}</td>
                <td className="streak">
                  {team.win_streak > 0 && <span className="win-streak">W{team.win_streak}</span>}
                  {team.loss_streak > 0 && <span className="loss-streak">L{team.loss_streak}</span>}
                  {!team.win_streak && !team.loss_streak && '-'}
                </td>
                <td className={`vs-exp ${team.avg_vs_expected >= 0 ? 'positive' : 'negative'}`}>
                  {team.avg_vs_expected !== null ? (team.avg_vs_expected >= 0 ? '+' : '') + team.avg_vs_expected.toFixed(1) : 'N/A'}
                </td>
                <td className={`rank-change ${team.rank_change > 0 ? 'positive' : team.rank_change < 0 ? 'negative' : ''}`}>
                  {team.rank_change > 0 ? '+' : ''}{team.rank_change || 0}
                </td>
                <td className="score low">{team.momentum_score.toFixed(1)}</td>
                <td className="trend" style={{ color: TREND_COLORS[team.trend] }}>
                  {TREND_ICONS[team.trend]}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="insight-box">
        💡 These favored teams are slumping heading into March - consider picking against them in early rounds
      </div>
    </div>
  );
}

function TeamCardModal({ team, onClose }) {
  const [teamDetails, setTeamDetails] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch additional team details
    fetch(`${API_BASE}/api/team/${team.team_id}/ratings`)
      .then(res => res.json())
      .then(data => {
        setTeamDetails(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error fetching team details:', err);
        setLoading(false);
      });
  }, [team.team_id]);

  // Close on escape key
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  // Close on backdrop click
  const handleBackdropClick = (e) => {
    if (e.target.classList.contains('modal-backdrop')) {
      onClose();
    }
  };

  return (
    <div className="modal-backdrop" onClick={handleBackdropClick}>
      <div className="team-card-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        
        <div className="team-card-header">
          <TeamLogo logoUrl={team.logo_url} teamName={team.name} size={64} />
          <div className="team-card-title">
            <h2>{team.name}</h2>
            <p className="team-card-subtitle">
              {team.conference} {team.seed && `• #${team.seed} Seed`} {team.region && `• ${team.region}`}
            </p>
          </div>
        </div>

        <div className="team-card-body">
          {/* Momentum Summary */}
          <div className="team-card-section">
            <h3>Momentum</h3>
            <div className="team-card-stats">
              <div className="stat-box">
                <span className="stat-value" style={{ color: TREND_COLORS[team.trend] }}>
                  {team.momentum_score?.toFixed(1) || 'N/A'}
                </span>
                <span className="stat-label">Score</span>
              </div>
              <div className="stat-box">
                <span className="stat-value">{TREND_ICONS[team.trend]}</span>
                <span className="stat-label">Trend</span>
              </div>
              <div className="stat-box">
                <span className={`stat-value ${team.avg_vs_expected >= 0 ? 'positive' : 'negative'}`}>
                  {team.avg_vs_expected !== null ? (team.avg_vs_expected >= 0 ? '+' : '') + team.avg_vs_expected?.toFixed(1) : 'N/A'}
                </span>
                <span className="stat-label">vs Expected</span>
              </div>
              <div className="stat-box">
                <span className={`stat-value ${team.rank_change > 0 ? 'positive' : team.rank_change < 0 ? 'negative' : ''}`}>
                  {team.rank_change > 0 ? '+' : ''}{team.rank_change || 0}
                </span>
                <span className="stat-label">Rank Δ</span>
              </div>
            </div>
          </div>

          {/* Record & Streaks */}
          <div className="team-card-section">
            <h3>Season</h3>
            <div className="team-card-stats">
              <div className="stat-box">
                <span className="stat-value">{team.wins}-{team.losses}</span>
                <span className="stat-label">L10 Record</span>
              </div>
              <div className="stat-box">
                <span className="stat-value">#{team.kenpom_rank}</span>
                <span className="stat-label">KenPom</span>
              </div>
              <div className="stat-box">
                {team.win_streak > 0 && (
                  <>
                    <span className="stat-value win-streak">W{team.win_streak}</span>
                    <span className="stat-label">Streak</span>
                  </>
                )}
                {team.loss_streak > 0 && (
                  <>
                    <span className="stat-value loss-streak">L{team.loss_streak}</span>
                    <span className="stat-label">Streak</span>
                  </>
                )}
                {!team.win_streak && !team.loss_streak && (
                  <>
                    <span className="stat-value">-</span>
                    <span className="stat-label">Streak</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* KenPom Ratings if available */}
          {teamDetails && teamDetails.ratings && (
            <div className="team-card-section">
              <h3>KenPom Ratings</h3>
              <div className="team-card-stats">
                <div className="stat-box">
                  <span className="stat-value">{teamDetails.ratings.adj_em?.toFixed(1)}</span>
                  <span className="stat-label">AdjEM</span>
                </div>
                <div className="stat-box">
                  <span className="stat-value">{teamDetails.ratings.adj_oe?.toFixed(1)}</span>
                  <span className="stat-label">AdjO</span>
                </div>
                <div className="stat-box">
                  <span className="stat-value">{teamDetails.ratings.adj_de?.toFixed(1)}</span>
                  <span className="stat-label">AdjD</span>
                </div>
                <div className="stat-box">
                  <span className="stat-value">{teamDetails.ratings.adj_tempo?.toFixed(1)}</span>
                  <span className="stat-label">Tempo</span>
                </div>
              </div>
            </div>
          )}

          {/* Tournament info if seeded */}
          {team.seed && team.region && (
            <div className="team-card-section">
              <h3>Tournament</h3>
              <div className="team-card-tournament">
                <span className="seed-badge">#{team.seed} Seed</span>
                <span className="region-badge">{team.region} Region</span>
              </div>
            </div>
          )}

          {loading && <div className="loading-small">Loading additional stats...</div>}
        </div>
      </div>
    </div>
  );
}

export default MomentumTracker;