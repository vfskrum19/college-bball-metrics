import { useState, useEffect } from 'react';
import TeamCard from '../compare/TeamCard';
import { KeyPlayersPreview } from '../player/PlayerCard';
import './BracketVisualizer.css';

/**
 * Calculate relative luminance of a hex color
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
    return getLuminance(hexColor) > 0.15;
}

function BracketVisualizer() {
    const [bracketData, setBracketData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeRegion, setActiveRegion] = useState('all');
    const [selectedMatchup, setSelectedMatchup] = useState(null);
    const [selectedTeam, setSelectedTeam] = useState(null);
    const [teamCardData, setTeamCardData] = useState(null);
    const [teamCardLoading, setTeamCardLoading] = useState(false);

    useEffect(() => {
        fetch('/api/bracket')
            .then(res => {
                if (!res.ok) throw new Error('Failed to fetch bracket');
                return res.json();
            })
            .then(data => {
                setBracketData(data.bracket);
                setLoading(false);
            })
            .catch(err => {
                setError(err.message);
                setLoading(false);
            });
    }, []);

    useEffect(() => {
        if (selectedTeam) {
            setTeamCardLoading(true);
            fetch(`/api/team/${selectedTeam.team.team_id}/ratings`)
                .then(res => res.json())
                .then(data => {
                    setTeamCardData(data);
                    setTeamCardLoading(false);
                })
                .catch(err => {
                    console.error('Error fetching team:', err);
                    setTeamCardLoading(false);
                });
        } else {
            setTeamCardData(null);
        }
    }, [selectedTeam]);

    if (loading) {
        return (
            <div className="bracket-loading">
                <div className="spinner"></div>
                <p>Loading bracket...</p>
            </div>
        );
    }

    if (error) {
        return <div className="bracket-error">Error: {error}</div>;
    }

    const regions = ['East', 'West', 'South', 'Midwest'];

    const findOpponent = (team, region) => {
        if (!team || !bracketData[region]) return null;
        
        const bracketOrder = [
            { high: 1, low: 16 }, { high: 8, low: 9 },
            { high: 5, low: 12 }, { high: 4, low: 13 },
            { high: 6, low: 11 }, { high: 3, low: 14 },
            { high: 7, low: 10 }, { high: 2, low: 15 }
        ];
        
        for (const pairing of bracketOrder) {
            if (team.seed === pairing.high) {
                return bracketData[region].teams.find(t => t.seed === pairing.low);
            }
            if (team.seed === pairing.low) {
                return bracketData[region].teams.find(t => t.seed === pairing.high);
            }
        }
        return null;
    };

    const handleMatchupClick = (highTeam, lowTeam, region) => {
        if (highTeam && lowTeam) {
            setSelectedMatchup({ highTeam, lowTeam, region });
            setSelectedTeam(null);
        }
    };

    const handleTeamCardClick = (team, region) => {
        setSelectedTeam({ team, region });
    };

    const handleBackToMatchup = () => {
        if (selectedTeam) {
            const opponent = findOpponent(selectedTeam.team, selectedTeam.region);
            if (opponent) {
                const highTeam = selectedTeam.team.seed < opponent.seed ? selectedTeam.team : opponent;
                const lowTeam = selectedTeam.team.seed < opponent.seed ? opponent : selectedTeam.team;
                setSelectedMatchup({ highTeam, lowTeam, region: selectedTeam.region });
                setSelectedTeam(null);
            }
        }
    };

    const handleCloseTeamCard = () => {
        setSelectedTeam(null);
        setTeamCardData(null);
    };

    return (
        <div className="bracket-visualizer">
            <div className="bracket-header">
                <h2>2026 NCAA Tournament</h2>
                <p className="bracket-subtitle">Bracket Matrix Consensus</p>
                
                <div className="region-tabs">
                    <button 
                        className={`region-tab ${activeRegion === 'all' ? 'active' : ''}`}
                        onClick={() => setActiveRegion('all')}
                    >
                        All Regions
                    </button>
                    {regions.map(region => (
                        <button 
                            key={region}
                            className={`region-tab ${activeRegion === region ? 'active' : ''}`}
                            onClick={() => setActiveRegion(region)}
                        >
                            {region}
                        </button>
                    ))}
                </div>
            </div>

            <div className={`bracket-container ${activeRegion !== 'all' ? 'single-region' : ''}`}>
                {regions.map(region => (
                    (activeRegion === 'all' || activeRegion === region) && (
                        <RegionBracket 
                            key={region}
                            region={region}
                            data={bracketData[region]}
                            onMatchupClick={(highTeam, lowTeam) => handleMatchupClick(highTeam, lowTeam, region)}
                            selectedMatchup={selectedMatchup?.region === region ? selectedMatchup : null}
                        />
                    )
                ))}
            </div>

            {selectedMatchup && !selectedTeam && (
                <MatchupModal 
                    matchup={selectedMatchup} 
                    onClose={() => setSelectedMatchup(null)}
                    onTeamClick={(team) => handleTeamCardClick(team, selectedMatchup.region)}
                />
            )}

            {selectedTeam && (
                <div className="modal-overlay" onClick={handleCloseTeamCard}>
                    <div className="team-card-modal" onClick={e => e.stopPropagation()}>
                        <button className="modal-close" onClick={handleCloseTeamCard}>×</button>
                        
                        <div className="team-card-header">
                            <span className="team-card-seed">#{selectedTeam.team.seed} Seed • {selectedTeam.region} Region</span>
                        </div>

                        {teamCardLoading ? (
                            <div className="modal-loading">
                                <div className="spinner"></div>
                            </div>
                        ) : teamCardData ? (
                            <>
                                <TeamCard data={teamCardData} />
                                
                                <div className="back-to-matchup-container">
                                    <button className="back-to-matchup-btn" onClick={handleBackToMatchup}>
                                        ← Back to Matchup Preview
                                    </button>
                                </div>
                            </>
                        ) : (
                            <div className="modal-error">Could not load team data</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

function RegionBracket({ region, data, onMatchupClick, selectedMatchup }) {
    if (!data || !data.teams) {
        return <div className="region-bracket empty">No data for {region}</div>;
    }

    const bracketOrder = [
        { high: 1, low: 16 }, { high: 8, low: 9 },
        { high: 5, low: 12 }, { high: 4, low: 13 },
        { high: 6, low: 11 }, { high: 3, low: 14 },
        { high: 7, low: 10 }, { high: 2, low: 15 }
    ];

    const getTeamBySeed = (seed) => data.teams.find(t => t.seed === seed);
    const hasPlayIn = (seed) => data.teams.filter(t => t.seed === seed).length > 1;
    
    const isMatchupSelected = (highTeam, lowTeam) => {
        if (!selectedMatchup || !highTeam || !lowTeam) return false;
        return (highTeam.team_id === selectedMatchup.highTeam?.team_id && 
                lowTeam.team_id === selectedMatchup.lowTeam?.team_id);
    };

    return (
        <div className="region-bracket">
            <div className="region-title">
                <h3>{region}</h3>
                <span className="region-subtitle">Region</span>
            </div>
            
            <div className="matchups-container">
                {bracketOrder.map((pairing, index) => {
                    const highTeam = getTeamBySeed(pairing.high);
                    const lowTeam = getTeamBySeed(pairing.low);
                    const isPlayIn = hasPlayIn(pairing.low) && (pairing.low === 11 || pairing.low === 16);
                    
                    return (
                        <Matchup
                            key={index}
                            highTeam={highTeam}
                            lowTeam={lowTeam}
                            highSeed={pairing.high}
                            lowSeed={pairing.low}
                            isPlayIn={isPlayIn}
                            onMatchupClick={onMatchupClick}
                            isSelected={isMatchupSelected(highTeam, lowTeam)}
                        />
                    );
                })}
            </div>
        </div>
    );
}

function Matchup({ highTeam, lowTeam, highSeed, lowSeed, isPlayIn, onMatchupClick, isSelected }) {
    const handleClick = () => {
        if (highTeam && lowTeam) {
            onMatchupClick(highTeam, lowTeam);
        }
    };

    return (
        <div 
            className={`matchup ${isSelected ? 'selected' : ''} ${highTeam && lowTeam ? 'clickable' : ''}`}
            onClick={handleClick}
        >
            <div className="matchup-inner">
                <TeamRow 
                    team={highTeam} 
                    seed={highSeed} 
                    position="top" 
                />
                <div className="matchup-divider"></div>
                <TeamRow 
                    team={lowTeam} 
                    seed={lowSeed} 
                    position="bottom" 
                    isPlayIn={isPlayIn}
                />
            </div>
        </div>
    );
}

function TeamRow({ team, seed, position, isPlayIn = false }) {
    if (!team) {
        return (
            <div className={`team-row ${position} empty`}>
                <span className="team-seed">{seed}</span>
                <span className="team-name">TBD</span>
            </div>
        );
    }

    return (
        <div 
            className={`team-row ${position}`}
            style={{ '--team-color': team.primary_color || '#444' }}
        >
            <span className="team-seed">{seed}</span>
            <div className="team-color-bar"></div>
            {team.logo_url && (
                <img src={team.logo_url} alt="" className="team-logo"
                    onError={(e) => e.target.style.display = 'none'} />
            )}
            <span className="team-name">{team.name}</span>
            <span className="team-rating">({team.rank_adj_em})</span>
            {isPlayIn && <span className="play-in-badge">★</span>}
        </div>
    );
}

function MatchupModal({ matchup, onClose, onTeamClick }) {
    const { highTeam, lowTeam, region } = matchup;
    const [team1Data, setTeam1Data] = useState(null);
const [team2Data, setTeam2Data] = useState(null);
const [team1Shooting, setTeam1Shooting] = useState(null);
const [team2Shooting, setTeam2Shooting] = useState(null);
const [loading, setLoading] = useState(true);

useEffect(() => {
    const fetchData = async () => {
        try {
            const [res1, res2, shot1, shot2] = await Promise.all([
                fetch(`/api/team/${highTeam.team_id}/ratings`),
                fetch(`/api/team/${lowTeam.team_id}/ratings`),
                fetch(`/api/team/${highTeam.team_id}/shooting`),
                fetch(`/api/team/${lowTeam.team_id}/shooting`),
            ]);
            setTeam1Data(await res1.json());
            setTeam2Data(await res2.json());
            const s1 = await shot1.json();
            const s2 = await shot2.json();
            setTeam1Shooting(s1.shooting ?? null);
            setTeam2Shooting(s2.shooting ?? null);
            setLoading(false);
        } catch (err) {
            console.error('Error fetching matchup data:', err);
            setLoading(false);
        }
    };
    fetchData();
}, [highTeam.team_id, lowTeam.team_id]);
    if (!highTeam || !lowTeam) return null;

    const kenPomDiff = (highTeam.adj_em - lowTeam.adj_em).toFixed(1);
    const favorite = highTeam.adj_em > lowTeam.adj_em ? highTeam : lowTeam;
    const fmtRate = (val) => val != null ? `${(val * 100).toFixed(1)}%` : 'N/A';
    const fmtPct  = (val) => val != null ? `${val.toFixed(1)}%` : 'N/A';

    const getBadLosses = (data) => {
        if (!data?.resume) return 0;
        return (data.resume.quad3_losses || 0) + (data.resume.quad4_losses || 0);
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content matchup-modal" onClick={e => e.stopPropagation()}>
                <button className="modal-close" onClick={onClose}>×</button>
                
                <div className="modal-header">
                    <span className="modal-region">{region} Region • First Round</span>
                    <h3>Matchup Preview</h3>
                </div>

                {loading ? (
                    <div className="modal-loading">
                        <div className="spinner"></div>
                    </div>
                ) : (
                    <>
                        <div className="modal-matchup">
                            <MatchupTeamCard 
                                team={highTeam} 
                                data={team1Data}
                                onClick={() => onTeamClick(highTeam)}
                            />
                            <div className="modal-vs">VS</div>
                            <MatchupTeamCard 
                                team={lowTeam} 
                                data={team2Data}
                                onClick={() => onTeamClick(lowTeam)}
                            />
                        </div>

                          {/* Scouting Narratives */}
                        {(team1Data?.narrative || team2Data?.narrative) && (
                            <div className="modal-narratives">
                                <h4>Scouting Report</h4>
                                <div className="narratives-comparison">
                                    <div className="narrative-team">
                                        {team1Data?.narrative ? (
                                            <p className="narrative-text">{team1Data.narrative}</p>
                                        ) : (
                                            <p className="narrative-text narrative-empty">No scouting report available.</p>
                                        )}
                                    </div>
                                    <div className="narrative-divider"></div>
                                    <div className="narrative-team">
                                        {team2Data?.narrative ? (
                                            <p className="narrative-text">{team2Data.narrative}</p>
                                        ) : (
                                            <p className="narrative-text narrative-empty">No scouting report available.</p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}
                        
                        {/* Key Players Section */}
                        <div className="modal-players">
                            <h4>Key Players</h4>
                            <div className="players-comparison">
                                <div className="team-players">
                                    <KeyPlayersPreview teamId={highTeam.team_id} />
                                </div>
                                <div className="players-divider"></div>
                                <div className="team-players">
                                    <KeyPlayersPreview teamId={lowTeam.team_id} />
                                </div>
                            </div>
                        </div>

                        <div className="modal-stats">
                            <h4>Statistical Comparison</h4>
                            
                            <div className="stats-section">
                                <div className="stats-section-title">Rankings</div>
                                <StatBar label="KenPom" val1={highTeam.rank_adj_em} val2={lowTeam.rank_adj_em} lowerBetter={true} />
                                <StatBar label="NET" val1={team1Data?.resume?.net_rank || 'N/A'} val2={team2Data?.resume?.net_rank || 'N/A'} lowerBetter={true} />
                            </div>

                            <div className="stats-section">
                                <div className="stats-section-title">Efficiency</div>
                                <StatBar label="Adj. EM" val1={highTeam.adj_em?.toFixed(1)} val2={lowTeam.adj_em?.toFixed(1)} />
                                <StatBar label="Offense" val1={highTeam.adj_oe?.toFixed(1)} val2={lowTeam.adj_oe?.toFixed(1)} />
                                <StatBar label="Defense" val1={highTeam.adj_de?.toFixed(1)} val2={lowTeam.adj_de?.toFixed(1)} lowerBetter={true} />
                            </div>

                            <div className="stats-section">
                                <div className="stats-section-title">Shooting</div>
                                <StatBar label="3PT%"    val1={fmtPct(team1Shooting?.three_point_pct)}  val2={fmtPct(team2Shooting?.three_point_pct)} />
                                <StatBar label="3PA Rate" val1={fmtRate(team1Shooting?.three_point_rate)} val2={fmtRate(team2Shooting?.three_point_rate)} />
                                <StatBar label="FT%"     val1={fmtPct(team1Shooting?.free_throw_pct)}   val2={fmtPct(team2Shooting?.free_throw_pct)} />
                                <StatBar label="FT Rate" val1={fmtRate(team1Shooting?.ft_rate)}          val2={fmtRate(team2Shooting?.ft_rate)} />
                            </div>

                            <div className="stats-section resume-section">
                                <div className="stats-section-title">Resume</div>
                                <div className="resume-comparison">
                                    <div className="resume-team">
                                        <div className="resume-record"><span className="quad-label">Q1</span><span className="quad-value">{team1Data?.resume?.quad1_wins || 0}-{team1Data?.resume?.quad1_losses || 0}</span></div>
                                        <div className="resume-record"><span className="quad-label">Q2</span><span className="quad-value">{team1Data?.resume?.quad2_wins || 0}-{team1Data?.resume?.quad2_losses || 0}</span></div>
                                        <div className="resume-record bad-losses"><span className="quad-label">Bad L</span><span className="quad-value">{getBadLosses(team1Data)}</span></div>
                                    </div>
                                    <div className="resume-divider"></div>
                                    <div className="resume-team">
                                        <div className="resume-record"><span className="quad-label">Q1</span><span className="quad-value">{team2Data?.resume?.quad1_wins || 0}-{team2Data?.resume?.quad1_losses || 0}</span></div>
                                        <div className="resume-record"><span className="quad-label">Q2</span><span className="quad-value">{team2Data?.resume?.quad2_wins || 0}-{team2Data?.resume?.quad2_losses || 0}</span></div>
                                        <div className="resume-record bad-losses"><span className="quad-label">Bad L</span><span className="quad-value">{getBadLosses(team2Data)}</span></div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="modal-prediction">
                            <span className="prediction-label">KenPom Projection</span>
                            <span className="prediction-value">
                                {favorite.name} by {Math.abs(parseFloat(kenPomDiff)).toFixed(1)} pts
                            </span>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

function MatchupTeamCard({ team, data, onClick }) {
    const record = data?.ratings ? `${data.ratings.wins}-${data.ratings.losses}` : '';
    
    // Use secondary color for background, with fallback
    const primaryColor = team.primary_color || '#4A9EFF';
    const secondaryColor = team.secondary_color || '#FFFFFF';
    const secondaryIsLight = isColorLight(secondaryColor);
    const headerBgColor = secondaryIsLight ? secondaryColor : '#FFFFFF';
    const headerTextColor = primaryColor;
    const headerSubTextColor = '#333333';
    
    return (
        <div 
            className="modal-team clickable" 
            style={{ 
                '--team-color': primaryColor,
                '--team-bg': headerBgColor,
                '--team-text': headerTextColor,
                '--team-subtext': headerSubTextColor
            }} 
            onClick={onClick}
        >
            <div className="modal-team-header">
                {team.logo_url && <img src={team.logo_url} alt={team.name} />}
                <div className="modal-team-info">
                    <span className="modal-seed">#{team.seed} Seed</span>
                    <div className="modal-name-row">
                        <span className="modal-name">{team.name}</span>
                    </div>
                    <div className="modal-team-meta">
                        <span className="modal-conf">{team.conference}</span>
                        {record && <span className="modal-record">{record}</span>}
                    </div>
                </div>
            </div>
            <span className="click-hint">Click for full stats</span>
        </div>
    );
}

function StatBar({ label, val1, val2, lowerBetter = false }) {
    const num1 = parseFloat(val1);
    const num2 = parseFloat(val2);
    let winner1 = false, winner2 = false;
    
    if (!isNaN(num1) && !isNaN(num2)) {
        if (lowerBetter) { winner1 = num1 < num2; winner2 = num2 < num1; }
        else { winner1 = num1 > num2; winner2 = num2 > num1; }
    }

    return (
        <div className="stat-bar-row">
            <div className={`stat-value left ${winner1 ? 'winner' : ''}`}>{val1}</div>
            <div className="stat-label">{label}</div>
            <div className={`stat-value right ${winner2 ? 'winner' : ''}`}>{val2}</div>
        </div>
    );
}

export default BracketVisualizer;