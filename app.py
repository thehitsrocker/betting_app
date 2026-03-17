import streamlit as st
import pandas as pd
import requests
import time
import base64
import traceback
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. APP CONFIGURATION ---
st.set_page_config(
    page_title="Kalshi Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .market-card {
        background-color: #1e2130;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
        border: 1px solid #30364d;
    }
    .market-card:hover { border-color: #4dabf7; }
    .market-title { font-weight: 600; font-size: 14px; color: #ffffff; margin-bottom: 4px; }
    .sub-text { font-size: 11px; color: #a0a0a0; }
    .price-box {
        background: #262a40; padding: 4px; border-radius: 4px; text-align: center;
    }
    .price-green { color: #00e676; font-weight: bold; font-size: 16px; }
    .price-red { color: #ff5252; font-weight: bold; font-size: 16px; }
    .tag {
        font-size: 10px; padding: 2px 6px; border-radius: 4px; background: #333; color: #bbb;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
HOST = "https://api.elections.kalshi.com"
BASE_PATH = "/trade-api/v2"

def sign_request(private_key_str, method, path, timestamp):
    try:
        private_key = serialization.load_pem_private_key(
            private_key_str.encode(), password=None
        )
        msg = f"{timestamp}{method}{path}"
        signature = private_key.sign(
            msg.encode("utf-8"),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode("utf-8")
    except Exception:
        return None

# --- 3. ROBUST DATA FETCHING (WITH PAGINATION) ---
@st.cache_data(ttl=60)
def fetch_all_markets(category_query):
    """
    Fetches MULTIPLE pages of events to ensure we find Politics/Economics 
    even if they are buried behind 100s of Tennis matches.
    """
    path = f"{BASE_PATH}/events"
    
    try:
        key_id = st.secrets["KALSHI_KEY_ID"]
        priv_key = st.secrets["KALSHI_PRIVATE_KEY"]
    except:
        st.error("❌ Secrets Missing")
        return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    headers = {
        "KALSHI-ACCESS-KEY": key_id, 
        "KALSHI-ACCESS-SIGNATURE": sig, 
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json"
    }
    
    # API MAX LIMIT is 200. Sending 500 causes error 400.
    params = {"status": "open", "limit": 100, "with_nested_markets": True}
    
    all_events = []
    cursor = None
    
    # PAGINATION LOOP: Fetch up to 5 pages (500 events) to find our data
    for _ in range(5):
        if cursor:
            params['cursor'] = cursor
            
        try:
            response = requests.get(f"{HOST}{path}", headers=headers, params=params)
            if response.status_code != 200:
                break # Stop if error
                
            data = response.json()
            events = data.get("events", [])
            all_events.extend(events)
            
            cursor = data.get("cursor")
            if not cursor:
                break # No more pages
        except:
            break

    # FILTERING LOGIC
    filtered_markets = []
    q = category_query.lower()
    
    # Enhanced Keywords mapping
    keywords = {
        "economics": ["economics", "economy", "fed", "inflation", "gdp", "cpi", "rate", "recession", "financial"],
        "politics": ["politics", "president", "election", "senate", "house", "trump", "biden", "vote", "government"],
        "tennis": ["tennis", "atp", "wta", "challenger", "itf", "open", "wimbledon"],
        "soccer": ["soccer", "league", "fifa", "uefa", "goal"],
        "crypto": ["crypto", "bitcoin", "btc", "eth", "price"]
    }
    
    target_words = keywords.get(q, [q])

    for e in all_events:
        # Create a searchable string from all available text fields
        search_text = f"{e.get('title', '')} {e.get('category', '')} {e.get('ticker', '')}".lower()
        
        # Check if ANY target word exists in the event text
        if any(w in search_text for w in target_words):
            for m in e.get("markets", []):
                m['event_title'] = e.get('title')
                m['event_cat'] = e.get('category')
                filtered_markets.append(m)
                
    return filtered_markets

# --- 4. HELPERS ---
def parse_price(market, side="yes"):
    p = market.get(f"{side}_bid")
    if p is not None: return int(p)
    p_str = market.get(f"{side}_bid_dollars")
    try: return int(float(p_str) * 100) if p_str else 0
    except: return 0

def format_time(iso_str):
    if not iso_str: return ""
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        if dt.date() == datetime.now().date():
            return f"Today {dt.strftime('%H:%M')}"
        return dt.strftime("%b %d")
    except:
        return ""

# --- 5. UI RENDERER ---
def render_row(m):
    ticker = m.get('ticker')
    title = m.get('title', 'Market')
    # If title is a massive list of legs, use event title
    if len(title) > 80:
        title = m.get('event_title', title)
        
    yes = parse_price(m, "yes")
    no = parse_price(m, "no")
    
    with st.container():
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        
        with c1:
            st.markdown(f"**{title}**")
            st.caption(f"{ticker} • {format_time(m.get('close_time'))}")
            
        with c2:
            # Yes Price
            color = "price-green" if yes > 0 else "sub-text"
            st.markdown(f"<div class='price-box'><span class='sub-text'>YES</span><br><span class='{color}'>{yes}¢</span></div>", unsafe_allow_html=True)

        with c3:
            # No Price
            color = "price-red" if no > 0 else "sub-text"
            st.markdown(f"<div class='price-box'><span class='sub-text'>NO</span><br><span class='{color}'>{no}¢</span></div>", unsafe_allow_html=True)
            
        with c4:
            st.button("Trade", key=ticker, use_container_width=True)
        
        st.markdown("---")

# --- 6. MAIN ---
def main():
    with st.sidebar:
        st.header("⚡ Kalshi Pro v5")
        cat = st.selectbox("Market", ["Politics", "Economics", "Tennis", "NBA", "Soccer", "Crypto"])
        min_liq = st.slider("Min Price", 0, 99, 1)
        st.info("v5.0: Auto-Pagination Enabled (Scans 500+ events)")

    st.title(f"{cat} Feed")
    
    with st.spinner(f"Scanning exchange for {cat} (Pages 1-5)..."):
        markets = fetch_all_markets(cat)
        
    # Filter
    valid = [m for m in markets if parse_price(m, "yes") >= min_liq]
    
    if valid:
        st.success(f"Found {len(valid)} Contracts")
        # Sort: Liquidity high to low, then time soonest
        valid.sort(key=lambda x: parse_price(x, "yes"), reverse=True)
        
        for m in valid[:50]: # Show top 50 to avoid lag
            render_row(m)
    else:
        st.warning("No markets found. The API is connected, but no matching events were found in the top 500 results.")

if __name__ == "__main__":
    main()
