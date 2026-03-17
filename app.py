import streamlit as st
import pandas as pd
import requests
import time
import base64
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Kalshi Pro v24", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .card {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 15px; margin-bottom: 10px;
    }
    .price-box { background: #26293b; padding: 10px; border-radius: 4px; text-align: center; min-width: 85px; border: 1px solid #3e445e; }
    .yes-txt { color: #3fb950; font-size: 19px; font-weight: bold; }
    .no-txt { color: #f85149; font-size: 19px; font-weight: bold; }
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

# --- 3. DATA FETCHING (SCANNING 1000+ EVENTS) ---
@st.cache_data(ttl=30)
def fetch_verified_events():
    path = f"{BASE_PATH}/events"
    try:
        key_id, priv_key = st.secrets["KALSHI_KEY_ID"], st.secrets["KALSHI_PRIVATE_KEY"]
    except: return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    headers = {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": ts, "Accept": "application/json"}
    
    all_events = []
    cursor = None
    for _ in range(10): # Deep scan to ensure sports matches are caught
        params = {"status": "open", "limit": 100, "with_nested_markets": "true"}
        if cursor: params["cursor"] = cursor
        res = requests.get(f"{HOST}{path}", headers=headers, params=params)
        if res.status_code != 200: break
        data = res.json()
        all_events.extend(data.get("events", []))
        cursor = data.get("cursor")
        if not cursor: break
    return all_events

# --- 4. MAIN UI ---
def main():
    st.sidebar.title("⚡ Monitor v24")
    view = st.sidebar.selectbox("Filter", ["All", "Tennis (Next 24h)", "Soccer (Next 24h)", "Politics", "Economics"])
    
    events = fetch_verified_events()
    now = datetime.now(timezone.utc)
    one_day_out = now + timedelta(hours=24)
    
    filtered = []
    for e in events:
        t, tick = e.get("title", "").lower(), e.get("ticker", "").upper()
        raw_cat = e.get("category", "").lower()
        
        # Safe Date Parsing
        raw_time = e.get("strike_date") or e.get("close_time")
        close_dt = None
        if raw_time:
            try: close_dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            except: pass
            
        is_next_24h = close_dt and (now <= close_dt <= one_day_out)
        
        # Greedy Match Logic
        is_tennis = any(x in tick for x in ["TENNIS", "WTA", "ATP"]) or "tennis" in t or raw_cat == "tennis"
        is_soccer = any(x in tick for x in ["SOC", "MLS", "UCL", "EPL", "SOCCER"]) or "soccer" in t or raw_cat == "soccer"
        
        match = False
        if view == "All": match = True
        elif view == "Tennis (Next 24h)": match = is_tennis and is_next_24h
        elif view == "Soccer (Next 24h)": match = is_soccer and is_next_24h
        elif view == "Politics": match = raw_cat == "politics" or "election" in t
        elif view == "Economics": match = raw_cat == "economics" or "fed" in t

        if match:
            for m in e.get("markets", []):
                y = int(float(m.get('yes_bid_dollars', 0)) * 100)
                n = int(float(m.get('no_bid_dollars', 0)) * 100)
                filtered.append({
                    "event": e.get('title'),
                    "market": m.get('title'),
                    "ticker": m.get('ticker'),
                    "y": f"{y}¢" if y > 0 else "N/A",
                    "n": f"{n}¢" if n > 0 else "N/A",
                    "cat": raw_cat.capitalize() or "General"
                })

    st.title(f"Feed: {view}")
    if not filtered:
        st.info(f"Total scanned: {len(events)}. No {view} matches. Check 'All' to confirm data flow.")
    else:
        for m in filtered:
            st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="max-width:70%;">
                            <span style="color:#58a6ff; font-family:monospace; font-size:11px;">{m['ticker']}</span>
                            <div style="font-size:17px; font-weight:600; margin:2px 0;">[{m['cat']}] {m['event']}</div>
                            <div style="color:#8b949e; font-size:14px;">{m['market']}</div>
                        </div>
                        <div style="display:flex; gap:10px;">
                            <div class="price-box"><span style="font-size:9px; color:#888;">YES</span><div class="yes-txt">{m['y']}</div></div>
                            <div class="price-box"><span style="font-size:9px; color:#888;">NO</span><div class="no-txt">{m['n']}</div></div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
