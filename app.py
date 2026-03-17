import streamlit as st
import pandas as pd
import requests
import time
import base64
import re
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Kalshi Pro v6", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .market-row {
        background-color: #1e2130; border-radius: 8px; padding: 15px;
        margin-bottom: 10px; border: 1px solid #30364d;
    }
    .price-val { font-weight: bold; font-size: 18px; }
    .yes-color { color: #00e676; }
    .no-color { color: #ff5252; }
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
HOST = "https://api.elections.kalshi.com"
BASE_PATH = "/trade-api/v2"

def sign_request(private_key_str, method, path, timestamp):
    try:
        private_key = serialization.load_pem_private_key(private_key_str.encode(), password=None)
        msg = f"{timestamp}{method}{path}"
        signature = private_key.sign(msg.encode("utf-8"), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        return base64.b64encode(signature).decode("utf-8")
    except: return None

# --- 3. DATA FETCHING (STRICT LOGIC) ---
@st.cache_data(ttl=60)
def fetch_markets_v6(user_selection):
    path = f"{BASE_PATH}/events"
    try:
        key_id, priv_key = st.secrets["KALSHI_KEY_ID"], st.secrets["KALSHI_PRIVATE_KEY"]
    except: return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    headers = {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": ts, "Accept": "application/json"}
    
    all_events = []
    cursor = None
    for _ in range(5): # Scan up to 500 events
        params = {"status": "open", "limit": 100, "with_nested_markets": True}
        if cursor: params['cursor'] = cursor
        res = requests.get(f"{HOST}{path}", headers=headers, params=params)
        if res.status_code != 200: break
        data = res.json()
        all_events.extend(data.get("events", []))
        cursor = data.get("cursor")
        if not cursor: break

    # --- STRICT FILTERING ENGINE ---
    filtered = []
    sel = user_selection.lower()
    
    for e in all_events:
        title = e.get("title", "").lower()
        cat = e.get("category", "").lower()
        ticker = e.get("ticker", "").lower()
        
        is_match = False
        
        if sel == "tennis":
            # Match only if Category is Sports AND Title contains Tennis/ATP/WTA
            if "sports" in cat and any(x in title for x in ["tennis", "atp", "wta", "challenger"]):
                is_match = True
        elif sel == "soccer":
            if "sports" in cat and any(x in title for x in ["soccer", "fifa", "uefa", "mls", "premier"]):
                is_match = True
        elif sel == "politics":
            if "politics" in cat or any(x in title for x in ["election", "president", "trump", "biden"]):
                is_match = True
        elif sel == "economics":
            if "economics" in cat or any(x in title for x in ["fed ", "inflation", "cpi", "gdp", "recession"]):
                is_match = True
        elif sel == "crypto":
            if any(x in title or x in ticker for x in ["bitcoin", "btc", "eth", "crypto"]):
                is_match = True

        if is_match:
            for m in e.get("markets", []):
                m['event_title'] = e.get('title')
                filtered.append(m)
    return filtered

# --- 4. RENDERER ---
def parse_p(m, side):
    val = m.get(f"{side}_bid")
    if val is not None: return int(val)
    val_s = m.get(f"{side}_bid_dollars")
    try: return int(float(val_s) * 100) if val_s else 0
    except: return 0

def main():
    with st.sidebar:
        st.header("⚡ Kalshi Pro v6")
        cat = st.selectbox("Category", ["Tennis", "Soccer", "Politics", "Economics", "Crypto"])
        min_liq = st.slider("Min Price", 0, 99, 1)

    st.title(f"Strict Feed: {cat}")
    markets = fetch_markets_v6(cat)
    valid = [m for m in markets if parse_p(m, "yes") >= min_liq]

    if not valid:
        st.info(f"No strict matches for {cat}. Tennis/Soccer matches often appear closer to game time.")
    else:
        st.success(f"Verified {len(valid)} {cat} Contracts")
        for m in valid[:40]:
            with st.container():
                st.markdown(f"""
                <div class="market-row">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#aaa; font-size:12px;">{m.get('ticker')}</span>
                        <span style="color:#aaa; font-size:12px;">{m.get('close_time')[:10]}</span>
                    </div>
                    <div class="market-title">{m.get('event_title')}</div>
                    <div style="margin-top:10px; display:flex; gap:40px;">
                        <div><span style="font-size:10px; color:#888;">YES BID</span><br><span class="price-val yes-color">{parse_p(m, 'yes')}¢</span></div>
                        <div><span style="font-size:10px; color:#888;">NO BID</span><br><span class="price-val no-color">{parse_p(m, 'no')}¢</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
