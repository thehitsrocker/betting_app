import streamlit as st
import pandas as pd
import requests
import time
import base64
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG ---
st.set_page_config(page_title="Kalshi Pro v21", page_icon="🎾", layout="wide")

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

# --- 3. DATA FETCHING ---
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
    # Scan more pages to ensure we reach sports data
    for _ in range(10):
        params = {"status": "open", "limit": 200, "with_nested_markets": "true"}
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
    st.sidebar.title("🎾 Match Monitor v21")
    view = st.sidebar.selectbox("Filter", ["All", "Tennis Next 24h", "Soccer Next 24h", "Live Now"])
    
    all_events = fetch_deep_scan()
    now = datetime.now(timezone.utc)
    one_day_out = now + timedelta(hours=24)

    filtered = []
    for e in all_events:
        t, tick = e.get("title", "").lower(), e.get("ticker", "").upper()
        raw_close = e.get("close_time") or e.get("strike_date") # Fallback for some event types
        
        if not raw_close: continue
        try:
            close_ts = datetime.fromisoformat(raw_close.replace("Z", "+00:00"))
        except: continue
        
        is_next_24h = now <= close_ts <= one_day_out
        
        # Broaden match logic for sports
        is_tennis = any(x in tick for x in ["TENNIS", "WTA", "ATP"]) or "tennis" in t
        is_soccer = any(x in tick for x in ["SOC", "MLS", "UCL"]) or "soccer" in t
        
        match = False
        if view == "All": match = True
        elif view == "Tennis Next 24h": match = is_tennis and is_next_24h
        elif view == "Soccer Next 24h": match = is_soccer and is_next_24h
        elif view == "Live Now": match = is_next_24h

        if match:
            for m in e.get("markets", []):
                # Handle cents vs dollars
                y = int(float(m.get('yes_bid_dollars', 0)) * 100)
                n = int(float(m.get('no_bid_dollars', 0)) * 100)
                
                filtered.append({
                    "ticker": m.get('ticker'),
                    "event": e.get('title'),
                    "market": m.get('title'),
                    "y": f"{y}¢" if y > 0 else "N/A",
                    "n": f"{n}¢" if n > 0 else "N/A",
                    "close_ts": close_ts,
                    "category": e.get("category", "General")
                })

    st.title(f"Feed: {view}")
    if not filtered:
        st.info(f"No results found. Total scanned events: {len(all_events)}. Try selecting 'All' to check data flow.")
    else:
        st.write(f"Showing {len(filtered)} contracts.")
        for m in sorted(filtered, key=lambda x: x['close_ts']):
            st.write(f"**[{m['category']}] {m['event']}** - {m['market']} | YES: {m['y']} NO: {m['n']}")

if __name__ == "__main__":
    main()
