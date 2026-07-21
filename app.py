import streamlit as st

st.set_page_config(page_title="Investment Dashboard", layout="wide")

btc_macro_page = st.Page("pages/btc_macro.py", title="BTC Macro Dashboard", icon="📊", default=True)

pg = st.navigation([btc_macro_page])
pg.run()
