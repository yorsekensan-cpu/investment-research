import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="BTC Analytics", layout="wide")
st.title("Bitcoin Investment Dashboard")

@st.cache_data(ttl=3600)
def get_data():
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    params = {
        "assets": "btc",
        "metrics": "PriceUSD,CapMVRVCur",
        "frequency": "1d",
        "limit_per_asset": 365
    }
    res = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}).json()
    df = pd.DataFrame(res['data'])
    df['date'] = pd.to_datetime(df['time'])
    df['close'] = df['PriceUSD'].astype(float)
    df['mvrv'] = df['CapMVRVCur'].astype(float)
    df['MA200'] = df['close'].rolling(200).mean()
    return df.dropna()

@st.cache_data(ttl=3600)
def get_fng():
    res = requests.get("https://api.alternative.me/fng/?limit=1").json()['data'][0]
    return res['value'], res['value_classification']

df = get_data()
fng_val, fng_class = get_fng()

col1, col2 = st.columns([3, 1])

with col1:
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df['date'], y=df['close'], name='BTC Price', line=dict(color='#2962FF')))
    fig1.add_trace(go.Scatter(x=df['date'], y=df['MA200'], name='200 MA', line=dict(color='#FF6D00')))
    fig1.update_layout(title="Price & 200 MA", height=380, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df['date'], y=df['mvrv'], name='MVRV', line=dict(color='#00E676')))
    fig2.add_hline(y=1.0, line_dash="dash", line_color="gray", annotation_text="Fair Value (1.0)")
    fig2.update_layout(title="MVRV Valuation Band", height=300, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
    st.plotly_chart(fig2, use_container_width=True)

with col2:
    st.subheader("Market Sentiment")
    st.metric(label="Fear & Greed Index", value=fng_val, delta=fng_class, delta_color="off")
