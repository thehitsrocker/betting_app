import streamlit as st
import pandas as pd
import numpy as np

# Page config
st.set_page_config(page_title="Pro Betting Dashboard", layout="wide")

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Odds Calculator", "Settings"])

if page == "Dashboard":
    st.title("📈 Betting Performance")
    
    # KPIs in columns
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Profit", "$1,250", "+$150")
    col2.metric("Win Rate", "64%", "+2%")
    col3.metric("ROI", "12.5%", "-0.5%")

    # Profit Chart
    st.subheader("Profit Over Time")
    chart_data = pd.DataFrame(
        np.random.randn(20, 1).cumsum(), 
        columns=['Profit']
    )
    st.line_chart(chart_data)

    # Betting Log
    st.subheader("Detailed Betting Log")
    df = pd.DataFrame({
        'Date': ['2024-03-01', '2024-03-02', '2024-03-03'],
        'Sport': ['NBA', 'Soccer', 'NFL'],
        'Bet': ['Lakers -3.5', 'Over 2.5 Goals', 'Chiefs ML'],
        'Result': ['Won', 'Won', 'Lost'],
        'Profit/Loss': [45.00, 22.50, -50.00]
    })
    st.dataframe(df, use_container_width=True)

elif page == "Odds Calculator":
    st.title("🧮 Odds Converter & Calculator")
    
    # Multiple inputs
    c1, c2 = st.columns(2)
    with c1:
        dec_odds = st.number_input("Decimal Odds", value=2.00)
    with c2:
        stake = st.number_input("Stake Amount ($)", value=100.00)
    
    profit = (dec_odds * stake) - stake
    st.success(f"Potential Profit: **${profit:,.2f}**")
    
    st.info("Tip: Professional bettors usually look for an Edge > 5%.")
