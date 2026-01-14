import { useState, useEffect } from 'react';
import TeamCard from '../compare/TeamCard';
import './BracketVisualizer.css';

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

    // Fetch full team data when a team is selected
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

    // Find opponent for a team
    const findOpponent = (team, region) => {
        if (!team || !bracketData[region]) return null;
        
        const bracketOrder = [
            { high: 1, low: 16 },
            { high: 8, low: 9 },
            { high: 5, low: 12 },
            { high: 4, low: 13 },
            { high: 6, low: 11 },
            { high: 3, low: 14 },
            { high: 7, low: 10 },
            { high: 2, low: 15 }
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

    // Click team in bracket -> Open matchup preview
    const handleTeamClick = (team, region) => {
        const opponent = findOpponent(team, region);
        if (opponent) {
            const highTeam = team.seed < opponent.seed ? team : opponent;
            const lowTeam = team.seed < opponent.seed ? opponent : team;
            setSelectedMatchup({ highTeam, lowTeam, region });
            setSelectedTeam(null);
        }
    };

    // Click team in matchup preview -> Show full TeamCard
    const handleTeamCardClick = (team, region) => {
        setSelectedTeam({ team, region });
    };

    // Go back to matchup from TeamCard
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
                            onTeamClick={(team) => handleTeamClick(team, region)}
                            selectedMatchup={selectedMatchup?.region === region ? selectedMatchup : null}
                        />
                    )
                ))}
            </div>

            {/* Matchup Preview Modal */}
            {selectedMatchup && !selectedTeam && (
                <MatchupModal 
                    matchup={selectedMatchup} 
                    onClose={() => setSelectedMatchup(null)}
                    onTeamClick={(team) => handleTeamCardClick(team, selectedMatchup.region)}
                />
            )}

            {/* Full Team Card Modal */}
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

function RegionBracket({ region, data, onTeamClick, selectedMatchup }) {
    if (!data || !data.teams) {
        return <div className="region-bracket empty">No data for {region}</div>;
    }

    const bracketOrder = [
        { high: 1, low: 16 },
        { high: 8, low: 9 },
        { high: 5, low: 12 },
        { high: 4, low: 13 },
        { high: 6, low: 11 },
        { high: 3, low: 14 },
        { high: 7, low: 10 },
        { high: 2, low: 15 }
    ];

    const getTeamBySeed = (seed) => {
        return data.teams.find(t => t.seed === seed);
    };

    const hasPlayIn = (seed) => {
        return data.teams.filter(t => t.seed === seed).length > 1;
    };

    // Check if a team is in the selected matchup
    const isTeamSelected = (team) => {
        if (!selectedMatchup || !team) return false;
        return team.team_id === selectedMatchup.highTeam?.team_id || 
               team.team_id === selectedMatchup.lowTeam?.team_id;
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
                            onTeamClick={onTeamClick}
                            isHighSelected={isTeamSelected(highTeam)}
                            isLowSelected={isTeamSelected(lowTeam)}
                        />
                    );
                })}
            </div>
        </div>
    );
}

function Matchup({ highTeam, lowTeam, highSeed, lowSeed, isPlayIn, onTeamClick, isHighSelected, isLowSelected }) {
    return (
        <div className="matchup">
            <div className="matchup-inner">
                <TeamRow 
                    team={highTeam} 
                    seed={highSeed} 
                    position="top" 
                    onClick={() => highTeam && onTeamClick(highTeam)}
                    isSelected={isHighSelected}
                />
                <div className="matchup-divider"></div>
                <TeamRow 
                    team={lowTeam} 
                    seed={lowSeed} 
                    position="bottom" 
                    isPlayIn={isPlayIn}
                    onClick={() => lowTeam && onTeamClick(lowTeam)}
                    isSelected={isLowSelected}
                />
            </div>
        </div>
    );
}

