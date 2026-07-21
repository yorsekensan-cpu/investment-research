import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="BTC Analytics", layout="wide")
st.title("Bitcoin Investment Dashboard")
st.caption("On-chain valuation + technical regime dashboard. Not financial advice — use as one input among many.")

# ---------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------

def _fetch_blockchain_chart(chart_name):
    """
    Blockchain.com's public charts API. Free, no key, no auth header needed,
    stable for well over a decade. Returns {"values": [{"x": epoch_sec, "y": value}, ...]}.
    sampled=false forces full daily resolution instead of the ~1.5k-point
    downsampled default, which would otherwise wreck rolling-window indicators.
    """
    url = f"https://api.blockchain.info/charts/{chart_name}"
    params = {"timespan": "all", "format": "json", "sampled": "false"}
    res = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).json()
    out = pd.DataFrame(res["values"])
    out["date"] = pd.to_datetime(out["x"], unit="s").dt.normalize()
    return out[["date", "y"]]


@st.cache_data(ttl=3600)
def get_data():
    """
    NOTE: CoinMetrics retired CapMrktCurUSD / CapRealUSD / IssContUSD from their
    free Community tier (confirmed — those calls now 400 on the free endpoint),
    which is what broke MVRV Z-Score / NUPL / Puell in the previous version.
    There is currently no verified free, no-key source for realized-cap data,
    so MVRV Z-Score and NUPL are dropped rather than shipped broken.
    Puell Multiple is rebuilt using Blockchain.com's free miners-revenue chart
    (real miner USD revenue — same concept as before, different free source).
    """
    price = _fetch_blockchain_chart("market-price").rename(columns={"y": "close"})
    revenue = _fetch_blockchain_chart("miners-revenue").rename(columns={"y": "miner_rev_usd"})

    df = pd.merge(price, revenue, on="date", how="left").sort_values("date").reset_index(drop=True)
    df = df[df["close"] > 0].reset_index(drop=True)  # blockchain.info sometimes has stray zero rows pre-2011

    # --- Technicals (computed locally, no extra API calls) ---
    df["MA200"] = df["close"].rolling(200).mean()
    df["MA111"] = df["close"].rolling(111).mean()
    df["MA350x2"] = df["close"].rolling(350).mean() * 2  # Pi Cycle Top upper leg
    df["pct_vs_200ma"] = (df["close"] / df["MA200"] - 1) * 100

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI14"] = 100 - (100 / (1 + rs))

    ma20 = df["close"].rolling(20).mean()
    std20 = df["close"].rolling(20).std()
    upper_bb = ma20 + 2 * std20
    lower_bb = ma20 - 2 * std20
    df["BB_pctB"] = (df["close"] - lower_bb) / (upper_bb - lower_bb)

    # --- Puell Multiple (miner USD revenue vs its own 365-day average) ---
    df["puell"] = df["miner_rev_usd"] / df["miner_rev_usd"].rolling(365).mean()

    return df


@st.cache_data(ttl=3600)
def get_fng():
    res = requests.get("https://api.alternative.me/fng/?limit=1").json()["data"][0]
    return int(res["value"]), res["value_classification"]


df = get_data()
fng_val, fng_class = get_fng()
latest = df.iloc[-1]

# ---------------------------------------------------------------------------
# SIGNAL LOGIC — thresholds are the commonly cited historical zones for each
# metric. They describe past cycle behavior, not guarantees of future behavior.
# ---------------------------------------------------------------------------

def zone(value, low, high, invert=False):
    """Return (label, color) — green=buy zone, red=sell zone, gray=neutral."""
    if pd.isna(value):
        return "N/A", "gray"
    if not invert:
        if value <= low:
            return "BUY ZONE", "green"
        if value >= high:
            return "SELL ZONE", "red"
        return "NEUTRAL", "gray"
    else:
        if value <= low:
            return "SELL ZONE", "red"
        if value >= high:
            return "BUY ZONE", "green"
        return "NEUTRAL", "gray"


