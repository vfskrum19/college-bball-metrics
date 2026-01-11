const { useState, useEffect } = React;

const API_BASE = 'http://localhost:5000/api';

function App() {
    const [team1Query, setTeam1Query] = useState('');
    const [team2Query, setTeam2Query] = useState('');
    const [team1Suggestions, setTeam1Suggestions] = useState([]);
    const [team2Suggestions, setTeam2Suggestions] = useState([]);
    const [selectedTeam1, setSelectedTeam1] = useState(null);
    const [selectedTeam2, setSelectedTeam2] = useState(null);
    const [team1Data, setTeam1Data] = useState(null);
    const [team2Data, setTeam2Data] = useState(null);
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState(null);

    useEffect(() => {
        fetch(`${API_BASE}/status`)
            .then(res => res.json())
            .then(data => setStatus(data))
            .catch(err => console.error('Status error:', err));
    }, []);

    useEffect(() => {
        if (team1Query.length < 2) {
            setTeam1Suggestions([]);
            return;
        }

        const timer = setTimeout(() => {
            fetch(`${API_BASE}/search?q=${encodeURIComponent(team1Query)}`)
                .then(res => res.json())
                .then(data => setTeam1Suggestions(data))
                .catch(err => console.error('Search error:', err));
        }, 300);

        return () => clearTimeout(timer);
    }, [team1Query]);

    useEffect(() => {
        if (team2Query.length < 2) {
            setTeam2Suggestions([]);
            return;
        }

        const timer = setTimeout(() => {
            fetch(`${API_BASE}/search?q=${encodeURIComponent(team2Query)}`)
                .then(res => res.json())
                .then(data => setTeam2Suggestions(data))
                .catch(err => console.error('Search error:', err));
        }, 300);

        return () => clearTimeout(timer);
    }, [team2Query]);

    // Fetch team data when both teams selected
    useEffect(() => {
        if (selectedTeam1 && selectedTeam2) {
            setLoading(true);
            fetch(`${API_BASE}/compare?team1=${selectedTeam1.team_id}&team2=${selectedTeam2.team_id}`)
                .then(res => res.json())
                .then(data => {
                    setTeam1Data(data.team1);
                    setTeam2Data(data.team2);
                    setTeam1Query('');  // Clear search box 1
                    setTeam2Query('');  
                    setLoading(false);
                })
                .catch(err => {
                    console.error('Comparison error:', err);
                    setLoading(false);
                });
        }
    }, [selectedTeam1, selectedTeam2]);

    const selectTeam1 = (team) => {
        setSelectedTeam1(team);
        setTeam1Query(team.name);
        setTeam1Suggestions([]);
    };

    const selectTeam2 = (team) => {
        setSelectedTeam2(team);
        setTeam2Query(team.name);
        setTeam2Suggestions([]);
    };

    return (
        <div className="container">
            <header>
                <h1>Court Vision</h1>
                <p className="subtitle">Metrics Driven Comparison Tool</p>
            </header>

            <div className="search-section">
                <div className="search-box">
                    <label className="search-label">Team 1</label>
                    <input
                        type="text"
                        value={team1Query}
                        onChange={(e) => setTeam1Query(e.target.value)}
                        placeholder="Search for a team..."
                    />
                    {team1Suggestions.length > 0 && (
                        <div className="suggestions">
                            {team1Suggestions.map(team => (
                                <div
                                    key={team.team_id}
                                    className="suggestion-item"
                                    onClick={() => selectTeam1(team)}
                                >
                                    <div className="team-name">{team.name}</div>
                                    <div className="team-meta">
                                        {team.conference} {team.rank_adj_em && `• #${team.rank_adj_em}`}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="search-box">
                    <label className="search-label">Team 2</label>
                    <input
                        type="text"
                        value={team2Query}
                        onChange={(e) => setTeam2Query(e.target.value)}
                        placeholder="Search for a team..."
                    />
                    {team2Suggestions.length > 0 && (
                        <div className="suggestions">
                            {team2Suggestions.map(team => (
                                <div
                                    key={team.team_id}
                                    className="suggestion-item"
                                    onClick={() => selectTeam2(team)}
                                >
                                    <div className="team-name">{team.name}</div>
                                    <div className="team-meta">
                                        {team.conference} {team.rank_adj_em && `• #${team.rank_adj_em}`}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {loading && (
                <div className="loading">
                    <div className="spinner"></div>
                </div>
            )}

            {!loading && team1Data && team2Data ? (
                <div className="comparison-grid">
                    <TeamCard data={team1Data} />
                    <TeamCard data={team2Data} />
                </div>
            ) : !loading && (
                <div className="empty-state">
                    <div className="empty-state-icon">🏀</div>
                    <p>Select two teams to compare their KenPom metrics</p>
                </div>
            )}

            {status && (
                <div className="status-bar">
                    ✓ Database online • {status.teams_count} teams • Last updated: {status.last_update ? new Date(status.last_update).toLocaleString() : 'Never'}
                </div>
            )}
        </div>
    );
}

function TeamCard({ data }) {
    const { team, ratings, four_factors, resume } = data;

    if (!team || !ratings) {
        return (
            <div className="team-card">
                <div className="card-content">
                    <p>No data available</p>
                </div>
            </div>
        );
    }

    // Use team colors if available
    const primaryColor = team.primary_color || '#4A9EFF';
    const secondaryColor = team.secondary_color || '#FFFFFF';

    return (
        <div className="team-card" style={{
            borderColor: primaryColor + '40' // 40 = 25% opacity in hex
        }}>
            <div className="team-color-accent" style={{
                background: `linear-gradient(90deg, ${primaryColor} 0%, ${secondaryColor} 100%)`
            }}></div>
            <div className="card-content">
                <div className="team-header">
                    {team.logo_url && (
                        <div className="team-logo-container">
                            <img src={team.logo_url} alt={team.name} className="team-logo" />
                        </div>
                    )}
                    <div className="team-info-container">
                        <h2 className="team-title" style={{color: primaryColor}}>{team.name}</h2>
                        <div className="team-info">
                            {team.conference} • {team.coach}<br />
                            <span className="record">{ratings.wins}-{ratings.losses}</span>
                        </div>
                    </div>
                </div>

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

                {four_factors && (
                    <div className="metrics-section">
                        <h3 className="section-title">Four Factors</h3>
                        <div style={{marginBottom: '1.5rem'}}>
                            <div style={{fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.5px'}}>Offense</div>
                            <div className="metric-row">
                                <span className="metric-label">eFG%</span>
                                <span className="metric-value">
                                    {four_factors.efg_pct?.toFixed(1)}%
                                    <span className="rank">#{four_factors.rank_efg_pct}</span>
                                </span>
                            </div>
                            <div className="metric-row">
                                <span className="metric-label">Turnover %</span>
                                <span className="metric-value">
                                    {four_factors.to_pct?.toFixed(1)}%
                                    <span className="rank">#{four_factors.rank_to_pct}</span>
                                </span>
                            </div>
                            <div className="metric-row">
                                <span className="metric-label">Off. Reb. %</span>
                                <span className="metric-value">
                                    {four_factors.or_pct?.toFixed(1)}%
                                    <span className="rank">#{four_factors.rank_or_pct}</span>
                                </span>
                            </div>
                            <div className="metric-row">
                                <span className="metric-label">FT Rate</span>
                                <span className="metric-value">
                                    {four_factors.ft_rate?.toFixed(1)}
                                    <span className="rank">#{four_factors.rank_ft_rate}</span>
                                </span>
                            </div>
                        </div>
                        <div>
                            <div style={{fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.5px'}}>Defense</div>
                            <div className="metric-row">
                                <span className="metric-label">Opp. eFG%</span>
                                <span className="metric-value">
                                    {four_factors.defg_pct?.toFixed(1)}%
                                    <span className="rank">#{four_factors.rank_defg_pct}</span>
                                </span>
                            </div>
                            <div className="metric-row">
                                <span className="metric-label">Opp. TO %</span>
                                <span className="metric-value">
                                    {four_factors.dto_pct?.toFixed(1)}%
                                    <span className="rank">#{four_factors.rank_dto_pct}</span>
                                </span>
                            </div>
                            <div className="metric-row">
                                <span className="metric-label">Def. Reb. %</span>
                                <span className="metric-value">
                                    {four_factors.dor_pct?.toFixed(1)}%
                                    <span className="rank">#{four_factors.rank_dor_pct}</span>
                                </span>
                            </div>
                            <div className="metric-row">
                                <span className="metric-label">Opp. FT Rate</span>
                                <span className="metric-value">
                                    {four_factors.dft_rate?.toFixed(1)}
                                    <span className="rank">#{four_factors.rank_dft_rate}</span>
                                </span>
                            </div>
                        </div>
                    </div>
                )}

                {resume && (
                    <div className="metrics-section">
                        <h3 className="section-title">Tournament Resume</h3>
                        <div className="metric-row">
                            <span className="metric-label">NET Ranking</span>
                            <span className="metric-value">
                                #{resume.net_rank || 'N/A'}
                            </span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Quadrant 1</span>
                            <span className="metric-value">
                                {resume.quad1_wins}-{resume.quad1_losses}
                            </span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Quadrant 2</span>
                            <span className="metric-value">
                                {resume.quad2_wins}-{resume.quad2_losses}
                            </span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Quadrant 3</span>
                            <span className="metric-value">
                                {resume.quad3_wins}-{resume.quad3_losses}
                            </span>
                        </div>
                        <div className="metric-row">
                            <span className="metric-label">Quadrant 4</span>
                            <span className="metric-value">
                                {resume.quad4_wins}-{resume.quad4_losses}
                            </span>
                        </div>
                        {resume.sor_rank && (
                            <div className="metric-row">
                                <span className="metric-label">Strength of Record</span>
                                <span className="metric-value">
                                    #{resume.sor_rank}
                                </span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

ReactDOM.render(<App />, document.getElementById('root'));