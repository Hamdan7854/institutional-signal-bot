import os
import time
import requests
import threading
from flask import Flask

from config import PAIRS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, COUNTDOWN_SECONDS
from market_data import MarketDataProvider
from strategy import InstitutionalEngine

# ------------------------------------------------------------------
# 1. Dummy Flask Web Server (Render Web Service ko 24/7 Active Rakhne Ke Liye)
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Institutional 24/7 Signal Engine is Running Live on Render!"

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------------
# 2. Aapka Telegram Messaging Logic
# ------------------------------------------------------------------
def send_telegram_msg(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram Warning] Tokens Missing!")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            return True
        else:
            print(f"[Telegram Error] Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"[Telegram Exception] {e}")
        return False

# ------------------------------------------------------------------
# 3. Aapka Main Institutional Scanner (24/7 Infinite Loop Ke Saath)
# ------------------------------------------------------------------
def run_institutional_scanner():
    print("🚀 Starting Institutional Signal & Backtesting Engine...")
    
    # Startup Confirmation Message on Telegram
    send_telegram_msg("🟢 <b>SYSTEM ONLINE:</b> Pocket Option Institutional Scanner deployed & active on Render 24/7!")
    
    provider = MarketDataProvider()

    # Continuous 24/7 Loop
    while True:
        try:
            for pair in PAIRS:
                df = provider.fetch_recent_candles(pair, count=100)
                engine = InstitutionalEngine(df)
                signal = engine.evaluate_signal(pair)

                # Safe extraction to prevent KeyError
                action = signal.get("action", "HOLD")
                score = signal.get("score", signal.get("quality_score", 0))
                entry_price = signal.get("entry_price", "N/A")
                expiry = signal.get("expiry", "60 Seconds")
                reason = signal.get("reason", "N/A")

                print(f"[{pair}] Action: {action} | Score: {score}")

                if action in ["CALL", "PUT"]:
                    print(f"⚠️ [ALERT] Valid setup found for {pair} ({action}). Sending Countdown...")
                    
                    # Countdown Alert
                    warning_msg = (
                        f"⚠️ <b>SIGNAL PREVIEW & COUNTDOWN ALERT</b> ⚠️\n"
                        f"<b>Pair:</b> {pair}\n"
                        f"<b>Expected Action:</b> {action}\n"
                        f"<b>Countdown:</b> {COUNTDOWN_SECONDS}s - 4, 3, 2, 1...\n"
                        f"<i>Get ready on Pocket Option. Signal finalizing!</i>"
                    )
                    send_telegram_msg(warning_msg)
                    time.sleep(COUNTDOWN_SECONDS)

                    # Final Confirmed Signal Alert
                    emoji = "🟢 CALL (BUY)" if action == "CALL" else "🔴 PUT (SELL)"
                    final_msg = (
                        f"🚨 <b>INSTITUTIONAL SIGNAL CONFIRMED</b> 🚨\n\n"
                        f"<b>Pair:</b> {pair}\n"
                        f"<b>Action:</b> {emoji}\n"
                        f"<b>Entry Price:</b> {entry_price}\n"
                        f"<b>Expiry:</b> {expiry}\n"
                        f"<b>Quality Score:</b> {score}/100\n"
                        f"<b>Reason:</b> {reason}\n\n"
                        f"⚠️ <i>Execute immediately on current candle open!</i>"
                    )
                    
                    if send_telegram_msg(final_msg):
                        print(f"✅ [SUCCESS] Confirmed signal sent to Telegram for {pair} ({action})!")
                    else:
                        print(f"❌ [FAILED] Could not send signal to Telegram for {pair}!")

        except Exception as e:
            print(f"[Scanner Loop Error] {e}")

        # Continuous Scanning (Har 30 seconds baad market scan karega)
        time.sleep(30)

# ------------------------------------------------------------------
# 4. Execution Entry Point
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Flask Web Server ko alag Thread mein chalayein
    threading.Thread(target=run_flask_server, daemon=True).start()

    # Aapka Scanner Loop Main Thread mein 24/7 chalega
    run_institutional_scanner()
