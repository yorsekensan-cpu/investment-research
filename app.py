import streamlit as st

st.set_page_config(page_title="Investment Dashboard", layout="wide")

# Register pages with Home as the default landing view
home_page = st.Page("pages/home.py", title="Command Center", icon="🏠", default=True)
btc_macro_page = st.Page("pages/btc_macro.py", title="BTC Macro Dashboard", icon="📊")
bbca_matrix_page = st.Page("pages/bbca_matrix.py", title="BBCA Equity Matrix", icon="🏦")
allocator_page = st.Page("pages/portfolio_allocator.py", title="Portfolio Allocator", icon="⚖️")

pg = st.navigation([home_page, btc_macro_page, bbca_matrix_page, allocator_page])
pg.run()
