import { useState, useEffect } from 'react';
import './PlayerCard.css';

/**
 * PlayerCard - Displays a single player with their stats
 * Used in team comparison and bracket views
 */
function PlayerCard({ player, compact = false }) {
    if (!player) return null;

    const {
        name,
        position,
        jersey_number,
        height,
        weight,
        headshot_url,
        ppg,
        rpg,
        apg,
        fg_pct,
        three_pct,
        ft_pct,
        // Advanced stats
        usage_pct,
        bpm,
        per,
        ts_pct,
        role,
        role_reason
    } = player;

    // Format stat safely
    const formatStat = (val, decimals = 1) => {
        if (val === null || val === undefined) return '-';
        return Number(val).toFixed(decimals);
    };

    // Format percentage (stored as decimal like 0.456)
    const formatPct = (val) => {
        if (val === null || val === undefined) return '-';
        // If already in percentage form (> 1), just format it
        if (val > 1) return val.toFixed(1) + '%';
        // Otherwise convert from decimal
        return (val * 100).toFixed(1) + '%';
    };

    const getRoleBadge = () => {
        if (role === 'star') return { label: '★ STAR', className: 'role-star' };
        if (role === 'x_factor') return { label: '⚡ X-FACTOR', className: 'role-xfactor' };
        return null;
    };

    const roleBadge = getRoleBadge();

    // Format height/weight for display
    const heightDisplay = height || null;
    const weightDisplay = weight ? `${weight} lbs` : null;

    if (compact) {
        // Compact view for matchup previews
        // Line 1: #Number Name + Role Badge
        // Line 2: Position • Height • Weight
        // Line 3: Stats
        return (
            <div className="player-card compact">
                <div className="player-headshot-compact">
                    {headshot_url ? (
                        <img src={headshot_url} alt={name} onError={(e) => e.target.style.display = 'none'} />
                    ) : (
                        <div className="player-headshot-placeholder">👤</div>
                    )}
                </div>
                <div className="player-info-compact">
                    {/* Line 1: Number and Name */}
                    <div className="player-name-row">
                        {(jersey_number !== null && jersey_number !== '' && jersey_number !== undefined) && (
                            <span className="player-number-compact">#{jersey_number}</span>
                        )}
                        <span className="player-name-compact">{name}</span>
                    </div>
                    
                    {/* Line 2: Position, Height, Weight, Role Badge */}
                    <div className="player-physical-row">
                        {position && <span className="player-position-compact">{position}</span>}
                        {heightDisplay && <span className="player-height-compact">{heightDisplay}</span>}
                        {weightDisplay && <span className="player-weight-compact">{weightDisplay}</span>}
                        {roleBadge && (
                            <span className={`role-badge-compact ${roleBadge.className}`}>
                                {roleBadge.label}
                            </span>
                        )}
                    </div>
                    
                    {/* Line 3: Stats */}
                    <div className="player-stats-row">
                        <span className="player-stats-compact">
                            {formatStat(ppg)} PPG • {formatStat(rpg)} RPG • {formatStat(apg)} APG
                        </span>
                    </div>
                </div>
            </div>
        );
    }

    // Full view
    return (
        <div className="player-card">
            <div className="player-header">
                <div className="player-headshot">
                    {headshot_url ? (
                        <img src={headshot_url} alt={name} onError={(e) => e.target.style.display = 'none'} />
                    ) : (
                        <div className="player-headshot-placeholder">👤</div>
                    )}
                </div>
                <div className="player-info">
                    <h4 className="player-name">
                        {jersey_number && <span className="player-number">#{jersey_number}</span>}
                        {name}
                    </h4>
                    <div className="player-meta">
                        {position && <span className="player-position">{position}</span>}
                        {heightDisplay && <span className="player-height">• {heightDisplay}</span>}
                        {weightDisplay && <span className="player-weight">• {weightDisplay}</span>}
                    </div>
                    {roleBadge && (
                        <span className={`role-badge ${roleBadge.className}`}>
                            {roleBadge.label}
                        </span>
                    )}
                    {role_reason && <span className="role-reason">{role_reason}</span>}
                </div>
            </div>

            <div className="player-stats">
                <div className="stat-row primary-stats">
                    <div className="stat">
                        <span className="stat-value">{formatStat(ppg)}</span>
                        <span className="stat-label">PPG</span>
                    </div>
                    <div className="stat">
                        <span className="stat-value">{formatStat(rpg)}</span>
                        <span className="stat-label">RPG</span>
                    </div>
                    <div className="stat">
                        <span className="stat-value">{formatStat(apg)}</span>
                        <span className="stat-label">APG</span>
                    </div>
                </div>

                <div className="stat-row shooting-stats">
                    <div className="stat">
                        <span className="stat-value">{formatPct(fg_pct)}</span>
                        <span className="stat-label">FG%</span>
                    </div>
                    <div className="stat">
                        <span className="stat-value">{formatPct(three_pct)}</span>
                        <span className="stat-label">3P%</span>
                    </div>
                    <div className="stat">
                        <span className="stat-value">{formatPct(ft_pct)}</span>
                        <span className="stat-label">FT%</span>
                    </div>
                </div>

                {/* Advanced Stats Row - only show if we have the data */}
                {(bpm !== null || usage_pct !== null || per !== null) && (
                    <div className="stat-row advanced-stats">
                        <div className="stat">
                            <span className={`stat-value ${bpm > 0 ? 'positive' : bpm < 0 ? 'negative' : ''}`}>
                                {bpm > 0 ? '+' : ''}{formatStat(bpm)}
                            </span>
                            <span className="stat-label">BPM</span>
                        </div>
                        <div className="stat">
                            <span className="stat-value">{formatStat(usage_pct)}%</span>
                            <span className="stat-label">USG</span>
                        </div>
                        <div className="stat">
                            <span className="stat-value">{formatStat(per)}</span>
                            <span className="stat-label">PER</span>
                        </div>
                        <div className="stat">
                            <span className="stat-value">{formatStat(ts_pct)}%</span>
                            <span className="stat-label">TS%</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

/**
 * PlayerList - Displays all players for a team
 * Shows star and x_factor prominently, contributors below
 */
function PlayerList({ teamId, showAll = false }) {
    const [players, setPlayers] = useState([]);
    const [loading, setLoading] = useState(true);


    useEffect(() => {
        if (!teamId) return;

        fetch(`/api/team/${teamId}/players`)
            .then(res => res.json())
            .then(data => {
                setPlayers(data.players || []);
                setLoading(false);
            })
            .catch(err => {
                console.error('Error fetching players:', err);
                setLoading(false);
            });
    }, [teamId]);

    if (loading) {
        return <div className="player-list-loading">Loading players...</div>;
    }

    if (!players.length) {
        return <div className="player-list-empty">No player data available</div>;
    }

    const starPlayer = players.find(p => p.role === 'star');
    const xFactor = players.find(p => p.role === 'x_factor');
    const contributors = players.filter(p => p.role === 'contributor');

    // Show all if requested, otherwise show key players + expandable contributors
// Show all if requested, otherwise show key players + expandable contributors
    const visibleContributors = contributors.slice(0, 4);    return (
        <div className="player-list">
            <h4 className="player-list-title">Key Players</h4>
            
            <div className="key-players">
                {starPlayer && <PlayerCard player={starPlayer} />}
                {xFactor && <PlayerCard player={xFactor} />}
            </div>

            {visibleContributors.length > 0 && (
                <div className="contributors-section">
                    <h5 className="contributors-title">Contributors</h5>
                    <div className="contributors-grid">
                        {visibleContributors.map(player => (
                            <PlayerCard key={player.player_id} player={player} compact />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

/**
 * KeyPlayersPreview - Compact view for bracket matchup
 * Shows just star and x_factor
 */
function KeyPlayersPreview({ teamId }) {
    const [players, setPlayers] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!teamId) return;

        fetch(`/api/team/${teamId}/players/key`)
            .then(res => res.json())
            .then(data => {
                setPlayers(data.players || []);
                setLoading(false);
            })
            .catch(err => {
                console.error('Error fetching key players:', err);
                setLoading(false);
            });
    }, [teamId]);

    if (loading) {
        return <div className="key-players-loading">...</div>;
    }

    if (!players.length) {
        return null;
    }

    return (
        <div className="key-players-preview">
            {players.map(player => (
                <PlayerCard key={player.player_id} player={player} compact />
            ))}
        </div>
    );
}

export { PlayerCard, PlayerList, KeyPlayersPreview };
export default PlayerCard;