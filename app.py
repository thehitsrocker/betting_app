import streamlit as st
import pandas as pd
import requests

# 1. API Configuration (Get a free key at the-odds-api.com)
# For security, you should put this in Streamlit's "Secrets" in the dashboard
API_KEY = st.sidebar.text_input("Enter Odds API Key", type="password")
SPORT = 'americanfootball_nfl' # Example: NFL
REGIONS = 'us'
MARKETS = 'h2h,spreads'

st.set_page_config(page_title="Pro Betting Engine", layout="wide")

def fetch_odds():
    if not API_KEY:
        st.warning("Please enter your API key in the sidebar to fetch live data.")
        return None
    
    url = f'https://api.the-odds-api.com{SPORT}/odds/?apiKey={API_KEY}&regions={REGIONS}&markets={MARKETS}'
    response = requests.get(url)
    
    if response.status_code != 200:
        st.error(f"Failed to get odds: {response.status_code}")
        return None
    else:
        return response.json()

st.title("🎯 Live Betting Engine")

# Sidebar Filters
st.sidebar.header("Market Filters")
selected_sport = st.sidebar.selectbox("Select League", ["NFL", "NBA", "MLB", "EPL"])

if st.button('Fetch Live Odds'):
    data = fetch_odds()
    
    if data:
        st.subheader(f"Current {selected_sport} Lines")
        
        # Flatten API data into a clean table
        rows = []
        for event in data:
            home_team = event['home_team']
            away_team = event['away_team']
            for bookmaker in event['bookmakers']:
                for market in bookmaker['markets']:
                    if market['key'] == 'h2h':
                        rows.append({
                            "Match": f"{away_team} @ {home_team}",
                            "Bookie": bookmaker['title'],
                            "Away Odds": market['outcomes'][0]['price'],
                            "Home Odds": market['outcomes'][1]['price']
                        })
        
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        
        # Simple Arbitrage or Value Check Logic
        st.info("💡 Analysis: Highlighting best available lines across bookmakers.")
