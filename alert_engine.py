import os
import requests
import yfinance as yf
import pandas as pd

# Load credentials from GitHub environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def check_signal(ticker, name):
    # Fetch 60 days of daily history to compute the 20-day MA
    df = yf.download(ticker, period="60d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
        
    df['MA20'] = df['Close'].rolling(window=20).mean()
    
    # Compare yesterday vs today
    yesterday = df.iloc[-2]
    today = df.iloc[-1]
    
    # Crossover Logic
    if yesterday['Close'] < yesterday['MA20'] and today['Close'] > today['MA20']:
        return f"📈 *{name}* crossed ABOVE its 20-day Moving Average. Signal changed to: *BUY*"
    elif yesterday['Close'] > yesterday['MA20'] and today['Close'] < today['MA20']:
        return f"📉 *{name}* crossed BELOW its 20-day Moving Average. Signal changed to: *SELL*"
    
    return None

if __name__ == "__main__":
    messages = []
    
    # Check BBCA.JK
    bbca_msg = check_signal("BBCA.JK", "Bank Central Asia (BBCA)")
    if bbca_msg: messages.append(bbca_msg)
        
    # Check Bitcoin
    btc_msg = check_signal("BTC-USD", "Bitcoin (BTC)")
    if btc_msg: messages.append(btc_msg)
        
    # Push alert if any signals changed
    if messages:
        final_text = "🔔 *Market Signal Alert*\n\n" + "\n\n".join(messages)
        send_telegram_msg(final_text)
        print("Alert triggered and sent via Telegram.")
    else:
        print("Market status unchanged. No alerts triggered today.")
        send_telegram_msg("🚀 *System Online!* Your market alert pipeline is active.")
