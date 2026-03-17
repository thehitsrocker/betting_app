import streamlit as st
import pandas as pd
import requests
import time
import base64
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- APP CONFIGURATION ---
st.set_page_config(
    page_title="Kalshi Pro Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR ESPN/BLOOMBERG STYLE ---
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
    .leg-item { font-size: 13px; color: #a0a0a0; margin-left: 15px; }
    .metric-box { text-align: center; padding: 5px; background: #262a40; border-radius: 5px; }
    .price-green { color: #00e676; font-weight: bold; font-size: 18px; }
    .price-red { color: #ff5252; font-weight: bold; font-size: 18px; }
    </style>
""", unsafe_allow_html=True)

# --- API CONSTANTS ---
BASE_URL = "https://api.elections.kalshi.com"

# --- AUTHENTICATION LOGIC (RSA-PSS) ---
def sign_request(private_key_str, method, path, timestamp):
    """
    Kalshi v2 RSA-PSS signing.
    """
    try:
        private_key = serialization.load_pem_private_key(
            private_key_str.encode(), password=None
        )
        msg = f"{timestamp}{method}{path}"
        signature = private_key.sign(
            msg.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode("utf-8")
    except Exception as e:
        st.error(f"Signing Error: {e}")
        return None

# --- DATA FETCHING ---
@st.cache_data(ttl=30)
def fetch_markets(category, status="open", limit=50):
    path = "/markets"
    
    # Dynamic params based on user selection
    params = {
        "limit": limit,
        "status": status,
        "category": category
    }

    try:
        key_id = st.secrets["KALSHI_KEY_ID"]
        priv_key = st.secrets["KALSHI_PRIVATE_KEY"]
    except KeyError:
        st.error("❌ Secrets Missing: Add KALSHI_KEY_ID and KALSHI_PRIVATE_KEY to .streamlit/secrets.toml")
        return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", path, ts)
    
    if not sig:
        return []

    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(f"{BASE_URL}{path}", headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            return data.get("markets", [])
        else:
            st.warning(f"API Status {response.status_code}: {response.text}")
            return []
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        return []

# --- PARSING HELPERS ---
def parse_price(market, side="yes"):
    """Safely extract price, handling both integer cents and dollar string formats."""
    # Try 'yes_bid' (old int format)
    price = market.get(f"{side}_bid")
    if price is not None:
        return int(price)
    
    # Try 'yes_bid_dollars' (new string format "0.56")
    price_str = market.get(f"{side}_bid_dollars")
    if price_str:
        try:
            return int(float(price_str) * 100)
        except ValueError:
            return 0
    return 0

def format_time(iso_str):
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%b %d, %H:%M")
    except:
        return iso_str

# --- UI COMPONENTS ---
def render_market_card(market):
    """Renders a single market in a clean, professional card."""
    ticker = market.get('ticker')
    # Parse the massive title string
    raw_title = market.get('title', 'Unknown Market')
    legs = [leg.strip() for leg in raw_title.split(',') if leg.strip()]
    
    # Clean up the main title (Use the first leg or a generic name)
    main_title = legs[0] if legs else ticker
    remaining_legs = legs[1:]
    
    yes_bid = parse_price(market, "yes")
    no_bid = parse_price(market, "no")
    volume = market.get('volume', 0)
    
    # Card Container
    with st.container():
        st.markdown(f"""
        <div class="market-card">
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#888; font-size:12px;">{ticker}</span>
                <span style="color:#888; font-size:12px;">⏱️ {format_time(market.get('close_time'))}</span>
            </div>
            <div class="market-title">{main_title}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Legs Expander (for Parlays)
        if remaining_legs:
            with st.expander(f"📋 +{len(remaining_legs)} Additional Legs"):
                for leg in remaining_legs:
                    st.markdown(f"- {leg}")
        
        # Price Grid
        c1, c2, c3 = st.columns([1, 1, 1.5])
        
        with c1:
            st.markdown(f"<div class='metric-box'><div style='font-size:10px; color:#aaa'>YES BID</div><div class='price-green'>{yes_bid}¢</div></div>", unsafe_allow_html=True)
        
        with c2:
            st.markdown(f"<div class='metric-box'><div style='font-size:10px; color:#aaa'>NO BID</div><div class='price-red'>{no_bid}¢</div></div>", unsafe_allow_html=True)
            
        with c3:
            # Action Button (Mockup)
            st.button(f"TRADE", key=f"btn_{ticker}", use_container_width=True, type="primary")
        
        st.markdown("---")

# --- MAIN APP LOGIC ---
def main():
    # Sidebar Navigation
    with st.sidebar:
        st.title("⚡ Kalshi Terminal")
        
        selected_category = st.selectbox(
            "Select Market",
            ["Tennis", "NBA", "Soccer", "Economics", "Politics", "Crypto"],
            index=0
        )
        
        st.divider()
        st.caption("Filters")
        min_liquidity = st.slider("Min Price (¢)", 1, 99, 1)
        hide_low_vol = st.checkbox("Hide Low Volume", value=True)
        
        if st.button("🔄 Refresh Feed", use_container_width=True):
            st.cache_data.clear()

    # Main Content
    st.title(f"Live {selected_category} Markets")
    
    # Fetch Data
    with st.spinner(f"Connecting to Kalshi Exchange ({selected_category})..."):
        markets = fetch_markets(selected_category)
    
    if not markets:
        st.info("No open markets found for this category. Try 'Economics' or 'Politics' for guaranteed data.")
        return

    # Filtering Logic
    filtered_markets = []
    for m in markets:
        price = parse_price(m, "yes")
        if price >= min_liquidity:
            filtered_markets.append(m)
            
    st.caption(f"Displaying {len(filtered_markets)} active contracts")

    # Grid Layout (3 cards per row)
    cols = st.columns(3)
    for i, market in enumerate(filtered_markets):
        with cols[i % 3]:
            render_market_card(market)

if __name__ == "__main__":
    main()
