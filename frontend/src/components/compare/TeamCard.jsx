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

    const primaryColor = team.primary_color || '#4A9EFF';
    const secondaryColor = team.secondary_color || '#FFFFFF';

    return (
        <div className="team-card" style={{
            borderColor: primaryColor + '40'
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
                            <div className="factor-label">Offense</div>
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
                            <div className="factor-label">Defense</div>
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

export default TeamCard;
