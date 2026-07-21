import streamlit as st
import pandas as pd
import yfinance as yf
import requests

st.title("Portfolio Allocation & Rebalancing Engine")
st.caption("Mathematical sizing and rebalancing model based on live market prices.")

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
    cash_fiat = st.number_input("Idle Cash (IDR)", min_value=0.0, value=50000000.0, step=1000000.0)
with col2:
    btc_units = st.number_input("BTC Holdings (Units)", min_value=0.0, value=0.25, step=0.01)
with col3:
    bbca_shares = st.number_input("BBCA Holdings (Shares)", min_value=0, value=1500, step=100)

st.subheader("2. Target Asset Allocation Weights (%)")
t_col1, t_col2, t_col3 = st.columns(3)

with t_col1:
    target_cash_pct = st.slider("Target Cash %", 0, 100, 30)
with t_col2:
    target_btc_pct = st.slider("Target BTC %", 0, 100, 30)
with t_col3:
    target_bbca_pct = st.slider("Target BBCA %", 0, 100, 40)

total_target_pct = target_cash_pct + target_btc_pct + target_bbca_pct

if total_target_pct != 100:
    st.error(f"Target weights must equal 100%. Current sum: {total_target_pct}%")
else:
    # --- 3. MATHEMATICAL ENGINE ---
    # Convert BTC USD price to IDR scale for uniform portfolio math (using an approximate USD/IDR rate baseline or native USD valuation)
    # Let's compute everything in IDR value baseline:
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

    # Convert capital deltas into executable asset quantities
    btc_units_to_trade = delta_btc_val / (btc_p * usd_to_idr)
    bbca_shares_to_trade = int(delta_bbca_val / bbca_p)

    st.divider()
    st.subheader("3. Execution Matrix & Rebalancing Plan")
    st.metric(label="Total Portfolio Valuation", value=f"Rp {total_portfolio_value:,.0f}")

    matrix_df = pd.DataFrame({
        "Asset": ["Cash / Stable", "Bitcoin (BTC)", "BBCA.JK"],
        "Current Value (IDR)": [cash_fiat, btc_val_idr, bbca_val_idr],
        "Actual Weight": [f"{actual_cash_pct:.1f}%", f"{actual_btc_pct:.1f}%", f"{actual_bbca_pct:.1f}%"],
        "Target Weight": [f"{target_cash_pct}%", f"{target_btc_pct}%", f"{target_bbca_pct}%"],
        "Action Required": [
            f"Add Rp {delta_cash:,.0f}" if delta_cash > 0 else f"Trim Rp {-delta_cash:,.0f}",
            f"Buy {btc_units_to_trade:.4f} BTC (Rp {delta_btc_val:,.0f})" if delta_btc_val > 0 else f"Sell {-btc_units_to_trade:.4f} BTC (Rp {-delta_btc_val:,.0f})",
            f"Buy {bbca_shares_to_trade} shares (Rp {delta_bbca_val:,.0f})" if bbca_shares_to_trade > 0 else f"Sell {-bbca_shares_to_trade} shares (Rp {-delta_bbca_val:,.0f})"
        ]
    })

    st.table(matrix_df)
