import { useState, useEffect, Component } from 'react';
import { PlayerList } from '../player/PlayerCard';

/**
 * Calculate relative luminance of a hex color
 * Returns value between 0 (black) and 1 (white)
 */
function getLuminance(hexColor) {
    if (!hexColor || typeof hexColor !== 'string') return 1;
    const hex = hexColor.replace('#', '');
    if (hex.length !== 6 && hex.length !== 3) return 1;
    const r = parseInt(hex.substr(0, 2), 16) / 255;
    const g = parseInt(hex.substr(2, 2), 16) / 255;
    const b = parseInt(hex.substr(4, 2), 16) / 255;
    const rLinear = r <= 0.03928 ? r / 12.92 : Math.pow((r + 0.055) / 1.055, 2.4);
    const gLinear = g <= 0.03928 ? g / 12.92 : Math.pow((g + 0.055) / 1.055, 2.4);
    const bLinear = b <= 0.03928 ? b / 12.92 : Math.pow((b + 0.055) / 1.055, 2.4);
    return 0.2126 * rLinear + 0.7152 * gLinear + 0.0722 * bLinear;
}

function isColorLight(hexColor) {
    return getLuminance(hexColor) > 0.1;
}

// ── Error Boundary ────────────────────────────────────────────────────────────
// Wraps sections that make fetch calls. If a section throws for any reason,
// it renders a silent fallback instead of crashing the entire card.
// React requires this to be a class component — hooks can't catch render errors.

class SectionErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }
    static getDerivedStateFromError() {
        return { hasError: true };
    }
    componentDidCatch(error, info) {
        console.error('TeamCard section error:', error, info);
    }
    render() {
        if (this.state.hasError) {
            return (
                <div className="metrics-section">
                    <h3 className="section-title">{this.props.title || 'Section'}</h3>
                    <div className="metric-row">
                        <span className="metric-label" style={{ color: '#888', fontStyle: 'italic' }}>
                            Unable to load this section
                        </span>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}

// ── Shooting Profile Section ──────────────────────────────────────────────────

function ShootingProfile({ teamId }) {
    const [shooting, setShooting] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!teamId) return;
        setLoading(true);
        fetch(`/api/team/${teamId}/shooting`)
            .then(res => res.json())
            .then(data => {
                setShooting(data.shooting ?? null);
                setLoading(false);
            })
            .catch(() => {
                setShooting(null);
                setLoading(false);
            });
    }, [teamId]);

    if (loading) {
        return (
            <div className="metrics-section">
                <h3 className="section-title">Shooting Profile</h3>
                <div className="metric-row">
                    <span className="metric-label" style={{ color: '#888', fontStyle: 'italic' }}>
                        Loading stats...
                    </span>
                </div>
            </div>
        );
    }

    // Safely destructure — API shape may vary if scraper hasn't run yet
    const threePoint = shooting?.three_point ?? {};
    const freeThrow  = shooting?.free_throw  ?? {};

    if (!shooting || (!threePoint.pct && !freeThrow.pct)) {
        return (
            <div className="metrics-section">
                <h3 className="section-title">Shooting Profile</h3>
                <div className="metric-row">
                    <span className="metric-label" style={{ color: '#888', fontStyle: 'italic' }}>
                        Stats not yet available
                    </span>
                </div>
            </div>
        );
    }

    return (
        <div className="metrics-section">
            <h3 className="section-title">Shooting Profile</h3>

            {/* Offense */}
            <div style={{ marginBottom: '1.5rem' }}>
                <div className="factor-label">Offense</div>
                <div className="metric-row">
                    <span className="metric-label">3PT%</span>
                    <span className="metric-value">
                        {threePoint.pct?.toFixed(1)}%
                        <span className="metric-sub">
                            ({threePoint.made?.toFixed(1)}-{threePoint.att?.toFixed(1)})
                        </span>
                    </span>
                </div>
                <div className="metric-row">
                    <span className="metric-label">FT%</span>
                    <span className="metric-value">
                        {freeThrow.pct?.toFixed(1)}%
                        <span className="metric-sub">
                            ({freeThrow.made?.toFixed(1)}-{freeThrow.att?.toFixed(1)})
                        </span>
                    </span>
                </div>
                <div className="metric-row">
                    <span className="metric-label">FT Rate</span>
                    <span className="metric-value">
                        {shooting.ft_rate?.toFixed(3)}
                        <span className="metric-sub" style={{ marginLeft: '6px', color: '#888', fontSize: '0.75rem' }}>
                            FTA/FGA
                        </span>
                    </span>
                </div>
            </div>

            {/* Defense */}
            <div>
                <div className="factor-label">Defense</div>
                <div className="metric-row">
                    <span className="metric-label">Opp. 3PT% Allowed</span>
                    <span className="metric-value">
                        {shooting.opp_fg3_pct != null
                            ? `${shooting.opp_fg3_pct.toFixed(1)}%`
                            : <span style={{ color: '#888' }}>N/A</span>
                        }
                    </span>
                </div>
            </div>
        </div>
    );
}

