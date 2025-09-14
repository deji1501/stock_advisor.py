import yfinance as yf
import pandas as pd
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
import os
from dotenv import load_dotenv

# ------------------------------
# Load environment variables
# ------------------------------
load_dotenv()
token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

# ------------------------------
# Telegram Alert Function
# ------------------------------
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("❌ Failed to send Telegram alert:", e)

# ------------------------------
# Your Watchlist
# ------------------------------
symbols = [
    'RR.L',    # Rolls-Royce
    'NVDA',    # NVIDIA
    'AMD',     # AMD
    'LITE',    # Lumentum Holdings
    'MP',      # MP Materials
    'FWRG',    # First Watch Restaurant Group
    'AAPL',    # Apple
    'MSFT',    # Microsoft
    'GOOGL',   # Alphabet
    'META',    # Meta Platforms
    'AVGO'     # Broadcom
]

# Additional companies (tech/AI, banks, energy, defense) — monitored only for dips
dip_only_symbols = [
    'TSLA',  # Tesla
    'PLTR',  # Palantir Technologies
    'SNOW',  # Snowflake
    'CRM',   # Salesforce
    'ORCL',  # Oracle
    'BIDU',  # Baidu
    'INTC',  # Intel
    'JPM',   # JPMorgan Chase
    'BAC',   # Bank of America
    'WFC',   # Wells Fargo
    'GS',    # Goldman Sachs
    'MS',    # Morgan Stanley
    'C',     # Citigroup
    'XOM',   # ExxonMobil
    'CVX',   # Chevron
    'COP',   # ConocoPhillips
    'EOG',   # EOG Resources
    'PSX',   # Phillips 66
    'LMT',   # Lockheed Martin
    'NOC',   # Northrop Grumman
    'RTX',   # Raytheon Technologies
    'GD',    # General Dynamics
    'BA',    # Boeing
    'HII',   # Huntington Ingalls Industries
    'BWXT'   # BWX Technologies
]

# ------------------------------
# Stock Screener from Finviz
# ------------------------------
def get_finviz_symbols(sector_filter):
    url = f"https://finviz.com/screener.ashx?v=111&f=sec_{sector_filter}&ft=4"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    tickers = []
    for row in soup.find_all('a', class_='screener-link-primary'):
        ticker = row.text.strip()
        if ticker.isalpha():
            tickers.append(ticker)
    return tickers

defense_symbols = get_finviz_symbols("defense")
energy_symbols = get_finviz_symbols("energy")
technology_symbols = get_finviz_symbols("technology")
suggest_universe = list(set(defense_symbols + energy_symbols + technology_symbols))

history_period = "1y"

# ------------------------------
# Stock Analysis
# ------------------------------
def analyze_stock(symbol, alert_on_dip_only=False):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period=history_period)
        hist['SMA20'] = hist['Close'].rolling(window=20).mean()
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        if len(hist) < 50:
            return None

        latest = hist.iloc[-1]
        short_signal = "Bullish (Buy)" if latest['SMA20'] > latest['SMA50'] else "Bearish (Wait)"

        info = stock.info
        pe = info.get("trailingPE", "N/A")
        eps = info.get("trailingEps", "N/A")

        if pe != "N/A" and eps and eps > 0:
            if pe < 25:
                long_signal = "Strong fundamentals (Long-term Buy ✅)"
            elif 25 <= pe <= 40:
                long_signal = "Moderate fundamentals (Consider Hold ⚖️)"
            else:
                long_signal = "Growth stock (High risk 🚀)"
        else:
            long_signal = "Weak fundamentals (Hold/Avoid ❌)"

        # DIP detection
        recent_high = hist['Close'].rolling(window=60).max().iloc[-1]
        dip_percent = ((recent_high - latest['Close']) / recent_high) * 100
        dip_alert = None
        if dip_percent >= 10 and "Strong fundamentals" in long_signal:
            dip_alert = f"📉 DIP ALERT: {symbol} is down {dip_percent:.2f}% from recent high. Strong fundamentals — consider buying!"

        if alert_on_dip_only and not dip_alert:
            return None

        return {
            "Symbol": symbol,
            "Short-Term Signal": short_signal,
            "Long-Term Signal": long_signal,
            "PE Ratio": pe,
            "EPS    ": eps,
            "Dip Alert": dip_alert
        }

    except Exception as e:
        return None

# ------------------------------
# Run Analysis and Send Alerts
# ------------------------------
def run_analysis():
    your_results = []
    top_picks = []
    for sym in symbols:
        res = analyze_stock(sym)
        if res:
            your_results.append(res)
            if res['Short-Term Signal'] == "Bullish (Buy)" and "Strong fundamentals" in res['Long-Term Signal']:
                send_telegram_alert(f"📢 Alert: {sym} is a strong buy candidate!\n\n{res}")
                top_picks.append(sym)
            if res.get("Dip Alert"):
                send_telegram_alert(res["Dip Alert"] + f"\n\nDetails:\n{res}")

    for sym in dip_only_symbols:
        res = analyze_stock(sym, alert_on_dip_only=True)
        if res and res.get("Dip Alert"):
            send_telegram_alert(res["Dip Alert"])

    df = pd.DataFrame(your_results)
    df["PE Ratio"] = pd.to_numeric(df["PE Ratio"], errors="coerce").round(2)
    df["EPS    "] = pd.to_numeric(df["EPS    "], errors="coerce").round(2)

    print("\n---------------------")
    print("Your Watchlist Analysis")
    print("---------------------")
    print(df.to_string(index=False))

    # Special 3PM alert
    now = datetime.now()
    if now.hour == 15:
        if top_picks:
            msg = "⏰ 3PM Top Picks:\n" + "\n".join([f"✅ {s}" for s in top_picks])
        else:
            msg = "⏰ 3PM Market Open: No strong buy picks right now."
        summary = "\n".join([str(r) for r in your_results if r['Symbol'] in top_picks])
        send_telegram_alert(msg + "\n\nDetails:\n" + summary)

# ------------------------------
# Loop Every Hour
# ------------------------------
if __name__ == "__main__":
    while True:
        print(f"\n🔁 Running analysis at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        run_analysis()
        time.sleep(3600)  # Run hourly
