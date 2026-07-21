import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="BTC Analytics", layout="wide")
st.title("Bitcoin Unified Analytics")

# 1. Price & MA200 (Coinbase - No Blocks)
@st.cache_data(ttl=3600)
def get_price():
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    res = requests.get(url, params={"granularity": 86400}).json()
    df = pd.DataFrame(res, columns=['time', 'low', 'high', 'open', 'close', 'vol']).sort_values('time')
    df['date'] = pd.to_datetime(df['time'], unit='s')
    df['MA200'] = df['close'].rolling(200).mean()
    return df.dropna()

# 2. Fear & Greed (Alternative.me)
@st.cache_data(ttl=3600)
def get_fng():
    res = requests.get("https://api.alternative.me/fng/?limit=1").json()['data'][0]
    return res['value'], res['value_classification']

# 3. MVRV Ratio (CoinMetrics Community API - No Key Required)
@st.cache_data(ttl=3600)
def get_mvrv():
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    params = {
        "assets": "btc",
        "metrics": "CapMVRVCur",
        "frequency": "1d",
        "limit_per_asset": 365
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, params=params, headers=headers).json()
    
    df = pd.DataFrame(res['data'])
    df['date'] = pd.to_datetime(df['time'])
    df['mvrv'] = df['CapMVRVCur'].astype(float)
    return df

# Execute Fetchers
df_price = get_price()
fng_val, fng_class = get_fng()
df_mvrv = get_mvrv()

# Build the UI Layout
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Price & Technicals")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df_price['date'], y=df_price['close'], name='BTC Price', line=dict(color='#2962FF')))
    fig1.add_trace(go.Scatter(x=df_price['date'], y=df_price['MA200'], name='MA200', line=dict(color='#FF6D00')))
    fig1.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("MVRV Ratio (On-Chain)")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df_mvrv['date'], y=df_mvrv['mvrv'], name='MVRV', line=dict(color='#00E676')))
    fig2.update_layout(height=250, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
    st.plotly_chart(fig2, use_container_width=True)

with col2:
    st.subheader("Sentiment")
    st.metric(label="Fear & Greed Index", value=fng_val, delta=fng_class, delta_color="off")
