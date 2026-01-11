#!/usr/bin/env python3
"""
Set up frontend folder structure
"""
import os
from pathlib import Path

def setup_frontend():
    print("="*70)
    print("SETTING UP FRONTEND STRUCTURE")
    print("="*70)
    print()
    
    # Create directories
    directories = [
        'frontend/static',
        'frontend/static/css',
        'frontend/static/js',
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {directory}/")
    
    # Create placeholder CSS
    css_content = """/* Court Vision Styles */
body {
    margin: 0;
    padding: 0;
    font-family: 'Source Sans 3', sans-serif;
    background: #0a0a0a;
    color: #ffffff;
}

#root {
    min-height: 100vh;
}

h1, h2, h3 {
    font-family: 'Archivo Black', sans-serif;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.loading {
    text-align: center;
    padding: 40px;
    font-size: 18px;
}

.error {
    color: #ff6b6b;
    text-align: center;
    padding: 40px;
}
"""
    
    with open('frontend/static/css/styles.css', 'w') as f:
        f.write(css_content)
    print("✓ Created frontend/static/css/styles.css")
    
    # Create placeholder JS
    js_content = """// Court Vision App
const { useState, useEffect } = React;

function App() {
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                setStatus(data);
                setLoading(false);
            })
            .catch(err => {
                console.error('Error fetching status:', err);
                setLoading(false);
            });
    }, []);

    if (loading) {
        return <div className="loading">Loading...</div>;
    }

    return (
        <div className="container">
            <h1>Court Vision</h1>
            <p>KenPom Team Comparison Tool</p>
            
            {status && (
                <div>
                    <p>Database Status: {status.status}</p>
                    <p>Teams: {status.teams_count}</p>
                    <p>Last Update: {status.last_update || 'N/A'}</p>
                </div>
            )}
            
            <p style={{marginTop: '40px', opacity: 0.7}}>
                Frontend is working! Start building your React components here.
            </p>
        </div>
    );
}

// Render the app
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
"""
    
    with open('frontend/static/js/app.js', 'w') as f:
        f.write(js_content)
    print("✓ Created frontend/static/js/app.js")
    
    print()
    print("="*70)
    print("FRONTEND SETUP COMPLETE!")
    print("="*70)
    print()
    print("File structure:")
    print("  frontend/")
    print("  ├── index.html")
    print("  └── static/")
    print("      ├── css/")
    print("      │   └── styles.css")
    print("      └── js/")
    print("          └── app.js")

if __name__ == '__main__':
    setup_frontend()
