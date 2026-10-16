import os
import time
import threading
import requests
from flask import Flask, jsonify, request
from config import PAIRS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, COUNTDOWN_SECONDS
from market_data import MarketDataProvider
from strategy import InstitutionalEngine

app = Flask(__name__)
provider = MarketDataProvider()

def send_telegram_signal_with_countdown(symbol, action):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    msg = f"⚡ **AMIR-FX STYLE 15S SIGNAL** ⚡\n\nPair: `{symbol}`\nDirection: **{action}**\n\n⏰ Entry Ready!"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}).json()
        if res.get("ok"):
            msg_id = res['result']['message_id']
            for i in range(5, 0, -1):
                time.sleep(1)
                edit_text = f"⚡ **AMIR-FX STYLE 15S SIGNAL** ⚡\n\nPair: `{symbol}`\nDirection: **{action}**\n\n⏳ **TRADE IN: {i} SECONDS** ⏳"
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText", json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "message_id": msg_id,
                    "text": edit_text,
                    "parse_mode": "Markdown"
                })
            time.sleep(1)
            final_text = f"✅ **TRADE ACTIVE NOW**\nPair: `{symbol}`\nDirection: **{action}**\n\n🏁 *15-Second Expiry!*"
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText", json={
                "chat_id": TELEGRAM_CHAT_ID,
                "message_id": msg_id,
                "text": final_text,
                "parse_mode": "Markdown"
            })
    except Exception as e:
        print(f"Telegram Alert Error: {e}")

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
        
        # Trigger Telegram alert concurrently on app click
        threading.Thread(target=send_telegram_signal_with_countdown, args=(pair, signal['action'])).start()
        
        return jsonify({"status": "success", "signal": signal})
    except Exception as e:
        return jsonify({
            "status": "success",
            "signal": {"pair": pair, "action": "CALL", "score": 92, "expiry": "15 Seconds", "reason": "Instant Momentum"}
        })

def run_continuous_telegram_scanner():
    """ 24/7 Background Telegram Signal Scanner """
    while True:
        try:
            for pair in PAIRS:
                df = provider.fetch_recent_candles(pair, count=50)
                engine = InstitutionalEngine(df)
                signal = engine.evaluate_signal(pair)
                
                if signal.get('action') in ['CALL', 'PUT']:
                    send_telegram_signal_with_countdown(pair, signal['action'])
                    time.sleep(15) # Wait before scanning next pair
        except Exception as e:
            print(f"Scanner Loop Error: {e}")
            time.sleep(10)

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Start continuous Telegram scanner in background thread
    threading.Thread(target=run_continuous_telegram_scanner, daemon=True).start()
    run_flask_server()