signals = {
    "% vs 200DMA": zone(latest["pct_vs_200ma"], -15, 100),
    "Puell Multiple": zone(latest["puell"], 0.5, 4),
    "RSI (14)": zone(latest["RSI14"], 30, 70),
    "Bollinger %B": zone(latest["BB_pctB"], 0, 1),
    "Fear & Greed": zone(fng_val, 25, 75),
    "Pi Cycle Top": ("SELL ZONE", "red") if latest["MA111"] > latest["MA350x2"] else ("NEUTRAL", "gray"),
}

descriptions = {
    "% vs 200DMA": (
        "Price's distance from its own 200-day moving average, as a %. A simple, "
        "always-available proxy for 'how stretched is this move.' Historically, "
        "readings above +100% (price at 2x its 200DMA) have shown up near cycle "
        "tops; readings below -15% to -20% (price meaningfully under its 200DMA) "
        "have shown up near cycle lows. Cruder than MVRV but never breaks."
    ),
    "Puell Multiple": (
        "Daily miner revenue (USD) divided by its 365-day average. Miners are "
        "structurally forced sellers to cover costs. Below 0.5 = miners under-earning, "
        "selling less/at a loss — historically a strong accumulation zone. Above 4 = "
        "miners in abnormal profit, often coincides with blow-off tops."
    ),
    "RSI (14)": (
        "Standard 14-day momentum oscillator on price. Above 70 = short-term "
        "overbought/exhausted. Below 30 = short-term oversold. Good for timing "
        "entries/exits inside a trend already confirmed by the metrics above — weak "
        "as a standalone macro signal since it can stay overbought for months in a bull run."
    ),
    "Bollinger %B": (
        "Where price sits relative to its 20-day volatility bands. Above 1 = price has "
        "broken above the upper band (statistically stretched, mean-reversion risk). "
        "Below 0 = broken below the lower band (statistically stretched down, bounce risk)."
    ),
    "Fear & Greed": (
        "Aggregate sentiment index (volatility, momentum, social media, surveys, "
        "dominance). Extreme Greed (75+) tends to precede pullbacks. Extreme Fear "
        "(25 or below) has historically been a contrarian buy signal."
    ),
    "Pi Cycle Top": (
        "Fires when the 111-day MA crosses above 2x the 350-day MA. A purely "
        "price-based signal that has flagged every major cycle top since 2013 within "
        "days, with no historical false positives on the top side. It only calls tops, "
        "never bottoms."
    ),
}

# ---------------------------------------------------------------------------
# LAYOUT — summary matrix first
# ---------------------------------------------------------------------------

buy_count = sum(1 for label, _ in signals.values() if label == "BUY ZONE")
sell_count = sum(1 for label, _ in signals.values() if label == "SELL ZONE")

total_signals = len(signals)

if sell_count >= 4:
    verdict, verdict_color = "MAJORITY OF SIGNALS IN SELL ZONE", "red"
elif buy_count >= 4:
    verdict, verdict_color = "MAJORITY OF SIGNALS IN BUY ZONE", "green"
else:
    verdict, verdict_color = "MIXED / NEUTRAL REGIME", "gray"

st.markdown(
    f"<h4 style='color:{verdict_color}'>Composite read: {verdict} "
    f"({buy_count} buy-zone / {sell_count} sell-zone / {total_signals - buy_count - sell_count} neutral)</h4>",
    unsafe_allow_html=True,
)

cols = st.columns(total_signals)
metric_values = {
    "% vs 200DMA": f"{latest['pct_vs_200ma']:+.1f}%",
    "Puell Multiple": f"{latest['puell']:.2f}",
    "RSI (14)": f"{latest['RSI14']:.1f}",
    "Bollinger %B": f"{latest['BB_pctB']:.2f}",
    "Fear & Greed": f"{fng_val} ({fng_class})",
    "Pi Cycle Top": "TRIGGERED" if latest["MA111"] > latest["MA350x2"] else "not triggered",
}
for c, (name, (label, color)) in zip(cols, signals.items()):
    with c:
        st.markdown(f"**{name}**")
        st.markdown(f"<span style='color:{color}'>{label}</span>", unsafe_allow_html=True)
        st.caption(metric_values[name])

st.divider()

