import streamlit as st
import pandas as pd
import requests
import time
import base64
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Kalshi Pro v8", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .market-card {
        background-color: #1e2130; border-radius: 10px; padding: 20px;
        margin-bottom: 15px; border: 1px solid #30364d;
    }
    .price-box { background: #2a2e3f; padding: 10px 20px; border-radius: 5px; text-align: center; min-width: 90px; }
    .yes-val { color: #00e676; font-size: 22px; font-weight: bold; }
    .no-val { color: #ff5252; font-size: 22px; font-weight: bold; }
    .ticker-label { color: #888; font-family: monospace; font-size: 11px; letter-spacing: 1px; }
    .category-tag { 
        background: #3e445e; color: #fff; padding: 2px 8px; 
        border-radius: 4px; font-size: 10px; text-transform: uppercase;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
HOST = "https://api.elections.kalshi.com"
BASE_PATH = "/trade-api/v2"

def sign_request(private_key_str, method, path, timestamp):
    try:
        private_key = serialization.load_pem_private_key(private_key_str.encode(), password=None)
        msg = f"{timestamp}{method}{path}"
        signature = private_key.sign(
            msg.encode("utf-8"), 
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), 
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode("utf-8")
    except Exception as e:
        st.error(f"Auth Error: {e}")
        return None

# --- 3. OPTIMIZED DATA FETCHING (PREVENTS API LIMIT HITS) ---
@st.cache_data(ttl=60) # Cache for 60s to avoid redundant API calls
def fetch_global_feed():
    path = f"{BASE_PATH}/events"
    try:
        key_id = st.secrets["KALSHI_KEY_ID"]
        priv_key = st.secrets["KALSHI_PRIVATE_KEY"]
    except:
        st.error("Missing KALSHI_KEY_ID or KALSHI_PRIVATE_KEY in Streamlit Secrets.")
        return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    
    headers = {
        "KALSHI-ACCESS-KEY": key_id, 
        "KALSHI-ACCESS-SIGNATURE": sig, 
        "KALSHI-ACCESS-TIMESTAMP": ts, 
        "Accept": "application/json"
    }
    
    # Fetch 200 events (The max allowed in one call to maximize data per hit)
    params = {"status": "open", "limit": 200, "with_nested_markets": True}
    
    try:
        response = requests.get(f"{HOST}{path}", headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("events", [])
        else:
            st.error(f"Kalshi API Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return []

# --- 4. MAIN UI & LOCAL FILTERING ---
def main():
    st.sidebar.title("⚡ Kalshi Pro v8")
    view_mode = st.sidebar.selectbox("Market Filter", ["All Markets", "Tennis", "Soccer", "Politics", "Economics", "Crypto"])
    min_liquidity = st.sidebar.slider("Min 'Yes' Bid (¢)", 0, 99, 1)

    if st.sidebar.button("Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.title(f"Live Terminal: {view_mode}")
    
    # 1. Fetch ALL data once
    raw_events = fetch_global_feed()
    
    if not raw_events:
        st.warning("No data returned from Kalshi. Check your API keys and internet connection.")
        return

    # 2. Filter LOCAL data based on selection (Does NOT hit API again)
    filtered_markets = []
    mode = view_mode.lower()

    for e in raw_events:
        title = e.get("title", "").lower()
        ticker = e.get("ticker", "").upper()
        cat = e.get("category", "").lower()
        
        is_match = False
        if mode == "all markets":
            is_match = True
        elif mode == "tennis":
            if "TENNIS" in ticker or any(x in title for x in ["atp", "wta", "itf", "tennis", "open"]):
                is_match = True
        elif mode == "soccer":
            if "SOC" in ticker or any(x in title for x in ["soccer", "premier league", "mls", "uefa"]):
                is_match = True
        elif mode == "politics":
            if cat == "politics" or any(x in title for x in ["election", "president", "trump", "biden"]):
                is_match = True
        elif mode == "economics":
            if cat == "economics" or any(x in title for x in ["fed", "inflation", "cpi", "rate"]):
                is_match = True
        elif mode == "crypto":
            if any(x in title or x in ticker for x in ["btc", "eth", "crypto", "bitcoin"]):
                is_match = True

        if is_match:
            for m in e.get("markets", []):
                m['parent_event_title'] = e.get('title')
                m['parent_category'] = e.get('category', 'General')
                filtered_markets.append(m)

    # 3. Apply secondary filters (Price/Liquidity)
    final_list = [m for m in filtered_markets if int(m.get('yes_bid', 0)) >= min_liquidity]

    if not final_list:
        st.info(f"No {view_mode} matches found with the current filters.")
    else:
        st.caption(f"Showing {len(final_list)} active contracts from {len(raw_events)} events scanned.")
        
        for m in final_list:
            yes_p = int(m.get('yes_bid', 0))
            no_p = int(m.get('no_bid', 0))
            
            st.markdown(f"""
                <div class="market-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="max-width: 70%;">
                            <div style="display:flex; gap:10px; align-items:center; margin-bottom:5px;">
                                <span class="ticker-label">{m.get('ticker')}</span>
                                <span class="category-tag">{m.get('parent_category')}</span>
                            </div>
                            <div style="font-size: 18px; font-weight: 500;">{m.get('parent_event_title')}</div>
                            <div style="color: #aaa; font-size: 14px; margin-top:4px;">{m.get('subtitle', m.get('title', ''))}</div>
                        </div>
                        <div style="display:flex; gap:12px;">
                            <div class="price-box">
                                <div style="font-size:10px; color:#888; margin-bottom:3px;">YES BID</div>
                                <div class="yes-val">{yes_p}¢</div>
                            </div>
                            <div class="price-box">
                                <div style="font-size:10px; color:#888; margin-bottom:3px;">NO BID</div>
                                <div class="no-val">{no_p}¢</div>
                            </div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
