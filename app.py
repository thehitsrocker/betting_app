import streamlit as st
import pandas as pd
import requests
import time
import base64
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Kalshi Pro v20", page_icon="🎾", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .card {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 15px; margin-bottom: 10px;
    }
    .status-tag {
        font-weight: bold; font-size: 10px; padding: 2px 8px; 
        border-radius: 4px; text-transform: uppercase; margin-bottom: 8px; display: inline-block;
    }
    .live-tag { color: #ff3e3e; border: 1px solid #ff3e3e; background: #2d0001; }
    .upcoming-tag { color: #58a6ff; border: 1px solid #58a6ff; background: #00152d; }
    .price-box { background: #26293b; padding: 10px; border-radius: 4px; text-align: center; min-width: 85px; border: 1px solid #3e445e; }
    .yes-val { color: #3fb950; font-size: 20px; font-weight: bold; }
    .no-val { color: #f85149; font-size: 20px; font-weight: bold; }
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
@st.cache_data(ttl=30)
def fetch_deep_scan():
    path = f"{BASE_PATH}/events"
    try:
        key_id, priv_key = st.secrets["KALSHI_KEY_ID"], st.secrets["KALSHI_PRIVATE_KEY"]
    except: return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    headers = {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": ts, "Accept": "application/json"}
    
    results = []
    cursor = None
    for _ in range(8):
        params = {"status": "open", "limit": 100, "with_nested_markets": True}
        if cursor: params["cursor"] = cursor
        try:
            res = requests.get(f"{HOST}{path}", headers=headers, params=params)
            if res.status_code != 200: break
            data = res.json()
            results.extend(data.get("events", []))
            cursor = data.get("cursor")
            if not cursor: break
        except: break
    return results

# --- 4. MAIN UI ---
def main():
    st.sidebar.title("🎾 Match Monitor v20")
    view = st.sidebar.selectbox("Filter", ["Tennis Next 24h", "Soccer Next 24h", "Live Now", "All"])
    
    all_events = fetch_deep_scan()
    now = datetime.now(timezone.utc)
    one_day_out = now + timedelta(hours=24)

    filtered = []
    for e in all_events:
        t, tick = e.get("title", "").lower(), e.get("ticker", "").upper()
        
        # --- SAFE DATE PARSING ---
        raw_close = e.get("close_time")
        if not raw_close: continue # Skip if no time data
        
        try:
            close_ts = datetime.fromisoformat(raw_close.replace("Z", "+00:00"))
        except: continue
        
        is_next_24h = now <= close_ts <= one_day_out
        
        match = False
        if view == "Tennis Next 24h":
            match = (any(x in tick for x in ["TENNIS", "KXWTA", "KXATP"]) or "tennis" in t) and is_next_24h
        elif view == "Soccer Next 24h":
            match = (any(x in tick for x in ["SOC", "KXMLS", "KXUCL"]) or "soccer" in t) and is_next_24h
        elif view == "Live Now":
            match = is_next_24h
        elif view == "All":
            match = True

        if match:
            for m in e.get("markets", []):
                y = int(float(m.get('yes_bid_dollars', 0)) * 100)
                n = int(float(m.get('no_bid_dollars', 0)) * 100)
                
                filtered.append({
                    "ticker": m.get('ticker'),
                    "event": e.get('title'),
                    "market": m.get('title'),
                    "y": f"{y}¢" if y > 0 else "N/A",
                    "n": f"{n}¢" if n > 0 else "N/A",
                    "close_ts": close_ts
                })

    st.title(f"Feed: {view}")
    if not filtered:
        st.info(f"No matches found for {view}. Ensure your scan limit is high enough to reach these events.")
    else:
        # Sort matches by start time (closest first)
        sorted_list = sorted(filtered, key=lambda x: x['close_ts'])
        
        for m in sorted_list:
            time_diff = m['close_ts'] - now
            h, m_rem = divmod(int(time_diff.total_seconds()), 3600)
            m_rem //= 60
            
            st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="max-width:75%;">
                            <div class="status-tag { 'live-tag' if h < 1 else 'upcoming-tag' }">
                                { 'LIVE' if h < 1 else 'UPCOMING' } - {h}h {m_rem}m left
                            </div>
                            <div style="color:#58a6ff; font-family:monospace; font-size:11px;">{m['ticker']}</div>
                            <div style="font-size:18px; font-weight:600; margin:2px 0;">{m['event']}</div>
                            <div style="color:#8b949e; font-size:14px;">{m['market']}</div>
                        </div>
                        <div style="display:flex; gap:12px;">
                            <div class="price-box"><span style="font-size:9px; color:#888;">YES</span><div class="yes-val">{m['y']}</div></div>
                            <div class="price-box"><span style="font-size:9px; color:#888;">NO</span><div class="no-val">{m['n']}</div></div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
