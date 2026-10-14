import os
import time
import requests
import threading
from flask import Flask

from config import PAIRS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, COUNTDOWN_SECONDS
from market_data import MarketDataProvider
from strategy import InstitutionalEngine

# -------------------------------------------------------------------
# 1. Dummy Flask Web Server (Render Web Service ko 24/7 Active Rakhne Ke Liye)
# -------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Institutional 24/7 Signal Engine is Running Live on Render!"

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# -------------------------------------------------------------------
# 2. Aapka Telegram Messaging Logic
# -------------------------------------------------------------------
def send_telegram_msg(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram Warning] Tokens Missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[Telegram Exception] {e}")

# -------------------------------------------------------------------
# 3. Aapka Main Institutional Scanner (24/7 Infinite Loop Ke Saath)
# -------------------------------------------------------------------
def run_institutional_scanner():
    print("🚀 Starting Institutional Signal & Backtesting Engine...")
    provider = MarketDataProvider()

    # Continuous 24/7 Loop
    while True:
        try:
            for pair in PAIRS:
                df = provider.fetch_recent_candles(pair, count=100)
                engine = InstitutionalEngine(df)
                signal = engine.evaluate_signal(pair)

                print(f"[{pair}] Action: {signal['action']} | Score: {signal.get('score', 0)} | Reason: {signal['reason']}")

                if signal["action"] in ["CALL", "PUT"]:
                    # Countdown Alert
                    warning_msg = (
                        f"⚠️ <b>SIGNAL PREVIEW & COUNTDOWN ALERT</b> ⚠️\n"
                        f"<b>Pair:</b> {pair}\n"
                        f"<b>Expected Action:</b> {signal['action']}\n"
                        f"<b>Countdown:</b> {COUNTDOWN_SECONDS} → 4 → 3 → 2 → 1 Sec\n"
                        f"<i>Get ready on Pocket Option. Signal finalizing on candle close...</i>"
                    )
                    send_telegram_msg(warning_msg)
                    time.sleep(COUNTDOWN_SECONDS)

                    # Final Confirmed Signal Alert
                    emoji = "🟢 CALL (BUY)" if signal["action"] == "CALL" else "🔴 PUT (SELL)"
                    final_msg = (
                        f"🚨 <b>INSTITUTIONAL SIGNAL CONFIRMED</b> 🚨\n\n"
                        f"<b>Pair:</b> {pair}\n"
                        f"<b>Action:</b> {emoji}\n"
                        f"<b>Entry Price:</b> {signal['entry_price']}\n"
                        f"<b>Expiry:</b> {signal['expiry']}\n"
                        f"<b>Quality Score:</b> {signal['score']}/100\n\n"
                        f"📌 <b>Reason:</b> {signal['reason']}\n"
                        f"⚠️ <i>Execute immediately on current candle open!</i>"
                    )
                    send_telegram_msg(final_msg)

        except Exception as e:
            print(f"[Scanner Loop Error] {e}")

        # Continuous Scanning (Har 30 seconds baad market scan karega)
        time.sleep(30)

# -------------------------------------------------------------------
# 4. Execution Entry Point
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Flask Web Server ko alag Thread mein chalayein
    threading.Thread(target=run_flask_server, daemon=True).start()

    # Aapka Scanner Loop Main Thread mein 24/7 chalega
    run_institutional_scanner()
