import streamlit as st
import pandas as pd
import requests
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Kalshi Pro v9", page_icon="📈", layout="wide")

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
    .ticker-label { color: #888; font-family: monospace; font-size: 11px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION (FIXED SIGNING) ---
HOST = "https://api.elections.kalshi.com"
BASE_PATH = "/trade-api/v2"

def sign_request(private_key_str, method, path, timestamp):
    """
    IMPORTANT: The path must include /trade-api/v2 but exclude query params.
    Example: sign_request(key, "GET", "/trade-api/v2/events", ts)
    """
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
        st.error(f"Signature Generation Failed: {e}")
        return None

# --- 3. DATA FETCHING ---
@st.cache_data(ttl=60)
def fetch_global_feed():
    endpoint = "/events"
    full_path = f"{BASE_PATH}{endpoint}" # This is what we sign
    
    try:
        key_id = st.secrets["KALSHI_KEY_ID"]
        priv_key = st.secrets["KALSHI_PRIVATE_KEY"]
    except:
        st.error("Missing Secrets!")
        return []

    ts = str(int(time.time() * 1000))
    # SIGN ONLY THE PATH: /trade-api/v2/events
    sig = sign_request(priv_key, "GET", full_path, ts)
    
    headers = {
        "KALSHI-ACCESS-KEY": key_id, 
        "KALSHI-ACCESS-SIGNATURE": sig, 
        "KALSHI-ACCESS-TIMESTAMP": ts, 
        "Accept": "application/json"
    }
    
    params = {"status": "open", "limit": 200, "with_nested_markets": True}
    
    try:
        # Request uses HOST + FULL_PATH
        response = requests.get(f"{HOST}{full_path}", headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("events", [])
        else:
            # THIS WILL TELL YOU EXACTLY WHY IT'S EMPTY
            st.error(f"API Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return []

# --- 4. MAIN UI ---
def main():
    st.sidebar.title("⚡ Kalshi Pro v9")
    view_mode = st.sidebar.selectbox("Market Filter", ["All Markets", "Tennis", "Soccer", "Politics", "Crypto"])
    min_liq = st.sidebar.slider("Min 'Yes' Bid (¢)", 0, 99, 0)

    if st.sidebar.button("Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.title(f"Live Terminal: {view_mode}")
    
    raw_events = fetch_global_feed()
    
    if not raw_events:
        return # Error already shown in fetch function

    filtered_markets = []
    mode = view_mode.lower()

    for e in raw_events:
        title = e.get("title", "").lower()
        ticker = e.get("ticker", "").upper()
        
        is_match = False
        if mode == "all markets": is_match = True
        elif mode == "tennis": is_match = "TENNIS" in ticker or "tennis" in title
        elif mode == "soccer": is_match = "SOC" in ticker or "soccer" in title
        elif mode == "politics": is_match = e.get("category") == "Politics" or "election" in title
        elif mode == "crypto": is_match = any(x in title or x in ticker for x in ["btc", "eth", "crypto", "bitcoin"])

        if is_match:
            for m in e.get("markets", []):
                m['parent_title'] = e.get('title')
                filtered_markets.append(m)

    final_list = [m for m in filtered_markets if int(m.get('yes_bid', 0)) >= min_liq]

    if not final_list:
        st.info(f"No {view_mode} matches found. Check the error box above if one appeared.")
    else:
        for m in final_list:
            st.markdown(f"""
                <div class="market-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div class="ticker-label">{m.get('ticker')}</div>
                            <div style="font-size: 18px;">{m.get('parent_title')}</div>
                            <div style="color: #aaa; font-size: 14px;">{m.get('subtitle', m.get('title', ''))}</div>
                        </div>
                        <div style="display:flex; gap:12px;">
                            <div class="price-box">
                                <div class="yes-val">{int(m.get('yes_bid', 0))}¢</div>
                                <div style="font-size:10px; color:#888;">YES</div>
                            </div>
                            <div class="price-box">
                                <div class="no-val">{int(m.get('no_bid', 0))}¢</div>
                                <div style="font-size:10px; color:#888;">NO</div>
                            </div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
