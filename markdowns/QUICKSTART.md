# Quick Start Guide

Get your KenPom comparison tool running in 5 minutes!

## Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 2: Add Your API Key
Open `fetch_data.py` and replace:
```python
KENPOM_API_KEY = "your_actual_api_key_here"
```

## Step 3: Sync Data
```bash
python fetch_data.py
```
Wait 30-60 seconds for initial data sync.

## Step 4: Start Backend
```bash
python app.py
```
Keep this terminal open.

## Step 5: Open Frontend
Open `index.html` in your browser.

## You're Done! 🎉
- Search for two teams
- Click suggestions to select
- View side-by-side comparison

## Daily Updates
Run once per day during season:
```bash
python fetch_data.py
```

## Need Help?
See README.md for detailed documentation.
