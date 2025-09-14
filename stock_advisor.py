import yfinance as yf
import pandas as pd
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime

# ------------------------------
# Telegram Alert Function
# ------------------------------
def send_telegram_alert(message):
    token = "8356307158:AAG4fMh7x60WwP9huz4WG8gAo0VdWog9Xu4"
    chat_id = "7292604517" 
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
    'FWRG',    # First Watch
    'AAPL',    # Apple
    'MSFT',    # Microsoft
    'GOOGL',   # Alphabet
    'META',    # Meta
    'AVGO'     # Broadcom
]

# Dip-only Symbols
dip_only_symbols = [
    'TSLA',  # Tesla
    'PLTR',  # Palantir
    'SNOW',  # Snowflake
    'CRM',   # Salesforce
    'ORCL',  # Oracle
    'BIDU',  # Baidu
    'INTC',  # Intel
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C',  # Banks
    'XOM', 'CVX', 'COP', 'EOG', 'PSX',     # Energy
    'LMT', 'NOC', 'RTX', 'GD', 'BA', 'HII', 'BWXT'  # Defense
]

# ------------------------------
# Get Suggested Stocks from Finviz
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

# ------------------------------
# Analyze Each Stock
# ------------------------------
def analyze_stock(symbol, alert_on_dip_only=False):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1y")
        if len(hist) < 50:
            return None

        hist['SMA20'] = hist['Close'].rolling(window=20).mean()
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
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
           dip_alert = f"📉 DIP ALERT: {symbol} dropped {dip_percent:.2f}% from recent high. Strong fundamentals — consider buying!"

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
# Run Full Analysis and Send Alerts
# ------------------------------
def run_analysis():
    your_results = []
    top_picks = []

    # Your primary watchlist
    for sym in symbols:
        res = analyze_stock(sym)
        if res:
            your_results.append(res)
            if res['Short-Term Signal'] == "Bullish (Buy)" and "Strong fundamentals" in res['Long-Term Signal']:
                msg = f"📢 Alert: {res['Symbol']} is a strong buy candidate!\n\n"
                msg += f"🧾 Details:\n• Short-Term: {res['Short-Term Signal']}\n• Long-Term: {res['Long-Term Signal']}\n"
                msg += f"• PE Ratio: {res['PE Ratio']}\n• EPS: {res['EPS    ']}"
                send_telegram_alert(msg)
                top_picks.append(res['Symbol'])

            if res.get("Dip Alert"):
                dip_msg = res["Dip Alert"] + "\n\n🧾 Details:\n"
                dip_msg += f"• PE Ratio: {res['PE Ratio']}\n• EPS: {res['EPS    ']}"
                send_telegram_alert(dip_msg)

    # Dip-only list
    for sym in dip_only_symbols:
        res = analyze_stock(sym, alert_on_dip_only=True)
        if res and res.get("Dip Alert"):
            dip_msg = res["Dip Alert"] + "\n\n🧾 Details:\n"
            dip_msg += f"• PE Ratio: {res['PE Ratio']}\n• EPS: {res['EPS    ']}"
            send_telegram_alert(dip_msg)

    # DataFrame for display
    df = pd.DataFrame(your_results)
    df["PE Ratio"] = pd.to_numeric(df["PE Ratio"], errors="coerce").round(2)
    df["EPS    "] = pd.to_numeric(df["EPS    "], errors="coerce").round(2)

    print("\n---------------------")
    print("Your Watchlist Analysis")
    print("---------------------")
    print(df.to_string(index=False))

    # 🔔 3PM Summary Alert
    now = datetime.now()
    if now.hour == 15:
        if top_picks:
            msg = "⏰ 3PM Top Picks:\n" + "\n".join([f"✅ {s}" for s in top_picks])
        else:
            msg = "⏰ 3PM Market Open: No strong buy picks right now."
        send_telegram_alert(msg)

# ------------------------------
# Loop every hour
# ------------------------------
if __name__ == "__main__":
    while True:
        print(f"\n⏰ Running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        run_analysis()
        print("Waiting 1 hour until next run...")
        time.sleep(3600)

