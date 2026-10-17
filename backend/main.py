import os
import time
import datetime
import threading
import requests
from flask import Flask, jsonify, request
from config import PAIRS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from market_data import MarketDataProvider
from strategy import InstitutionalEngine

app = Flask(__name__)
provider = MarketDataProvider()

def get_scannable_pairs():
    """ Automatically filters pairs based on Weekend vs Weekday """
    # Saturday = 5, Sunday = 6
    is_weekend = datetime.datetime.now().weekday() in [5, 6]
    scannable = []

    for pair in PAIRS:
        if is_weekend:
            # Weekend पर सिर्फ OTC Pairs allow होंगे
            if "-OTC" in pair or "_otc" in pair.lower():
                scannable.append(pair)
        else:
            # Weekdays पर सिर्फ Live Forex Pairs allow होंगे
            if "-OTC" not in pair and "_otc" not in pair.lower():
                scannable.append(pair)

    return scannable

def send_telegram_signal_with_countdown(symbol, action, score, accuracy, price, reason):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    # 1. SIGNAL PREVIEW & COUNTDOWN ALERT
    preview_msg = (
        f"⚠️ **SIGNAL PREVIEW & COUNTDOWN ALERT** ⚠️\n"
        f"Pair: **{symbol}**\n"
        f"Expected Action: **{action}**\n"
        f"Quality Score: **{score}/100**\n"
        f"Estimated Accuracy: **{accuracy}**\n"
        f"Countdown: **5s - 4, 3, 2, 1...**\n"
        f"_Get ready on Pocket Option. Signal finalizing!_"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        # Step A: Send Preview Message
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": preview_msg,
            "parse_mode": "Markdown"
        })

        # 5-Second Countdown Wait
        time.sleep(5)

        # Step B: Send Final Confirmed Signal
        emoji = "🟢" if action.upper() == "CALL" else "🔴"
        action_text = f"{emoji} {action.upper()} ({'BUY' if action.upper() == 'CALL' else 'SELL'})"

        confirmed_msg = (
            f"🚨 **INSTITUTIONAL SIGNAL CONFIRMED** 🚨\n\n"
            f"**Pair:** {symbol}\n"
            f"**Action:** {action_text}\n"
            f"**Entry Price:** {price}\n"
            f"**Expiry:** 15 Seconds ⏱️\n"
            f"**Quality Score:** {score}/100\n"
            f"**Signal Accuracy:** {accuracy} 🔥\n"
            f"**Reason:** {reason}\n\n"
            f"⚡ *Execute immediately on current 15s candle open!*"
        )

        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": confirmed_msg,
            "parse_mode": "Markdown"
        })

    except Exception as e:
        print(f"Telegram Signal Send Error: {e}")

@app.route('/')
def home():
    return "Institutional 15s Signal Engine Active!"

@app.route('/api/signal', methods=['GET', 'POST'])
def get_instant_signal():
    pair = request.args.get('pair', 'EUR/USD-OTC')
    try:
        df = provider.fetch_recent_candles(pair, count=50)
        engine = InstitutionalEngine(df)
        signal = engine.evaluate_signal(pair)

        if signal.get('action') in ['CALL', 'PUT']:
            threading.Thread(
                target=send_telegram_signal_with_countdown,
                args=(
                    pair, 
                    signal.get('action'), 
                    signal.get('score'), 
                    signal.get('accuracy'), 
                    signal.get('entry_price'), 
                    signal.get('reason')
                )
            ).start()

        return jsonify({"status": "success", "signal": signal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def run_continuous_telegram_scanner():
    """ 24/7 Background Institutional Telegram Signal Scanner """
    print("Starting Continuous Telegram Scanner...")
    while True:
        try:
            active_pairs = get_scannable_pairs()
            print(f"Scanning Pairs ({len(active_pairs)} Active): {active_pairs}")

            for pair in active_pairs:
                df = provider.fetch_recent_candles(pair, count=50)
                if df is None or df.empty:
                    continue

                engine = InstitutionalEngine(df)
                signal = engine.evaluate_signal(pair)

                # Send ONLY High-Quality Signals (Score >= 85)
                if signal.get('action') in ['CALL', 'PUT'] and signal.get('score', 0) >= 85:
                    send_telegram_signal_with_countdown(
                        pair,
                        signal.get('action'),
                        signal.get('score'),
                        signal.get('accuracy'),
                        signal.get('entry_price'),
                        signal.get('reason')
                    )
                    # Signal bhejney ke baad wait taake same candle par multiple signals na ayein
                    time.sleep(20)

            time.sleep(5)  # 5 Seconds gap between full market scans
        except Exception as e:
            print(f"Scanner Error: {e}")
            time.sleep(10)

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_continuous_telegram_scanner, daemon=True).start()
    run_flask_server()
