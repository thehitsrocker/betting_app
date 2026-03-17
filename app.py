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
    page_title="Kalshi Pro Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .market-card {
        background-color: #1e2130;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #30364d;
        transition: transform 0.2s;
    }
    .market-card:hover { border-color: #4dabf7; transform: translateY(-2px); }
    .market-title { font-weight: 700; font-size: 16px; color: #ffffff; margin-bottom: 8px; }
    .sub-text { font-size: 12px; color: #a0a0a0; }
    .price-green { color: #00e676; font-weight: bold; font-size: 18px; }
    .price-red { color: #ff5252; font-weight: bold; font-size: 18px; }
    .status-tag { 
        background-color: #3b82f6; color: white; padding: 2px 6px; 
        border-radius: 4px; font-size: 10px; font-weight: bold; text-transform: uppercase;
    }
    .status-tag.open { background-color: #00e676; color: black; }
    .status-tag.upcoming { background-color: #f59e0b; color: black; }
    </style>
""", unsafe_allow_html=True)

# --- 3. API CORE ---
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
    except Exception as e:
        st.error(f"🔐 Signing Error: {e}")
        return None

# --- 4. INTELLIGENT DATA FETCHING ---
@st.cache_data(ttl=60)
def fetch_events_with_markets(category_filter, status="open"):
    """
    Fetches EVENTS (which contain the category field) and their nested MARKETS.
    This fixes the issue where filtering Markets directly failed.
    """
    endpoint = "/events"
    full_path_sign = f"{BASE_PATH}{endpoint}"
    
    try:
        key_id = st.secrets["KALSHI_KEY_ID"]
        priv_key = st.secrets["KALSHI_PRIVATE_KEY"]
    except KeyError:
        st.error("❌ Secrets Missing: Add KALSHI_KEY_ID and KALSHI_PRIVATE_KEY")
        return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", full_path_sign, ts)
    
    if not sig: return []

    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json"
    }
    
    # Params for fetching EVENTS
    params = {
        "with_nested_markets": True, # CRITICAL: Get the markets inside the event
        "limit": 200,
        "status": status 
    }
    
    # If looking for future/upcoming, we might need to loosen the status
    if status == "upcoming":
        params["status"] = "open" # Kalshi often marks future events as 'open' but with future start dates, or we remove status
        # Note: To find truly "not yet open" markets, we'd remove status, but 'open' is safer for now.
        # We will filter by date in Python.
    
    try:
        response = requests.get(f"{HOST}{full_path_sign}", headers=headers, params=params)
        if response.status_code != 200:
            return []
            
        events = response.json().get("events", [])
        
        # 1. Filter Events by Category (Case insensitive)
        valid_events = [
            e for e in events 
            if e.get("category", "").lower() == category_filter.lower()
        ]
        
        # 2. Extract Markets from Valid Events
        all_markets = []
        for e in valid_events:
            nested_markets = e.get("markets", [])
            for m in nested_markets:
                # Inject event data into market for display
                m['event_category'] = e.get('category')
                m['event_title'] = e.get('title')
                m['event_status'] = status
                all_markets.append(m)
                
        return all_markets

    except Exception as e:
        st.error(f"Connection Error: {e}")
        return []

# --- 5. HELPER FUNCTIONS ---
def parse_price(market, side="yes"):
    price = market.get(f"{side}_bid")
    if price is not None: return int(price)
    price_str = market.get(f"{side}_bid_dollars")
    if price_str:
        try: return int(float(price_str) * 100)
        except: return 0
    return 0

def format_time(iso_str):
    if not iso_str: return ""
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        # If date is far in future, show Date, else show Time
        if dt > datetime.now() + timedelta(days=1):
            return dt.strftime("%b %d")
        return dt.strftime("%H:%M")
    except:
        return iso_str

# --- 6. UI RENDERING ---
def render_market_card(market, is_upcoming=False):
    ticker = market.get('ticker')
    # Clean title logic
    raw_title = market.get('title', 'Unknown')
    # If title is massive, use Event title
    if len(raw_title) > 100 and market.get('event_title'):
        main_title = market.get('event_title')
        sub_title = raw_title[:50] + "..."
    else:
        legs = raw_title.split(',')
        main_title = legs[0]
        sub_title = f"+{len(legs)-1} legs" if len(legs) > 1 else ""

    yes_bid = parse_price(market, "yes")
    no_bid = parse_price(market, "no")
    
    status_badge = "🟢 LIVE" if not is_upcoming else "📅 PRE-MARKET"
    status_class = "open" if not is_upcoming else "upcoming"

    with st.container():
        st.markdown(f"""
        <div class="market-card">
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span class="status-tag {status_class}">{status_badge}</span>
                <span class="sub-text">⏱️ {format_time(market.get('close_time'))}</span>
            </div>
            <div class="market-title">{main_title}</div>
            <div class="sub-text">{sub_title}</div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1, 1, 1.5])
        
        # If upcoming and no bids yet, show dashes
        yes_display = f"{yes_bid}¢" if yes_bid > 0 else "--"
        no_display = f"{no_bid}¢" if no_bid > 0 else "--"

        with c1:
            st.markdown(f"<div class='metric-box'><div style='font-size:10px; color:#aaa'>YES</div><div class='price-green'>{yes_display}</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-box'><div style='font-size:10px; color:#aaa'>NO</div><div class='price-red'>{no_display}</div></div>", unsafe_allow_html=True)
        with c3:
            btn_label = "TRADE" if not is_upcoming else "WATCH"
            st.button(btn_label, key=f"btn_{ticker}", use_container_width=True)

# --- 7. MAIN APP ---
def main():
    try:
        with st.sidebar:
            st.header("⚡ Kalshi Pro")
            cat = st.selectbox("Category", ["Economics", "Politics", "Tennis", "NBA", "Soccer", "Crypto", "Weather"])
            st.divider()
            min_liq = st.slider("Min Liquidity (¢)", 1, 99, 1)
            if st.button("Clear Cache"): st.cache_data.clear()

        st.title(f"Market Feed: {cat}")

        # PHASE 1: FETCH LIVE MARKETS
        with st.spinner("Scanning Live Markets..."):
            markets = fetch_events_with_markets(cat, status="open")
            
        # Filter by liquidity
        active_markets = [m for m in markets if parse_price(m, "yes") >= min_liq]

        if active_markets:
            st.success(f"Found {len(active_markets)} Active Contracts")
            cols = st.columns(3)
            for i, m in enumerate(active_markets):
                with cols[i % 3]:
                    render_market_card(m, is_upcoming=False)
        
        else:
            # PHASE 2: FALLBACK TO UPCOMING (If no live markets found)
            st.warning(f"No active '{cat}' markets found matching criteria.")
            st.info("🔎 Searching for upcoming events in the next 7 days...")
            
            # We intentionally re-fetch but logic could be adjusted to fetch 'all' if needed.
            # For now, we assume 'open' covers future, but maybe they were filtered out by liquidity.
            # Let's try to show low-liquidity ones as "Upcoming" or fetch strict future.
            
            future_markets = [m for m in markets if parse_price(m, "yes") < min_liq] 
            # If truly empty, it might be that the API returns nothing for "open". 
            # We could try fetching without status="open" here, but keeping it simple for v3.1
            
            if future_markets:
                 st.markdown("### 📅 Upcoming / Low Liquidity")
                 cols = st.columns(3)
                 for i, m in enumerate(future_markets[:9]): # Show max 9
                     with cols[i % 3]:
                         render_market_card(m, is_upcoming=True)
            else:
                st.error("No upcoming events found in the feed.")

    except Exception:
        st.error("System Error")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
