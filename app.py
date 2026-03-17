import streamlit as st
import pandas as pd
import requests
import numpy as np

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="Tennis Edge: Kalshi Dashboard", layout="wide", page_icon="🎾")
st.title("🎾 Tennis Edge: Kalshi Event Exchange")

# --- 2. LOGIC: KALSHI API & CONVERSION ---
BASE_URL = "https://trading-api.kalshi.com"

def get_kalshi_token(email, password):
    """Authenticate and retrieve session token."""
    res = requests.post(f"{BASE_URL}/login", json={"email": email, "password": password})
    return res.json().get("token") if res.status_code == 200 else None

def odds_converter(price_cents):
    """Convert Kalshi binary price (1-99) to Decimal/American Odds."""
    if price_cents <= 0 or price_cents >= 100: return 0
    decimal = 100 / price_cents
    american = (100/price_cents - 1) * 100 if price_cents <= 50 else (-100 / (100/price_cents - 1))
    return round(decimal, 2), int(american)

# --- 3. SIDEBAR: CREDENTIALS & REQUIREMENTS ---
st.sidebar.header("🔐 Exchange Access")
email = st.sidebar.text_input("Kalshi Email")
password = st.sidebar.text_input("Kalshi Password", type="password")

if st.sidebar.button("Establish Session"):
    token = get_kalshi_token(email, password)
    if token:
        st.session_state['token'] = token
        st.sidebar.success("Session Active")
    else:
        st.sidebar.error("Auth Failed")

# --- 4. THE ANALYST DASHBOARD ---
if 'token' in st.session_state:
    st.subheader("Live Tennis Markets (ATP/WTA/ITF)")
    
    # Fetching Open Tennis Markets
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    res = requests.get(f"{BASE_URL}/markets?category=Tennis&status=open", headers=headers)
    
    if res.status_code == 200:
        markets = res.json().get("markets", [])
        if markets:
            analysis = []
            for m in markets:
                yes_price = m['yes_bid'] # Price in cents
                dec, am = odds_converter(yes_price)
                
                analysis.append({
                    "Match / Event": m['title'],
                    "Yes Price": f"${yes_price/100:.2f}",
                    "Implied Prob": f"{yes_price}%",
                    "Decimal Odds": dec,
                    "American Odds": f"{'+' if am > 0 else ''}{am}",
                    "Ticker": m['ticker']
                })
            
            df = pd.DataFrame(analysis)
            st.dataframe(df, use_container_width=True)
            
            # Analytical Logic: Market Arbitrage Check
            st.divider()
            st.subheader("💡 Analysis: Market Discrepancies")
            col1, col2 = st.columns(2)
            with col1:
                st.info("Check for 'Value': If your model says >60% and Kalshi price is <$0.55, it's a Buy.")
            with col2:
                st.warning("Note: Kalshi contracts settle at $1.00 (Win) or $0.00 (Loss).")
        else:
            st.write("No active tennis contracts currently listed.")
else:
    st.warning("👈 Please login to the exchange to retrieve live tennis data.")

# --- 5. BETTING LOGIC CALCULATOR ---
st.sidebar.divider()
st.sidebar.header("🧮 Edge Calculator")
model_prob = st.sidebar.slider("Your Model Probability (%)", 1, 99, 60)
market_price = st.sidebar.number_input("Kalshi 'Yes' Price ($)", 0.01, 0.99, 0.50)

expected_value = (model_prob/100 * (1 - market_price)) - ((1 - model_prob/100) * market_price)
st.sidebar.metric("Expected Value (EV)", f"{expected_value*100:.1f}%")