function TeamRow({ team, seed, position, isPlayIn = false, onClick, isSelected = false }) {
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
            className={`team-row ${position} ${isSelected ? 'selected' : ''}`}
            style={{ '--team-color': team.primary_color || '#444' }}
            onClick={onClick}
        >
            <span className="team-seed">{seed}</span>
            <div className="team-color-bar"></div>
            {team.logo_url && (
                <img 
                    src={team.logo_url} 
                    alt="" 
                    className="team-logo"
                    onError={(e) => e.target.style.display = 'none'}
                />
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
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [res1, res2] = await Promise.all([
                    fetch(`/api/team/${highTeam.team_id}/ratings`),
                    fetch(`/api/team/${lowTeam.team_id}/ratings`)
                ]);
                const data1 = await res1.json();
                const data2 = await res2.json();
                setTeam1Data(data1);
                setTeam2Data(data2);
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

    const getRecord = (data) => {
        if (!data?.ratings) return '';
        return `${data.ratings.wins}-${data.ratings.losses}`;
    };

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

                        <div className="modal-stats">
                            <h4>Statistical Comparison</h4>
                            
                            <div className="stats-section">
                                <div className="stats-section-title">Rankings</div>
                                <StatBar 
                                    label="KenPom" 
                                    val1={highTeam.rank_adj_em} 
                                    val2={lowTeam.rank_adj_em}
                                    lowerBetter={true}
                                />
                                <StatBar 
                                    label="NET" 
                                    val1={team1Data?.resume?.net_rank || 'N/A'} 
                                    val2={team2Data?.resume?.net_rank || 'N/A'}
                                    lowerBetter={true}
                                />
                            </div>

                            <div className="stats-section">
                                <div className="stats-section-title">Efficiency</div>
                                <StatBar 
                                    label="Adj. EM" 
                                    val1={highTeam.adj_em?.toFixed(1)} 
                                    val2={lowTeam.adj_em?.toFixed(1)}
                                />
                                <StatBar 
                                    label="Offense" 
                                    val1={highTeam.adj_oe?.toFixed(1)} 
                                    val2={lowTeam.adj_oe?.toFixed(1)}
                                />
                                <StatBar 
                                    label="Defense" 
                                    val1={highTeam.adj_de?.toFixed(1)} 
                                    val2={lowTeam.adj_de?.toFixed(1)}
                                    lowerBetter={true}
                                />
                            </div>

                            <div className="stats-section">
                                <div className="stats-section-title">Shooting</div>
                                <StatBar 
                                    label="eFG%" 
                                    val1={team1Data?.four_factors?.efg_pct?.toFixed(1) || 'N/A'} 
                                    val2={team2Data?.four_factors?.efg_pct?.toFixed(1) || 'N/A'}
                                />
                                <StatBar 
                                    label="FT Rate" 
                                    val1={team1Data?.four_factors?.ft_rate?.toFixed(1) || 'N/A'} 
                                    val2={team2Data?.four_factors?.ft_rate?.toFixed(1) || 'N/A'}
                                />
                            </div>

                            <div className="stats-section resume-section">
                                <div className="stats-section-title">Resume</div>
                                <div className="resume-comparison">
                                    <div className="resume-team">
                                        <div className="resume-record">
                                            <span className="quad-label">Q1</span>
                                            <span className="quad-value">{team1Data?.resume?.quad1_wins || 0}-{team1Data?.resume?.quad1_losses || 0}</span>
                                        </div>
                                        <div className="resume-record">
                                            <span className="quad-label">Q2</span>
                                            <span className="quad-value">{team1Data?.resume?.quad2_wins || 0}-{team1Data?.resume?.quad2_losses || 0}</span>
                                        </div>
                                        <div className="resume-record bad-losses">
                                            <span className="quad-label">Bad L</span>
                                            <span className="quad-value">{getBadLosses(team1Data)}</span>
                                        </div>
                                    </div>
                                    <div className="resume-divider"></div>
                                    <div className="resume-team">
                                        <div className="resume-record">
                                            <span className="quad-label">Q1</span>
                                            <span className="quad-value">{team2Data?.resume?.quad1_wins || 0}-{team2Data?.resume?.quad1_losses || 0}</span>
                                        </div>
                                        <div className="resume-record">
                                            <span className="quad-label">Q2</span>
                                            <span className="quad-value">{team2Data?.resume?.quad2_wins || 0}-{team2Data?.resume?.quad2_losses || 0}</span>
                                        </div>
                                        <div className="resume-record bad-losses">
                                            <span className="quad-label">Bad L</span>
                                            <span className="quad-value">{getBadLosses(team2Data)}</span>
                                        </div>
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
    
    return (
        <div 
            className="modal-team clickable" 
            style={{ '--team-color': team.primary_color }}
            onClick={onClick}
        >
            {team.logo_url && <img src={team.logo_url} alt={team.name} />}
            <div className="modal-team-info">
                <span className="modal-seed">#{team.seed} Seed</span>
                <div className="modal-name-row">
                    <span className="modal-name">{team.name}</span>
                    {record && <span className="modal-record">{record}</span>}
                </div>
                <span className="modal-conf">{team.conference}</span>
            </div>
            <span className="click-hint">Click for full stats</span>
        </div>
    );
}

function StatBar({ label, val1, val2, lowerBetter = false }) {
    const num1 = parseFloat(val1);
    const num2 = parseFloat(val2);
    
    let winner1 = false;
    let winner2 = false;
    
    if (!isNaN(num1) && !isNaN(num2)) {
        if (lowerBetter) {
            winner1 = num1 < num2;
            winner2 = num2 < num1;
        } else {
            winner1 = num1 > num2;
            winner2 = num2 > num1;
        }
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