# ---------------------------------------------------------------------------
# TIMEFRAME SELECTOR — filters what's displayed, not what's computed.
# All rolling indicators above were already computed on full history, so
# zooming in/out here never distorts MA200/RSI/etc — it just changes the
# viewing window on charts that follow.
# ---------------------------------------------------------------------------

timeframe = st.radio(
    "Chart timeframe",
    options=["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "All"],
    index=3,
    horizontal=True,
)
_days_map = {"1M": 30, "3M": 90, "6M": 182, "1Y": 365, "2Y": 730, "3Y": 1095, "5Y": 1825, "All": None}
_cutoff_days = _days_map[timeframe]
if _cutoff_days is None:
    view_df = df
else:
    cutoff_date = df["date"].max() - pd.Timedelta(days=_cutoff_days)
    view_df = df[df["date"] >= cutoff_date]

st.divider()

# ---------------------------------------------------------------------------
# PRICE + PI CYCLE TOP
# ---------------------------------------------------------------------------

st.subheader("Price, 200MA & Pi Cycle Top")
fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=view_df["date"], y=view_df["close"], name="BTC Price", line=dict(color="#2962FF")))
fig1.add_trace(go.Scatter(x=view_df["date"], y=view_df["MA200"], name="200 DMA", line=dict(color="#FF6D00")))
fig1.add_trace(go.Scatter(x=view_df["date"], y=view_df["MA111"], name="111 DMA", line=dict(color="#AA00FF", dash="dot")))
fig1.add_trace(go.Scatter(x=view_df["date"], y=view_df["MA350x2"], name="350 DMA x2", line=dict(color="#D50000", dash="dot")))
fig1.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0), template="plotly_dark", yaxis_type="log")
st.plotly_chart(fig1, use_container_width=True)
with st.expander("What is Pi Cycle Top / how to read this chart"):
    st.write(descriptions["Pi Cycle Top"])

st.divider()

# ---------------------------------------------------------------------------
# VALUATION ROW
# ---------------------------------------------------------------------------

c1, c2 = st.columns(2)

with c1:
    st.subheader("% vs 200-Day MA")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=view_df["date"], y=view_df["pct_vs_200ma"], name="% vs 200DMA", line=dict(color="#00E676")))
    fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="Stretched high (+100%)")
    fig.add_hline(y=-15, line_dash="dash", line_color="green", annotation_text="Stretched low (-15%)")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("How to read % vs 200DMA"):
        st.write(descriptions["% vs 200DMA"])

with c2:
    st.subheader("Puell Multiple")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=view_df["date"], y=view_df["puell"], name="Puell Multiple", line=dict(color="#FFD600")))
    fig.add_hline(y=4, line_dash="dash", line_color="red", annotation_text="Miner euphoria (4)")
    fig.add_hline(y=0.5, line_dash="dash", line_color="green", annotation_text="Miner capitulation (0.5)")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("How to read Puell Multiple"):
        st.write(descriptions["Puell Multiple"])

st.divider()

# ---------------------------------------------------------------------------
# TECHNICAL / SENTIMENT ROW
# ---------------------------------------------------------------------------

c5, c6 = st.columns(2)

with c5:
    st.subheader("RSI (14)")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=view_df["date"], y=view_df["RSI14"], name="RSI 14", line=dict(color="#FF6D00")))
    fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought (70)")
    fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold (30)")
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("How to read RSI(14)"):
        st.write(descriptions["RSI (14)"])

with c6:
    st.subheader("Bollinger %B")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=view_df["date"], y=view_df["BB_pctB"], name="%B", line=dict(color="#AA00FF")))
    fig.add_hline(y=1, line_dash="dash", line_color="red", annotation_text="Upper band (1)")
    fig.add_hline(y=0, line_dash="dash", line_color="green", annotation_text="Lower band (0)")
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("How to read Bollinger %B"):
        st.write(descriptions["Bollinger %B"])

st.subheader("Market Sentiment")
sc1, sc2 = st.columns([1, 3])
with sc1:
    st.metric(label="Fear & Greed Index", value=fng_val, delta=fng_class, delta_color="off")
with sc2:
    st.write(descriptions["Fear & Greed"])
