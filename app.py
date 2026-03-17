import streamlit as st
import pandas as pd
import requests
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Kalshi Pro v14", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .card {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 18px; margin-bottom: 12px;
    }
    .price-box { background: #002d11; color: #3fb950; padding: 5px 12px; border-radius: 4px; font-weight: bold; font-size: 20px; }
    .liq-box { color: #8b949e; font-size: 12px; margin-top: 5px; }
    .meta { color: #8b949e; font-family: monospace; font-size: 11px; }
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
    except: return None

# --- 3. DATA FETCHING (DEEP SCAN) ---
@st.cache_data(ttl=60)
def fetch_global_verified_feed():
    path = f"{BASE_PATH}/events"
    try:
        key_id, priv_key = st.secrets["KALSHI_KEY_ID"], st.secrets["KALSHI_PRIVATE_KEY"]
    except: return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    headers = {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": ts, "Accept": "application/json"}
    
    results = []
    cursor = None
    # Scan 5 pages (500 events) to find specific matches buried under politics
    for _ in range(5):
        params = {"status": "open", "limit": 100, "with_nested_markets": True}
        if cursor: params["cursor"] = cursor
        res = requests.get(f"{HOST}{path}", headers=headers, params=params)
        if res.status_code != 200: break
        data = res.json()
        results.extend(data.get("events", []))
        cursor = data.get("cursor")
        if not cursor: break
    return results

# --- 4. MAIN UI ---
def main():
    st.sidebar.title("📊 Pro Terminal v14")
    view = st.sidebar.selectbox("Market Tier", ["Tennis", "Soccer", "Politics", "Crypto", "All Open"])
    min_liq = st.sidebar.number_input("Min Liquidity ($)", 0, 1000000, 0)
    
    raw_data = fetch_global_verified_feed()
    st.sidebar.caption(f"Backend Scanned: {len(raw_data)} Events")

    filtered = []
    for e in raw_data:
        e_title, e_ticker = e.get("title", "").lower(), e.get("ticker", "").upper()
        
        match = False
        if view == "All Open": match = True
        elif view == "Tennis": match = any(x in e_ticker for x in ["TENNIS", "KXWTA", "KXATP"]) or "tennis" in e_title
        elif view == "Soccer": match = any(x in e_ticker for x in ["SOC", "KXUCL", "KXMLS"]) or "soccer" in e_title
        elif view == "Politics": match = e.get("category") == "Politics" or "election" in e_title
        elif view == "Crypto": match = any(x in e_ticker for x in ["BTC", "ETH", "SOL", "DOGE"]) or "crypto" in e_title

        if match:
            for m in e.get("markets", []):
                liq = m.get('liquidity_dollars', 0)
                if liq >= min_liq:
                    m['y_val'] = int(float(m.get('yes_bid_dollars', 0)) * 100)
                    m['n_val'] = int(float(m.get('no_bid_dollars', 0)) * 100)
                    m['liq_val'] = f"{int(liq):,}"
                    m['event_name'] = e.get('title')
                    filtered.append(m)

    st.title(f"Live {view} Feed")
    if not filtered:
        st.info(f"No {view} matches found with ${min_liq}+ liquidity.")
    else:
        for m in filtered:
            st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="max-width:70%;">
                            <div class="meta">{m.get('ticker')}</div>
                            <div style="font-size:18px; margin:4px 0;">{m['event_name']}</div>
                            <div style="color:#8b949e; font-size:14px;">{m.get('title')}</div>
                            <div class="liq-box">Liquidity: ${m['liq_val']}</div>
                        </div>
                        <div style="display:flex; gap:10px;">
                            <div class="price-box">{m['y_val']}¢</div>
                            <div style="background:#2d0001; color:#f85149; padding:5px 12px; border-radius:4px; font-weight:bold; font-size:20px;">{m['n_val']}¢</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
