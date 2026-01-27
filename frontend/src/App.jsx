import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import CompareView from './components/compare/CompareView';
import BracketVisualizer from './components/bracket/BracketVisualizer';
import MomentumTracker from './components/momentum/MomentumTracker';
import './global.css';

function App() {
    const [status, setStatus] = useState(null);

    useEffect(() => {
        fetch('/api/status')
            .then(res => res.json())
            .then(data => setStatus(data))
            .catch(err => console.error('Status error:', err));
    }, []);

    return (
        <BrowserRouter>
            <div className="app">
                <header>
                    <h1>Court Vision</h1>
                    <p className="subtitle">Metrics Driven Analysis Tool</p>
                    
                    <nav className="main-nav">
                        <NavLink to="/" end className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>
                            Compare
                        </NavLink>
                        <NavLink to="/bracket" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>
                            Bracket
                        </NavLink>
                        <NavLink to="/momentum" className={({isActive}) => isActive ? 'nav-link active' : 'nav-link'}>
                            🔥 Momentum
                        </NavLink>
                    </nav>
                </header>

                <main>
                    <Routes>
                        <Route path="/" element={<CompareView />} />
                        <Route path="/bracket" element={<BracketVisualizer />} />
                        <Route path="/momentum" element={<MomentumTracker />} />
                    </Routes>
                </main>

                {status && (
                    <footer className="status-bar">
                        ✓ Database online • {status.teams_count} teams • Last updated: {status.last_update ? new Date(status.last_update).toLocaleString() : 'Never'}
                    </footer>
                )}
            </div>
        </BrowserRouter>
    );
}

export default App;