import streamlit as st
import pandas as pd
import requests
import time
import base64
import traceback
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. CONFIG & STYLING ---
st.set_page_config(
    page_title="Kalshi Pro",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .market-card {
        background-color: #1e2130;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #30364d;
    }
    .market-card:hover { border-color: #4dabf7; }
    .market-title { font-weight: 700; font-size: 15px; color: #ffffff; margin-bottom: 5px; }
    .sub-text { font-size: 11px; color: #a0a0a0; }
    .price-green { color: #00e676; font-weight: bold; font-size: 18px; }
    .price-red { color: #ff5252; font-weight: bold; font-size: 18px; }
    .league-tag {
        background-color: #262a40; color: #4dabf7; padding: 2px 8px;
        border-radius: 4px; font-size: 10px; font-weight: bold; letter-spacing: 1px;
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

# --- 3. OMNI-SEARCH LOGIC ---
@st.cache_data(ttl=60)
def fetch_sports_markets(sport_keyword):
    """
    Fetches ALL 'Sports' events and filters manually for keywords like 'Tennis', 'ATP', 'WTA'.
    This bypasses the API's strict category limitations.
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
    
    if not sig: return []

    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json"
    }
    
    # We fetch "Sports" generally, then filter in Python
    params = {"status": "open", "limit": 500, "with_nested_markets": True}
    
    try:
        response = requests.get(f"{HOST}{path}", headers=headers, params=params)
        if response.status_code != 200: return []
        
        events = response.json().get("events", [])
        matches = []
        
        # Keywords to identify the sport
        # If user selects "Tennis", we look for: Tennis, ATP, WTA, Challenger, ITF
        search_terms = [sport_keyword.lower()]
        if sport_keyword == "Tennis":
            search_terms += ["atp", "wta", "challenger", "itf", "australian", "french", "wimbledon", "us open"]
        elif sport_keyword == "NBA":
            search_terms += ["basketball"]
            
        for e in events:
            # Check if any keyword is in the Title, Category, or Ticker
            e_str = f"{e.get('title')} {e.get('category')} {e.get('ticker')}".lower()
            
            if any(term in e_str for term in search_terms):
                for m in e.get("markets", []):
                    # Inject event details into the market object
                    m['event_title'] = e.get('title')
                    m['series_ticker'] = e.get('series_ticker', '')
                    matches.append(m)
                    
        return matches

    except Exception as e:
        st.error(f"Connection Error: {e}")
        return []

# --- 4. HELPERS ---
def parse_price(market, side="yes"):
    p = market.get(f"{side}_bid")
    if p is not None: return int(p)
    p_str = market.get(f"{side}_bid_dollars")
    try: return int(float(p_str) * 100) if p_str else 0
    except: return 0

def format_start_time(iso_str):
    if not iso_str: return ""
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        now = datetime.now()
        # If today, show time. If future, show Date + Time
        if dt.date() == now.date():
            return f"Today, {dt.strftime('%H:%M')}"
        return dt.strftime("%b %d, %H:%M")
    except:
        return iso_str

def get_league_tag(ticker):
    if "ATP" in ticker: return "ATP TOUR"
    if "WTA" in ticker: return "WTA TOUR"
    if "NBA" in ticker: return "NBA"
    return "PRO SPORT"

# --- 5. UI RENDERER ---
def render_market_card(market):
    ticker = market.get('ticker')
    event_title = market.get('event_title', 'Match')
    
    # Tennis titles are often "Player A vs Player B"
    # We can clean this up if it's too long
    display_title = event_title
    
    yes_bid = parse_price(market, "yes")
    no_bid = parse_price(market, "no")
    league = get_league_tag(market.get('series_ticker', ''))

    with st.container():
        st.markdown(f"""
        <div class="market-card">
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span class="league-tag">{league}</span>
                <span class="sub-text">⏱️ {format_start_time(market.get('close_time'))}</span>
            </div>
            <div class="market-title">{display_title}</div>
            <div class="sub-text" style="margin-bottom:10px;">{ticker}</div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1, 1, 1.2])
        
        # Use grey if price is 0 (illiquid)
        c_yes = "price-green" if yes_bid > 0 else "sub-text"
        c_no = "price-red" if no_bid > 0 else "sub-text"

        with c1:
            st.markdown(f"<div style='text-align:center'><div style='font-size:10px; color:#aaa'>YES</div><div class='{c_yes}'>{yes_bid}¢</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='text-align:center'><div style='font-size:10px; color:#aaa'>NO</div><div class='{c_no}'>{no_bid}¢</div></div>", unsafe_allow_html=True)
        with c3:
            st.button("TRADE", key=f"btn_{ticker}", use_container_width=True)

# --- 6. MAIN APP ---
def main():
    with st.sidebar:
        st.header("🎾 Pro Tennis Terminal")
        sport = st.selectbox("Sport Selection", ["Tennis", "NBA", "Soccer", "Economics", "Politics"])
        st.divider()
        min_liq = st.slider("Min Liquidity (¢)", 1, 99, 1)
        if st.button("🔄 Force Refresh"):
            st.cache_data.clear()

    st.title(f"Live {sport} Feed")

    with st.spinner(f"Scanning Global Markets for {sport}..."):
        # Logic: If Economics/Politics, use standard fetch. If Sports, use Omni-Search.
        if sport in ["Tennis", "NBA", "Soccer"]:
            markets = fetch_sports_markets(sport)
        else:
            # Fallback for non-sports if you want to keep using the other function
            # For this snippet, I'll just map them to the same function 
            # assuming "Economics" works as a keyword search too.
            markets = fetch_sports_markets(sport)

    # Filter by liquidity
    valid_markets = [m for m in markets if parse_price(m, "yes") >= min_liq]

    if valid_markets:
        st.success(f"Found {len(valid_markets)} Active Contracts")
        
        # Sort by time (soonest first)
        valid_markets.sort(key=lambda x: x.get('close_time', ''))
        
        cols = st.columns(3)
        for i, m in enumerate(valid_markets):
            with cols[i % 3]:
                render_market_card(m)
    else:
        st.warning(f"No markets found for {sport} with price >= {min_liq}¢.")
        st.info("Tip: Try lowering the liquidity filter to 1¢ to see illiquid markets.")

if __name__ == "__main__":
    main()
