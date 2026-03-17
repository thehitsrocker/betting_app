import streamlit as st
import pandas as pd
import requests
import time
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- API CONSTANTS ---
BASE_URL = "https://trading-api.kalshi.com/v1" # Production

def sign_request(private_key_str, method, path, body=""):
    """Professional RSA-PSS signing for Kalshi v2 API"""
    private_key = serialization.load_pem_private_key(
        private_key_str.encode(), password=None
    )
    timestamp = str(int(time.time() * 1000))
    msg = timestamp + method + path + body
    signature = private_key.sign(
        msg.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode(), timestamp

def get_tennis_markets():
    path = "/markets?category=Tennis&status=open"
    # Use secrets for security
    key_id = st.secrets["KALSHI_KEY_ID"]
    priv_key = st.secrets["KALSHI_PRIVATE_KEY"]
    
    sig, ts = sign_request(priv_key, "GET", path)
    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts
    }
    res = requests.get(BASE_URL + path, headers=headers)
    return res.json().get("markets", [])

st.title("🎾 Pro Tennis Kalshi Terminal")

if st.button("Fetch Live Tennis Contracts"):
    markets = get_tennis_markets()
    if markets:
        df = pd.DataFrame(markets)[['title', 'yes_bid', 'no_bid', 'ticker']]
        st.dataframe(df, use_container_width=True)
    else:
        st.error("Check API Keys in Streamlit Secrets")
