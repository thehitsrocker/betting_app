import streamlit as st
import pandas as pd
import requests
import time
import base64
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG ---
st.set_page_config(page_title="Kalshi Pro v23", page_icon="⚡", layout="wide")

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

# --- 3. REBUILT DATA FETCHING ---
@st.cache_data(ttl=30)
def fetch_verified_data():
    path = f"{BASE_PATH}/events"
    try:
        key_id, priv_key = st.secrets["KALSHI_KEY_ID"], st.secrets["KALSHI_PRIVATE_KEY"]
    except: return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    headers = {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": ts, "Accept": "application/json"}
    
    all_events = []
    cursor = None
    # Deep Scan: 10 pages (1000 events)
    for _ in range(10):
        params = {"status": "open", "limit": 100, "with_nested_markets": "true"}
        if cursor: params["cursor"] = cursor
        try:
            res = requests.get(f"{HOST}{path}", headers=headers, params=params)
            if res.status_code != 200: break
            data = res.json()
            all_events.extend(data.get("events", []))
            cursor = data.get("cursor")
            if not cursor: break
        except: break
    return all_events

# --- 4. MAIN TERMINAL LOGIC ---
def main():
    st.sidebar.title("⚡ Pro Monitor v23")
    # Sub-categories based on verified 2026 Ticker Prefixes
    view = st.sidebar.selectbox("Filter View", ["All", "Tennis (Next 24h)", "Soccer (Next 24h)", "Politics", "Economics", "Crypto"])
    
    events = fetch_verified_data()
    now = datetime.now(timezone.utc)
    one_day_out = now + timedelta(hours=24)
    
    filtered_output = []
    
    for e in events:
        # 1. Basic Metadata
        title = e.get("title", "").lower()
        ticker = e.get("ticker", "").upper()
        cat = e.get("category", "").lower()
        
        # 2. Time Parsing
        raw_close = e.get("strike_date") or e.get("close_time")
        close_dt = None
        if raw_close:
            try: close_dt = datetime.fromisoformat(raw_close.replace("Z", "+00:00"))
            except: pass
        
        is_next_24h = close_dt and (now <= close_dt <= one_day_out)
        
        # 3. Categorization Logic (Greedy)
        is_tennis = any(x in ticker for x in ["TENNIS", "WTA", "ATP"]) or "tennis" in title
        is_soccer = any(x in ticker for x in ["SOC", "MLS", "UCL", "PREMIER"]) or "soccer" in title
        is_politics = cat == "politics" or any(x in title for x in ["election", "president", "senate"])
        is_economics = cat == "economics" or any(x in title for x in ["fed", "cpi", "inflation", "gdp"])
        is_crypto = any(x in ticker for x in ["BTC", "ETH", "SOL", "CRYPTO"]) or "crypto" in title

        # Select match
        match = False
        if view == "All": match = True
        elif view == "Tennis (Next 24h)": match = is_tennis and is_next_24h
        elif view == "Soccer (Next 24h)": match = is_soccer and is_next_24h
        elif view == "Politics": match = is_politics
        elif view == "Economics": match = is_economics
        elif view == "Crypto": match = is_crypto

        if match:
            for m in e.get("markets", []):
                y = int(float(m.get('yes_bid_dollars', 0)) * 100)
                n = int(float(m.get('no_bid_dollars', 0)) * 100)
                filtered_output.append({
                    "event": e.get('title'),
                    "market": m.get('title'),
                    "ticker": m.get('ticker'),
                    "y": f"{y}¢" if y > 0 else "N/A",
                    "n": f"{n}¢" if n > 0 else "N/A",
                    "close": close_dt,
                    "cat_label": cat.capitalize() or "General"
                })

    st.title(f"Feed: {view}")
    if not filtered_output:
        st.info(f"Scanned {len(events)} events. No matches found for {view}. Try 'All' to confirm data flow.")
    else:
        # Sort by Time for 24h views
        if "24h" in view: filtered_output.sort(key=lambda x: x['close'] or datetime.max.replace(tzinfo=timezone.utc))
        
        for m in filtered_output:
            with st.container():
                st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="max-width:70%;">
                            <span style="color:#58a6ff; font-family:monospace; font-size:11px;">{m['ticker']}</span>
                            <div style="font-size:17px; font-weight:600; margin:2px 0;">[{m['cat_label']}] {m['event']}</div>
                            <div style="color:#8b949e; font-size:14px;">{m['market']}</div>
                        </div>
                        <div style="display:flex; gap:10px;">
                            <div class="price-box"><span style="font-size:9px; color:#888;">YES</span><div style="color:#3fb950; font-size:20px; font-weight:bold;">{m['y']}</div></div>
                            <div class="price-box"><span style="font-size:9px; color:#888;">NO</span><div style="color:#f85149; font-size:20px; font-weight:bold;">{m['n']}</div></div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
