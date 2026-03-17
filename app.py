import streamlit as st
import pandas as pd
import requests
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CORE CONFIG ---
st.set_page_config(page_title="Kalshi Pro v12", page_icon="🏦", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .card {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 6px; padding: 16px; margin-bottom: 12px;
    }
    .yes-box { color: #3fb950; font-size: 22px; font-weight: bold; background: #002d11; padding: 5px 15px; border-radius: 4px; }
    .no-box { color: #f85149; font-size: 22px; font-weight: bold; background: #2d0001; padding: 5px 15px; border-radius: 4px; }
    .meta { color: #8b949e; font-family: monospace; font-size: 11px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SIGNING LOGIC (STRICT) ---
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
    except: return None

# --- 3. BACKEND DATA PULL (PAGINATED) ---
@st.cache_data(ttl=60)
def fetch_verified_feed():
    path = f"{BASE_PATH}/events"
    try:
        key_id, priv_key = st.secrets["KALSHI_KEY_ID"], st.secrets["KALSHI_PRIVATE_KEY"]
    except: return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    headers = {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": ts, "Accept": "application/json"}
    
    # We pull 3 pages (300 events) to ensure we hit the sports tier
    results = []
    cursor = None
    for _ in range(3):
        params = {"status": "open", "limit": 100, "with_nested_markets": True}
        if cursor: params["cursor"] = cursor
        res = requests.get(f"{HOST}{path}", headers=headers, params=params)
        if res.status_code != 200: break
        data = res.json()
        results.extend(data.get("events", []))
        cursor = data.get("cursor")
        if not cursor: break
    return results

# --- 4. DATA RENDERING ---
def main():
    st.sidebar.title("🏦 Backend View")
    view = st.sidebar.selectbox("Market Tier", ["Tennis", "Soccer", "Politics", "Crypto", "All Open"])
    
    raw_data = fetch_verified_feed()
    st.sidebar.caption(f"Backend Scanned: {len(raw_data)} Events")

    filtered = []
    for e in raw_data:
        # Backend matching logic
        e_title = e.get("title", "").lower()
        e_ticker = e.get("ticker", "").upper()
        
        match = False
        if view == "All Open": match = True
        elif view == "Tennis": match = e_ticker.startswith("TENNIS") or "tennis" in e_title
        elif view == "Soccer": match = e_ticker.startswith("SOC") or "soccer" in e_title
        elif view == "Politics": match = e.get("category") == "Politics" or "election" in e_title
        elif view == "Crypto": match = "KXBTC" in e_ticker or "crypto" in e_title

        if match:
            for m in e.get("markets", []):
                # Convert string dollars to integer cents
                y_raw = m.get('yes_bid_dollars', '0')
                n_raw = m.get('no_bid_dollars', '0')
                m['y_val'] = int(float(y_raw) * 100)
                m['n_val'] = int(float(n_raw) * 100)
                m['event_name'] = e.get('title')
                filtered.append(m)

    if not filtered:
        st.info(f"No active {view} markets. Check back during live match hours.")
    else:
        st.success(f"Matched {len(filtered)} Contracts")
        for m in filtered:
            st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between;">
                        <div style="max-width:70%;">
                            <div class="meta">{m.get('ticker')}</div>
                            <div style="font-size:18px; margin:4px 0;">{m['event_name']}</div>
                            <div style="color:#8b949e; font-size:14px;">{m.get('title')}</div>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center;">
                            <div class="yes-box">{m['y_val']}¢</div>
                            <div class="no-box">{m['n_val']}¢</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
