import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="ADRO Matrix", layout="wide")

st.title("⛏️ PT Alamtri Resources (ADRO.JK) Cyclical Matrix")
st.caption("Commodity, Currency, and Trend Regime Monitoring")

# --- 1. SAFE DATA FETCHING ---
@st.cache_data(ttl=300)
def fetch_adro_data():
    try:
        df = yf.download("ADRO.JK", period="2y", progress=False)
        fx_df = yf.download("IDR=X", period="1y", progress=False)
        
        # Handle MultiIndex column structures cleanly
        if not df.empty and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if not fx_df.empty and isinstance(fx_df.columns, pd.MultiIndex):
            fx_df.columns = fx_df.columns.droplevel(1)
            
        return df, fx_df
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df, fx_df = fetch_adro_data()

# Validation Guard: Prevent crashing if yfinance returns empty data
if df.empty or len(df) < 200 or fx_df.empty:
    st.warning("⚠️ Market data provider (yfinance) is temporarily busy or returning incomplete data. Please refresh in a few moments.")
    st.stop()

# --- 2. CALCULATE INDICATORS ---
df["MA50"] = df["Close"].rolling(50).mean()
df["MA200"] = df["Close"].rolling(200).mean()
df["pct_vs_200ma"] = (df["Close"] / df["MA200"] - 1) * 100

delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / loss
df["RSI14"] = 100 - (100 / (1 + rs))

ma20 = df["Close"].rolling(20).mean()
std20 = df["Close"].rolling(20).std()
df["Upper_BB"] = ma20 + (2 * std20)
df["Lower_BB"] = ma20 - (2 * std20)
df["BB_pctB"] = (df["Close"] - df["Lower_BB"]) / (df["Upper_BB"] - df["Lower_BB"])

fx_df["MA50"] = fx_df["Close"].rolling(50).mean()

# Drop NA rows safely
clean_df = df.dropna()
clean_fx = fx_df.dropna()

if clean_df.empty or clean_fx.empty:
    st.warning("⚠️ Calculating technicals... Waiting for complete data history.")
    st.stop()

latest = clean_df.iloc[-1]
latest_fx = clean_fx.iloc[-1]

# --- 3. SCORING REGIME LOGIC ---
buy_count, sell_count = 0, 0

trend_status = "BULLISH" if latest["MA50"] > latest["MA200"] else "BEARISH"
if trend_status == "BULLISH": buy_count += 1 
else: sell_count += 1

if latest["pct_vs_200ma"] <= -15: buy_count += 1
elif latest["pct_vs_200ma"] >= 15: sell_count += 1

if latest["RSI14"] <= 35: buy_count += 1
elif latest["RSI14"] >= 70: sell_count += 1

if latest["BB_pctB"] <= 0: buy_count += 1
elif latest["BB_pctB"] >= 1: sell_count += 1

fx_status = "TAILWIND (Strong USD)" if latest_fx["Close"] > latest_fx["MA50"] else "HEADWIND (Weak USD)"
if latest_fx["Close"] > latest_fx["MA50"]: buy_count += 1
else: sell_count += 1

if buy_count >= 3:
    verdict = "CYCLICAL BUY ZONE 🟢"
    color = "normal"
elif sell_count >= 3:
    verdict = "CYCLICAL SELL ZONE 🔴"
    color = "inverse"
else:
    verdict = "NEUTRAL REGIME ⚪"
    color = "off"

# --- 4. DASHBOARD UI ---
st.divider()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Live Price", f"Rp{latest['Close']:,.0f}")
col2.metric("Trend (50 vs 200)", trend_status)
col3.metric("% vs 200 DMA", f"{latest['pct_vs_200ma']:+.2f}%")
col4.metric("RSI (14)", f"{latest['RSI14']:.1f}")
col5.metric("USD/IDR Overlay", fx_status)

st.metric("Algorithmic Verdict", verdict, delta_color=color)

st.divider()

# --- 5. INTERACTIVE CHART ---
st.subheader("Price Action vs Institutional Averages")
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
    name='ADRO Price'
))

fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], line=dict(color='orange', width=1.5), name='50-Day MA'))
fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='blue', width=2), name='200-Day MA'))

fig.update_layout(
    template="plotly_dark",
    xaxis_rangeslider_visible=False,
    height=500,
    margin=dict(l=0, r=0, t=30, b=0)
)
st.plotly_chart(fig, use_container_width=True)

with st.expander("View Manager's Research Thesis"):
    st.markdown("""
    **The Cyclical Nature of ADRO:**
    Unlike financial assets (like BBCA) that compound steadily, ADRO trades structurally based on commodity and macro cycles. 
    *   **The 15% DMA Rule:** Coal cycles create violent swings. We look for deep -15% structural discounts from the 200-day average to initiate cyclical accumulation.
    *   **The FX Component:** ADRO generates revenue in USD but pays domestic costs in IDR. A strengthening dollar (USD/IDR > 50MA) creates an artificial margin expansion for the asset.
    """)
