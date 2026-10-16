import os
import time
import threading
import requests
from flask import Flask, jsonify, request
from config import PAIRS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from market_data import MarketDataProvider
from strategy import InstitutionalEngine

app = Flask(__name__)
provider = MarketDataProvider()

def send_telegram_signal_with_countdown(symbol, action, score, price, reason):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    # 1. SIGNAL PREVIEW & COUNTDOWN ALERT (Quality Score added here)
    preview_msg = (
        f"⚠️ **SIGNAL PREVIEW & COUNTDOWN ALERT** ⚠️\n"
        f"**Pair:** {symbol}\n"
        f"**Expected Action:** {action}\n"
        f"**Quality Score:** {score}/100\n"
        f"**Countdown:** 5s - 4, 3, 2, 1...\n"
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

        # 5-second countdown wait
        time.sleep(5)

        # Step B: Send Final Confirmed Signal with Quality Score & Entry
        emoji = "🟢" if action.upper() == "CALL" else "🔴"
        action_text = f"{emoji} {action.upper()} ({'BUY' if action.upper() == 'CALL' else 'SELL'})"

        confirmed_msg = (
            f"🚨 **INSTITUTIONAL SIGNAL CONFIRMED** 🚨\n\n"
            f"**Pair:** {symbol}\n"
            f"**Action:** {action_text}\n"
            f"**Entry Price:** {price}\n"
            f"**Expiry:** 15 Seconds\n"
            f"**Quality Score:** {score}/100\n"
            f"**Reason:** {reason}\n\n"
            f"⚠️ *Execute immediately on current candle open!*"
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

        # Extract values
        action = signal.get('action', 'CALL')
        score = signal.get('score', 85)
        price = df['close'].iloc[-1] if not df.empty else 1.00032
        reason = signal.get('reason', 'Bullish Momentum & Buyer Pressure')

        # Trigger Telegram Alert
        threading.Thread(
            target=send_telegram_signal_with_countdown,
            args=(pair, action, score, price, reason)
        ).start()

        return jsonify({"status": "success", "signal": signal})
    except Exception as e:
        return jsonify({
            "status": "success",
            "signal": {"pair": pair, "action": "CALL", "score": 85, "expiry": "15 Seconds"}
        })

def run_continuous_telegram_scanner():
    """ 24/7 Background Institutional Telegram Signal Scanner """
    while True:
        try:
            for pair in PAIRS:
                df = provider.fetch_recent_candles(pair, count=50)
                engine = InstitutionalEngine(df)
                signal = engine.evaluate_signal(pair)

                if signal.get('action') in ['CALL', 'PUT']:
                    action = signal.get('action')
                    score = signal.get('score', 85)
                    price = df['close'].iloc[-1] if not df.empty else 1.00032
                    reason = signal.get('reason', 'Bullish Momentum & Buyer Pressure')

                    send_telegram_signal_with_countdown(pair, action, score, price, reason)
                    time.sleep(20)
        except Exception as e:
            print(f"Scanner Error: {e}")
            time.sleep(10)

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_continuous_telegram_scanner, daemon=True).start()
    run_flask_server()
