"""
National Champions Only Analysis

Analyzes just the teams that won it all to find the true
"championship DNA" profile without Cinderella outliers.

Run from project root:
    python scrapers/analyze_champions.py
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE = PROJECT_ROOT / 'database' / 'kenpom.db'

# National Champions 2002-2025 (team_name must match KenPom exactly)
NATIONAL_CHAMPIONS = {
    2002: ("Maryland", 1),
    2003: ("Syracuse", 3),
    2004: ("Connecticut", 2),
    2005: ("North Carolina", 1),
    2006: ("Florida", 3),
    2007: ("Florida", 1),
    2008: ("Kansas", 1),
    2009: ("North Carolina", 1),
    2010: ("Duke", 1),
    2011: ("Connecticut", 3),
    2012: ("Kentucky", 1),
    2013: ("Louisville", 1),
    2014: ("Connecticut", 7),
    2015: ("Duke", 1),
    2016: ("Villanova", 2),
    2017: ("North Carolina", 1),
    2018: ("Villanova", 1),
    2019: ("Virginia", 1),
    # 2020: Cancelled
    2021: ("Baylor", 1),
    2022: ("Kansas", 1),
    2023: ("Connecticut", 4),
    2024: ("Connecticut", 1),
    2025: ("Florida", 1),  # Current champion
}

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def analyze_champions():
    print("="*70)
    print("NATIONAL CHAMPIONS ANALYSIS (2002-2025)")
    print("="*70)
    print(f"\nSample size: {len(NATIONAL_CHAMPIONS)} champions\n")
    
    db = get_db()
    cursor = db.cursor()
    
    # Metrics to analyze
    metrics = [
        ('rank_adj_oe', 'Adjusted OE'),
        ('rank_adj_de', 'Adjusted DE'),
        ('rank_adj_em', 'Adjusted EM'),
        ('rank_efg_pct', 'Offensive eFG%'),
        ('rank_defg_pct', 'Defensive eFG%'),
        ('rank_to_pct', 'Turnover % (Off)'),
        ('rank_dto_pct', 'Forced TO %'),
        ('rank_or_pct', 'Offensive Reb %'),
        ('rank_dor_pct', 'Defensive Reb %'),
        ('rank_ft_rate', 'FT Rate (Off)'),
        ('rank_dft_rate', 'Opp FT Rate (Def)'),
    ]
    
    results = {}
    
    for metric_col, metric_name in metrics:
        ranks = []
        teams_data = []
        
        for year, (team_name, seed) in NATIONAL_CHAMPIONS.items():
            if year == 2020:
                continue
            
            row = cursor.execute(f'''
                SELECT {metric_col}, team_name, season 
                FROM historical_four_factors
                WHERE season = ? AND team_name = ?
            ''', (year, team_name)).fetchone()
            
            if row and row[metric_col]:
                ranks.append(row[metric_col])
                teams_data.append((year, team_name, row[metric_col]))
        
        if not ranks:
            print(f"\n⚠ {metric_name}: No data found")
            continue
        
        ranks.sort()
        n = len(ranks)
        
        avg_rank = sum(ranks) / n
        median_rank = ranks[n // 2] if n % 2 == 1 else (ranks[n//2 - 1] + ranks[n//2]) / 2
        min_rank = min(ranks)
        max_rank = max(ranks)
        
        # Percentile analysis
        pct_top_10 = sum(1 for r in ranks if r <= 10) / n * 100
        pct_top_25 = sum(1 for r in ranks if r <= 25) / n * 100
        pct_top_50 = sum(1 for r in ranks if r <= 50) / n * 100
        pct_top_75 = sum(1 for r in ranks if r <= 75) / n * 100
        pct_top_100 = sum(1 for r in ranks if r <= 100) / n * 100
        
        results[metric_col] = {
            'name': metric_name,
            'median': median_rank,
            'avg': avg_rank,
            'min': min_rank,
            'max': max_rank,
            'pct_top_10': pct_top_10,
            'pct_top_25': pct_top_25,
            'pct_top_50': pct_top_50,
            'pct_top_75': pct_top_75,
            'pct_top_100': pct_top_100,
            'ranks': ranks,
            'teams': teams_data,
        }
        
        print(f"\n{'─'*70}")
        print(f"📊 {metric_name}")
        print(f"{'─'*70}")
        print(f"   Median: {median_rank:.0f}")
        print(f"   Average: {avg_rank:.1f}")
        print(f"   Range: {min_rank} - {max_rank}")
        print(f"   ")
        print(f"   % in Top 10:  {pct_top_10:5.1f}%  {'🔥' if pct_top_10 >= 50 else ''}")
        print(f"   % in Top 25:  {pct_top_25:5.1f}%  {'🔥' if pct_top_25 >= 75 else ''}")
        print(f"   % in Top 50:  {pct_top_50:5.1f}%  {'✓' if pct_top_50 >= 75 else ''}")
        print(f"   % in Top 75:  {pct_top_75:5.1f}%")
        print(f"   % in Top 100: {pct_top_100:5.1f}%")
        
        # Show outliers (worst ranks)
        worst_teams = sorted(teams_data, key=lambda x: x[2], reverse=True)[:3]
        if max_rank > 50:
            print(f"\n   Outliers (worst ranks):")
            for year, team, rank in worst_teams:
                print(f"      {year} {team}: #{rank}")
    
    db.close()
    
    # Summary table
    print("\n" + "="*70)
    print("SUMMARY: CHAMPION DNA PROFILE")
    print("="*70)
    print(f"\n{'Metric':<22} {'Median':>8} {'Top 10%':>10} {'Top 25%':>10} {'Top 50%':>10}")
    print("─"*70)
    
    # Sort by how predictive (% in top 25)
    sorted_metrics = sorted(results.items(), key=lambda x: x[1]['pct_top_25'], reverse=True)
    
    for metric_col, data in sorted_metrics:
        indicator = ""
        if data['pct_top_25'] >= 75:
            indicator = "🔥 CRITICAL"
        elif data['pct_top_50'] >= 75:
            indicator = "✓ Important"
        else:
            indicator = "○ Weak"
        
        print(f"{data['name']:<22} {data['median']:>8.0f} {data['pct_top_10']:>9.0f}% {data['pct_top_25']:>9.0f}% {data['pct_top_50']:>9.0f}%  {indicator}")
    
    # Recommended thresholds
    print("\n" + "="*70)
    print("RECOMMENDED THRESHOLDS FOR CHAMPIONSHIP CONTENDER")
    print("="*70)
    
    print("\n🔥 CRITICAL (Must meet to be Elite Contender):")
    for metric_col, data in sorted_metrics:
        if data['pct_top_25'] >= 70:
            # Use a threshold that ~85% of champs meet
            threshold = int(sorted(data['ranks'])[int(len(data['ranks']) * 0.85)])
            print(f"   {data['name']}: Top {threshold} ({data['pct_top_25']:.0f}% of champs in top 25)")
    
    print("\n✓ IMPORTANT (Helps but not required):")
    for metric_col, data in sorted_metrics:
        if 50 <= data['pct_top_25'] < 70:
            threshold = int(sorted(data['ranks'])[int(len(data['ranks']) * 0.85)])
            print(f"   {data['name']}: Top {threshold}")
    
    print("\n○ WEAK PREDICTORS (Don't use for tiering):")
    for metric_col, data in sorted_metrics:
        if data['pct_top_25'] < 50:
            print(f"   {data['name']} (only {data['pct_top_25']:.0f}% of champs in top 25)")
    
    return results


if __name__ == '__main__':
    analyze_champions()