// ── Quality Wins / Notable Losses Section ─────────────────────────────────────
// Fetches game context from /api/team/<id>/resume-games.
// Displayed below the existing quad record breakdown in the resume section.
// Each entry shows: opponent logo, home/away, opponent name, NET rank, score.

function ResumeGames({ teamId }) {
    const [resumeGames, setResumeGames] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!teamId) return;
        setLoading(true);
        fetch(`/api/team/${teamId}/resume-games`)
            .then(res => res.json())
            .then(data => {
                setResumeGames(data);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, [teamId]);

    if (loading) {
        return (
            <div style={{ marginTop: '1.5rem' }}>
                <div style={{ color: '#888', fontStyle: 'italic', fontSize: '0.85rem' }}>
                    Loading game results...
                </div>
            </div>
        );
    }

    if (!resumeGames) return null;

    const { quality_wins, notable_losses } = resumeGames;
    const hasWins   = quality_wins   && quality_wins.length > 0;
    const hasLosses = notable_losses && notable_losses.length > 0;

    if (!hasWins && !hasLosses) return null;

    return (
        <div style={{ marginTop: '1.5rem' }}>

            {/* Quality Wins */}
            {hasWins && (
                <div style={{ marginBottom: '1.25rem' }}>
                    <div className="factor-label">Quality Wins</div>
                    {quality_wins.map((game, i) => (
                        <GameRow key={game.game_id || i} game={game} isWin={true} />
                    ))}
                </div>
            )}

            {/* Notable Losses */}
            {hasLosses && (
                <div>
                    <div className="factor-label">
                        Notable Losses
                    </div>
                    {notable_losses.map((game, i) => (
                        <GameRow key={game.game_id || i} game={game} isWin={false} />
                    ))}
                </div>
            )}
        </div>
    );
}

// Individual game row — used for both wins and losses
function GameRow({ game, isWin }) {
    const isBadLoss = !isWin && game.is_bad_loss;

    // Format date: "Jan 14" from "2026-01-14"
    const formatDate = (dateStr) => {
        if (!dateStr) return '';
        const d = new Date(dateStr + 'T00:00:00'); // force local parse
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 0',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
        }}>
            {/* Opponent logo */}
            {game.opponent.logo ? (
                <img
                    src={game.opponent.logo}
                    alt={game.opponent.name}
                    style={{ width: '22px', height: '22px', objectFit: 'contain', flexShrink: 0 }}
                />
            ) : (
                <div style={{ width: '22px', height: '22px', flexShrink: 0 }} />
            )}

            {/* Location indicator */}
            <span style={{
                fontSize: '0.75rem',
                color: '#888',
                fontWeight: 600,
                minWidth: '16px',
                flexShrink: 0,
            }}>
                {game.location}
            </span>

            {/* Opponent name + NET rank */}
            <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{
                    fontSize: '0.85rem',
                    color: isBadLoss ? '#ff6b6b' : '#e0e0e0',
                    fontWeight: isBadLoss ? 600 : 400,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: 'block',
                }}>
                    {game.opponent.name}
                    {game.opponent.net_rank && (
                        <span style={{ color: '#888', fontSize: '0.75rem', marginLeft: '5px' }}>
                            #{game.opponent.net_rank} NET
                        </span>
                    )}
                </span>
            </div>

            {/* Score */}
            {game.score.team != null && game.score.opponent != null && (
                <span style={{
                    fontSize: '0.8rem',
                    color: isWin ? '#4ade80' : (isBadLoss ? '#ff6b6b' : '#f87171'),
                    fontWeight: 600,
                    flexShrink: 0,
                }}>
                    {game.score.team}-{game.score.opponent}
                </span>
            )}

            {/* Date */}
            <span style={{
                fontSize: '0.72rem',
                color: '#666',
                flexShrink: 0,
                minWidth: '36px',
                textAlign: 'right',
            }}>
                {formatDate(game.date)}
            </span>
        </div>
    );
}

// ── Main TeamCard ─────────────────────────────────────────────────────────────

