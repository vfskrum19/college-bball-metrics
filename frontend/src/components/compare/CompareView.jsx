import { useState, useEffect } from 'react';
import TeamCard from './TeamCard';

function CompareView() {
    const [team1Query, setTeam1Query] = useState('');
    const [team2Query, setTeam2Query] = useState('');
    const [team1Suggestions, setTeam1Suggestions] = useState([]);
    const [team2Suggestions, setTeam2Suggestions] = useState([]);
    const [selectedTeam1, setSelectedTeam1] = useState(null);
    const [selectedTeam2, setSelectedTeam2] = useState(null);
    const [team1Data, setTeam1Data] = useState(null);
    const [team2Data, setTeam2Data] = useState(null);
    const [loading, setLoading] = useState(false);

    // Search for team 1
    useEffect(() => {
        if (team1Query.length < 2) {
            setTeam1Suggestions([]);
            return;
        }

        const timer = setTimeout(() => {
            fetch(`/api/search?q=${encodeURIComponent(team1Query)}`)
                .then(res => res.json())
                .then(data => setTeam1Suggestions(data))
                .catch(err => console.error('Search error:', err));
        }, 300);

        return () => clearTimeout(timer);
    }, [team1Query]);

    // Search for team 2
    useEffect(() => {
        if (team2Query.length < 2) {
            setTeam2Suggestions([]);
            return;
        }

        const timer = setTimeout(() => {
            fetch(`/api/search?q=${encodeURIComponent(team2Query)}`)
                .then(res => res.json())
                .then(data => setTeam2Suggestions(data))
                .catch(err => console.error('Search error:', err));
        }, 300);

        return () => clearTimeout(timer);
    }, [team2Query]);

    // Fetch comparison when both teams selected
    useEffect(() => {
        if (selectedTeam1 && selectedTeam2) {
            setLoading(true);
            fetch(`/api/compare?team1=${selectedTeam1.team_id}&team2=${selectedTeam2.team_id}`)
                .then(res => res.json())
                .then(data => {
                    setTeam1Data(data.team1);
                    setTeam2Data(data.team2);
                    setTeam1Query('');
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
        <div className="compare-view">
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
        </div>
    );
}

export default CompareView;
