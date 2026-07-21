import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import plotly.graph_objects as go

st.title("Portfolio Allocation & Rebalancing Engine")
st.caption("Mathematical sizing, scenario modeling, and rebalancing driven by live market prices.")

# --- 1. FETCH LIVE PRICES ---
@st.cache_data(ttl=3600)
def get_live_prices():
    btc_price, bbca_price = 60000.0, 10000.0
    try:
        url = "https://api.blockchain.info/charts/market-price"
        res = requests.get(url, params={"timespan": "30days", "format": "json"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).json()
        btc_price = float(res["values"][-1]["y"])
    except:
        pass

    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        df_bbca = yf.download("BBCA.JK", period="5d", progress=False, session=session)
        if isinstance(df_bbca.columns, pd.MultiIndex):
            df_bbca.columns = df_bbca.columns.droplevel(1)
        bbca_price = float(df_bbca["Close"].iloc[-1])
    except:
        pass

    return btc_price, bbca_price

btc_p, bbca_p = get_live_prices()

# --- 2. INPUT PARAMETERS ---
st.subheader("1. Input Current Holdings & Capital")
col1, col2, col3 = st.columns(3)

with col1:
    cash_fiat = st.number_input("Idle Cash (IDR)", min_value=0.0, value=50000000.0, step=1000000.0, format="%.0f")
with col2:
    btc_units = st.number_input("BTC Holdings (Units)", min_value=0.0, value=0.25, step=0.01, format="%.4f")
with col3:
    bbca_shares = st.number_input("BBCA Holdings (Shares)", min_value=0, value=1500, step=100)

# --- 3. SCENARIO PRESETS ---
st.subheader("2. Select Deployment Scenario Preset")
scenario = st.radio(
    "Choose risk posture:", 
    options=[
        "Custom Weights", 
        "🛡️ Conservative (Non-Deployed / High Cash - 60% Cash / 20% BTC / 20% BBCA)", 
        "⚖️ Balanced (Medium Deployed - 30% Cash / 30% BTC / 40% BBCA)", 
        "🚀 Aggressive (Fully Deployed w/ Cash Reserve - 15% Cash / 45% BTC / 40% BBCA)"
    ],
    index=2, 
    horizontal=False
)

if "Conservative" in scenario:
    def_cash, def_btc, def_bbca = 60, 20, 20
elif "Balanced" in scenario:
    def_cash, def_btc, def_bbca = 30, 30, 40
elif "Aggressive" in scenario:
    def_cash, def_btc, def_bbca = 15, 45, 40  # Preserves 15% cash safety buffer
else:
    def_cash, def_btc, def_bbca = 30, 30, 40

st.subheader("3. Target Asset Allocation Weights (%)")
t_col1, t_col2, t_col3 = st.columns(3)

with t_col1:
    target_cash_pct = st.slider("Target Cash %", 0, 100, def_cash)
with t_col2:
    target_btc_pct = st.slider("Target BTC %", 0, 100, def_btc)
with t_col3:
    target_bbca_pct = st.slider("Target BBCA %", 0, 100, def_bbca)

total_target_pct = target_cash_pct + target_btc_pct + target_bbca_pct

if total_target_pct != 100:
    st.error(f"Target weights must equal 100%. Current sum: {total_target_pct}%")
else:
    # --- 4. MATHEMATICAL ENGINE ---
    usd_to_idr = 16000 
    btc_val_idr = btc_units * btc_p * usd_to_idr
    bbca_val_idr = bbca_shares * bbca_p
    
    total_portfolio_value = cash_fiat + btc_val_idr + bbca_val_idr

    # Actual Weights
    actual_cash_pct = (cash_fiat / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
    actual_btc_pct = (btc_val_idr / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
    actual_bbca_pct = (bbca_val_idr / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0

    # Target Capital Values
    target_cash_val = total_portfolio_value * (target_cash_pct / 100)
    target_btc_val = total_portfolio_value * (target_btc_pct / 100)
    target_bbca_val = total_portfolio_value * (target_bbca_pct / 100)

    # Rebalance Deltas
    delta_cash = target_cash_val - cash_fiat
    delta_btc_val = target_btc_val - btc_val_idr
    delta_bbca_val = target_bbca_val - bbca_val_idr

    # Trade Quantities
    btc_units_to_trade = delta_btc_val / (btc_p * usd_to_idr)
    bbca_shares_to_trade = int(delta_bbca_val / bbca_p)

    st.divider()
    st.subheader("4. Visual Weight Distribution")
    
    d_col1, d_col2 = st.columns(2)
    labels = ["Cash / Stable", "Bitcoin (BTC)", "BBCA.JK"]
    actual_weights = [actual_cash_pct, actual_btc_pct, actual_bbca_pct]
    target_weights = [target_cash_pct, target_btc_pct, target_bbca_pct]
    colors = ["#2962FF", "#FFD600", "#00E676"]

    with d_col1:
        fig_actual = go.Figure(data=[go.Pie(labels=labels, values=actual_weights, hole=.5, marker_colors=colors)])
        fig_actual.update_layout(title="Current Allocation", height=300, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
        st.plotly_chart(fig_actual, use_container_width=True)

    with d_col2:
        fig_target = go.Figure(data=[go.Pie(labels=labels, values=target_weights, hole=.5, marker_colors=colors)])
        fig_target.update_layout(title="Target Allocation", height=300, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
        st.plotly_chart(fig_target, use_container_width=True)

    st.divider()
    st.subheader("5. Execution Matrix & Rebalancing Plan")
    st.metric(label="Total Portfolio Valuation", value=f"Rp {total_portfolio_value:,.0f}")

    matrix_df = pd.DataFrame({
        "Asset": ["Cash / Stable", "Bitcoin (BTC)", "BBCA.JK"],
        "Current Value (IDR)": [f"Rp {cash_fiat:,.0f}", f"Rp {btc_val_idr:,.0f}", f"Rp {bbca_val_idr:,.0f}"],
        "Actual Weight": [f"{actual_cash_pct:.1f}%", f"{actual_btc_pct:.1f}%", f"{actual_bbca_pct:.1f}%"],
        "Target Weight": [f"{target_cash_pct}%", f"{target_btc_pct}%", f"{target_bbca_pct}%"],
        "Action Required": [
            f"Add Rp {delta_cash:,.0f}" if delta_cash > 0 else f"Trim Rp {-delta_cash:,.0f}",
            f"Buy {btc_units_to_trade:.4f} BTC (Rp {delta_btc_val:,.0f})" if delta_btc_val > 0 else f"Sell {-btc_units_to_trade:.4f} BTC (Rp {-delta_btc_val:,.0f})",
            f"Buy {bbca_shares_to_trade} shares (Rp {delta_bbca_val:,.0f})" if bbca_shares_to_trade > 0 else f"Sell {-bbca_shares_to_trade} shares (Rp {-delta_bbca_val:,.0f})"
        ]
    })

    st.table(matrix_df)
