import streamlit as st
import pandas as pd
import requests
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- API CONSTANTS ---
# Use the v2 API URL (even for non-election markets like Tennis)
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2" 

def sign_request(private_key_str, method, path, timestamp):
    """
    Kalshi v2 RSA-PSS signing.
    IMPORTANT: The signature message must be: timestamp + method + path
    The path must NOT include query parameters.
    """
    private_key = serialization.load_pem_private_key(
        private_key_str.encode(), password=None
    )
    # The message to sign
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

def get_tennis_markets():
    # Path for signing (NO query params here)
    path = "/markets"
    
    # Query parameters for the request
    params = {
        "category": "Tennis",
        "status": "open",
        "limit": 100
    }
    
    try:
        key_id = st.secrets["KALSHI_KEY_ID"]
        priv_key = st.secrets["KALSHI_PRIVATE_KEY"]
    except KeyError:
        st.error("Missing KALSHI_KEY_ID or KALSHI_PRIVATE_KEY in Streamlit Secrets.")
        return []

    # Generate timestamp in milliseconds
    ts = str(int(time.time() * 1000))
    
    # Sign the request using the base path only
    sig = sign_request(priv_key, "GET", path, ts)
    
    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json"
    }
    
    # Make the request with params separated from the path
    response = requests.get(f"{BASE_URL}{path}", headers=headers, params=params)
    
    if response.status_code != 200:
        st.error(f"API Error {response.status_code}: {response.text}")
        return []
        
    try:
        return response.json().get("markets", [])
    except requests.exceptions.JSONDecodeError:
        st.error("Server returned non-JSON response. Check API URL.")
        return []

st.set_page_config(page_title="Tennis Terminal", page_icon="🎾")
st.title("🎾 Pro Tennis Kalshi Terminal")

if st.button("Fetch Live Tennis Contracts"):
    with st.spinner("Fetching markets..."):
        markets = get_tennis_markets()
        
    if markets:
        # v2 API uses different field names (yes_bid -> yes_bid_price, etc.)
        df = pd.DataFrame(markets)
        
        # Standardizing display columns for Tennis contracts
        cols_to_show = ['title', 'ticker', 'yes_bid', 'no_bid', 'close_time']
        available_cols = [c for c in cols_to_show if c in df.columns]
        
        st.dataframe(df[available_cols], use_container_width=True)
    else:
        st.info("No open Tennis markets found or there was an error.")

