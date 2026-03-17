import streamlit as st
import pandas as pd

st.set_page_config(page_title="Betting Dashboard", page_icon="🎲")

st.title("🎲 Betting App Dashboard")
st.write("Welcome to your awesome betting app!")

# Simple Betting Calculator
st.header("Quick Odds Calculator")
odds = st.number_input("Enter Decimal Odds", min_value=1.0, value=2.0)
stake = st.number_input("Enter Stake ($)", min_value=0.0, value=10.0)

if st.button("Calculate Potential Profit"):
    profit = (odds * stake) - stake
    total = odds * stake
    st.success(f"Potential Profit: ${profit:.2f}")
    st.info(f"Total Return: ${total:.2f}")

# Placeholder for Data
st.header("Recent Bets")
data = pd.DataFrame({
    'Date': ['2023-10-01', '2023-10-02'],
    'Event': ['Lakers vs Celtics', 'Real Madrid vs Barca'],
    'Result': ['Won', 'Lost']
})
st.table(data)
