import { useState, useEffect } from 'react';

function BracketVisualizer() {
    const [bracketData, setBracketData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeRegion, setActiveRegion] = useState('all');

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

    return (
        <div className="bracket-visualizer">
            <div className="bracket-header">
                <h2>2026 NCAA Tournament Bracket</h2>
                <p className="bracket-subtitle">Bracket Matrix Consensus</p>
                
                <div className="region-tabs">
                    <button 
                        className={`region-tab ${activeRegion === 'all' ? 'active' : ''}`}
                        onClick={() => setActiveRegion('all')}
                    >
                        Full Bracket
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

            <div className={`bracket-regions ${activeRegion !== 'all' ? 'single-region' : ''}`}>
                {regions.map(region => (
                    (activeRegion === 'all' || activeRegion === region) && (
                        <RegionBracket 
                            key={region}
                            region={region}
                            data={bracketData[region]}
                        />
                    )
                ))}
            </div>
        </div>
    );
}

function RegionBracket({ region, data }) {
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

    return (
        <div className="region-bracket">
            <div className="region-header">
                <h3>{region} Region</h3>
            </div>
            
            <div className="bracket-column">
                {bracketOrder.map((pairing, index) => {
                    const highTeam = getTeamBySeed(pairing.high);
                    const lowTeam = getTeamBySeed(pairing.low);
                    
                    return (
                        <div key={index} className="matchup-container">
                            <div className="matchup">
                                <TeamSlot team={highTeam} seed={pairing.high} />
                                <TeamSlot team={lowTeam} seed={pairing.low} />
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function TeamSlot({ team, seed }) {
    if (!team) {
        return (
            <div className="team-slot empty">
                <span className="seed">{seed}</span>
                <span className="team-name">TBD</span>
            </div>
        );
    }

    return (
        <div className="team-slot" style={{
            '--team-primary': team.primary_color || '#333'
        }}>
            <span className="seed">{seed}</span>
            {team.logo_url && (
                <img 
                    src={team.logo_url} 
                    alt={team.name} 
                    className="team-logo-small"
                    onError={(e) => e.target.style.display = 'none'}
                />
            )}
            <span className="team-name">{team.name}</span>
            <span className="team-rank">#{team.rank_adj_em}</span>
        </div>
    );
}

export default BracketVisualizer;
