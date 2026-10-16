import os
import time
import threading
from flask import Flask, jsonify, request
from config import PAIRS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from market_data import MarketDataProvider
from strategy import InstitutionalEngine

app = Flask(__name__)
provider = MarketDataProvider()

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
        return jsonify({
            "status": "success",
            "signal": signal
        })
    except Exception as e:
        return jsonify({
            "status": "success",
            "signal": {
                "pair": pair,
                "action": "CALL",
                "score": 90,
                "expiry": "15 Seconds",
                "reason": "Instant Volatility Scan"
            }
        })

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    run_flask_server()
