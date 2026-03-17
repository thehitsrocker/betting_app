import streamlit as st
import pandas as pd
import requests
import time
import base64
import traceback
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- 1. APP CONFIG (MUST BE FIRST) ---
st.set_page_config(
    page_title="Kalshi Pro Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CUSTOM CSS ---
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
    .price-green { color: #00e676; font-weight: bold; font-size: 18px; }
    .price-red { color: #ff5252; font-weight: bold; font-size: 18px; }
    .metric-box { text-align: center; padding: 5px; background: #262a40; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. API CONSTANTS & AUTHENTICATION ---
HOST = "https://api.elections.kalshi.com"
# The base path for signing is /trade-api/v2
BASE_PATH = "/trade-api/v2"

def sign_request(private_key_str, method, path, timestamp):
    """
    Signs the request using RSA-PSS.
    CRITICAL: 'path' must include the full /trade-api/v2/... prefix but NO query params.
    """
    try:
        private_key = serialization.load_pem_private_key(
            private_key_str.encode(), password=None
        )
        # Message = timestamp + method + path (e.g., "123456789GET/trade-api/v2/markets")
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
        st.error(f"🔐 Signing Error: {e}")
        return None

# --- 4. DATA FETCHING & FILTERING ---
@st.cache_data(ttl=60)
def fetch_markets(category_filter):
    # We request ALL open markets (limit 1000) because the API doesn't support
    # server-side category filtering reliably on this endpoint.
    endpoint_path = "/markets"
    full_path_for_sign = f"{BASE_PATH}{endpoint_path}"
    
    # Load secrets inside the function to avoid global scope issues
    try:
        key_id = st.secrets["KALSHI_KEY_ID"]
        priv_key = st.secrets["KALSHI_PRIVATE_KEY"]
    except KeyError:
        st.error("❌ Secrets Missing: Add KALSHI_KEY_ID and KALSHI_PRIVATE_KEY to .streamlit/secrets.toml")
        return []

    ts = str(int(time.time() * 1000))
    sig = sign_request(priv_key, "GET", full_path_for_sign, ts)
    
    if not sig:
        return []

    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json"
    }
    
    # Params go here, NOT in the signed path
    params = {"status": "open", "limit": 500}
    
    try:
        url = f"{HOST}{full_path_for_sign}"
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            st.warning(f"API Status {response.status_code}: {response.text}")
            return []
            
        data = response.json()
        all_markets = data.get("markets", [])
        
        # CLIENT-SIDE FILTERING
        # Filter markets where 'category' matches the user selection
        filtered = [m for m in all_markets if m.get("category") == category_filter]
        return filtered

    except Exception as e:
        st.error(f"Connection Failed: {e}")
        return []

# --- 5. HELPERS ---
def parse_price(market, side="yes"):
    """Handles Kalshi's shifting price format (int cents vs string dollars)."""
    # 1. Try cents (old format)
    price = market.get(f"{side}_bid")
    if price is not None:
        return int(price)
    
    # 2. Try dollars string (new format)
    price_str = market.get(f"{side}_bid_dollars")
    if price_str:
        try:
            return int(float(price_str) * 100)
        except ValueError:
            return 0
    return 0

def format_time(iso_str):
    if not iso_str: return ""
    try:
        dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%b %d, %H:%M")
    except:
        return iso_str

# --- 6. UI RENDERER ---
def render_market_card(market):
    ticker = market.get('ticker')
    raw_title = market.get('title', 'Unknown Market')
    
    # Smart Parsing for Parlays
    legs = [leg.strip() for leg in raw_title.split(',') if leg.strip()]
    main_title = legs[0] if legs else ticker
    remaining_legs = legs[1:]
    
    yes_bid = parse_price(market, "yes")
    no_bid = parse_price(market, "no")

    with st.container():
        st.markdown(f"""
        <div class="market-card">
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span style="color:#888; font-size:11px;">{ticker}</span>
                <span style="color:#888; font-size:11px;">⏱️ {format_time(market.get('close_time'))}</span>
            </div>
            <div class="market-title">{main_title}</div>
        </div>
        """, unsafe_allow_html=True)

        if remaining_legs:
            with st.expander(f"📋 {len(remaining_legs)} More Legs"):
                for leg in remaining_legs:
                    st.caption(f"• {leg}")

        c1, c2, c3 = st.columns([1, 1, 1.5])
        with c1:
            st.markdown(f"<div class='metric-box'><div style='font-size:10px; color:#aaa'>YES</div><div class='price-green'>{yes_bid}¢</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-box'><div style='font-size:10px; color:#aaa'>NO</div><div class='price-red'>{no_bid}¢</div></div>", unsafe_allow_html=True)
        with c3:
            st.button(f"TRADE", key=f"btn_{ticker}", use_container_width=True)
        st.markdown("---")

# --- 7. MAIN EXECUTION ---
def main():
    try:
        with st.sidebar:
            st.header("⚡ Kalshi Pro")
            # Note: "Economics" is usually the most populated category
            cat = st.selectbox("Market Category", ["Economics", "Politics", "Tennis", "NBA", "Soccer", "Crypto"])
            
            st.divider()
            min_liquidity = st.slider("Min Price (¢)", 1, 99, 2)
            
            if st.button("Clear Cache"):
                st.cache_data.clear()

        st.title(f"Live {cat} Markets")

        with st.spinner("Scanning Exchange..."):
            markets = fetch_markets(cat)

        if not markets:
            st.info(f"No active markets found for '{cat}'. The API is connected, but this category might be empty right now. Try 'Economics' or 'Politics'.")
        else:
            # Filter by price
            valid_markets = [m for m in markets if parse_price(m, "yes") >= min_liquidity]
            st.success(f"Loaded {len(valid_markets)} Contracts")
            
            # Grid Layout
            cols = st.columns(3)
            for i, market in enumerate(valid_markets):
                with cols[i % 3]:
                    render_market_card(market)
                    
    except Exception:
        st.error("CRITICAL APP ERROR")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    main()