function TeamCard({ data, showPlayers = true }) {
    const { team, ratings, resume } = data;
    // four_factors intentionally omitted — replaced by ShootingProfile

    if (!team || !ratings) {
        return (
            <div className="team-card">
                <div className="card-content">
                    <p>No data available</p>
                </div>
            </div>
        );
    }

    const primaryColor   = team.primary_color   || '#4A9EFF';
    const secondaryColor = team.secondary_color || '#FFFFFF';

    const secondaryIsLight = isColorLight(secondaryColor);
    const headerBgColor    = secondaryIsLight ? secondaryColor : '#FFFFFF';
    const headerBgIsLight  = isColorLight(headerBgColor);
    const headerTextColor  = headerBgIsLight ? primaryColor : '#FFFFFF';

    const headerStyle = {
        background: `linear-gradient(135deg, ${headerBgColor} 0%, ${headerBgColor}DD 100%)`,
        borderRadius: '8px',
        padding: '15px',
        marginBottom: '15px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    };

    return (
        <div className="team-card" style={{ borderColor: primaryColor + '40' }}>
            <div className="team-color-accent" style={{
                background: `linear-gradient(90deg, ${primaryColor} 0%, ${secondaryColor} 100%)`
            }} />
            <div className="card-content">

                {/* ── Header ── */}
                <div className="team-header" style={headerStyle}>
                    {team.logo_url && (
                        <div className="team-logo-container">
                            <img src={team.logo_url} alt={team.name} className="team-logo" />
                        </div>
                    )}
                    <div className="team-info-container">
                        <h2 className="team-title" style={{ color: headerTextColor }}>{team.name}</h2>
                        <div className="team-info" style={{ color: headerTextColor }}>
                            {team.conference} • {team.coach}<br />
                            <span className="record" style={{ color: headerTextColor, fontWeight: 600 }}>
                                {ratings.wins}-{ratings.losses}
                            </span>
                        </div>
                    </div>
                </div>

                {/* ── Overall Rankings ── */}
                <div className="metrics-section">
                    <h3 className="section-title">Overall Rankings</h3>
                    <div className="metric-row">
                        <span className="metric-label">Adjusted Efficiency Margin</span>
                        <span className="metric-value">
                            {ratings.adj_em?.toFixed(2)}
                            <span className="rank">#{ratings.rank_adj_em}</span>
                        </span>
                    </div>
                    <div className="metric-row">
                        <span className="metric-label">Adjusted Offensive Efficiency</span>
                        <span className="metric-value">
                            {ratings.adj_oe?.toFixed(1)}
                            <span className="rank">#{ratings.rank_adj_oe}</span>
                        </span>
                    </div>
                    <div className="metric-row">
                        <span className="metric-label">Adjusted Defensive Efficiency</span>
                        <span className="metric-value">
                            {ratings.adj_de?.toFixed(1)}
                            <span className="rank">#{ratings.rank_adj_de}</span>
                        </span>
                    </div>
                    <div className="metric-row">
                        <span className="metric-label">Tempo</span>
                        <span className="metric-value">
                            {ratings.tempo?.toFixed(1)}
                            <span className="rank">#{ratings.rank_tempo}</span>
                        </span>
                    </div>
                </div>

                {/* ── Strength of Schedule ── */}
                <div className="metrics-section">
                    <h3 className="section-title">Strength of Schedule</h3>
                    <div className="metric-row">
                        <span className="metric-label">Overall SOS</span>
                        <span className="metric-value">
                            {ratings.sos?.toFixed(2)}
                            <span className="rank">#{ratings.rank_sos}</span>
                        </span>
                    </div>
                    <div className="metric-row">
                        <span className="metric-label">Non-Conference SOS</span>
                        <span className="metric-value">
                            {ratings.ncsos?.toFixed(2)}
                            <span className="rank">#{ratings.rank_ncsos}</span>
                        </span>
                    </div>
                </div>

                {/* ── Shooting Profile (replaces Four Factors) ── */}
                <SectionErrorBoundary title="Shooting Profile">
                    <ShootingProfile teamId={team.team_id} />
                </SectionErrorBoundary>

                {/* ── Tournament Resume ── */}
                {resume && (
                    <div className="metrics-section">
                        <h3 className="section-title">Tournament Resume</h3>
                        <div className="metric-row">
                            <span className="metric-label">NET Ranking</span>
                            <span className="metric-value">#{resume.net_rank || 'N/A'}</span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Quadrant 1</span>
                            <span className="metric-value">{resume.quad1_wins}-{resume.quad1_losses}</span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Quadrant 2</span>
                            <span className="metric-value">{resume.quad2_wins}-{resume.quad2_losses}</span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Quadrant 3</span>
                            <span className="metric-value">{resume.quad3_wins}-{resume.quad3_losses}</span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Quadrant 4</span>
                            <span className="metric-value">{resume.quad4_wins}-{resume.quad4_losses}</span>
                        </div>
                        {resume.sor_rank && (
                            <div className="metric-row">
                                <span className="metric-label">Strength of Record</span>
                                <span className="metric-value">#{resume.sor_rank}</span>
                            </div>
                        )}

                        {/* Quality wins / notable losses with game context */}
                        <SectionErrorBoundary title="Resume Games">
                            <ResumeGames teamId={team.team_id} />
                        </SectionErrorBoundary>
                    </div>
                )}

                {/* ── Players ── */}
                {showPlayers && team.team_id && (
                    <PlayerList teamId={team.team_id} />
                )}

            </div>
        </div>
    );
}

export default TeamCard;