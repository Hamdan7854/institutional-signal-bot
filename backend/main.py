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
    is_weekend = datetime.datetime.now().weekday() in [5, 6]
    scannable = []
    for pair in PAIRS:
        if is_weekend:
            if "-OTC" in pair or "_otc" in pair.lower():
                scannable.append(pair)
        else:
            if "-OTC" not in pair and "_otc" not in pair.lower():
                scannable.append(pair)
    return scannable

def wait_until_10th_second():
    now = datetime.datetime.now()
    seconds = now.second
    microseconds = now.microsecond
    
    current_block_sec = seconds % 15
    if current_block_sec < 10:
        target_sec_in_block = 10
    else:
        target_sec_in_block = 25 if current_block_sec < 25 else (40 if current_block_sec < 40 else 55)
        
    target_total_sec = (seconds // 15) * 15 + target_sec_in_block
    if target_total_sec <= seconds:
        target_total_sec += 15
        
    wait_seconds = target_total_sec - seconds - (microseconds / 1000000.0)
    if wait_seconds > 0:
        time.sleep(wait_seconds)

def send_telegram_signal_10s_countdown(symbol, chat_id=None):
    target_chat = chat_id if chat_id else TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Step 1: Wait until exact 10th second of the candle block
    wait_until_10th_second()

    # Step 2: Fetch live WebSocket stream feed data
    try:
        df = provider.fetch_recent_candles(symbol, count=50)
        engine = InstitutionalEngine(df)
        signal = engine.evaluate_signal(symbol)
    except Exception:
        engine = InstitutionalEngine(None)
        signal = engine.evaluate_signal(symbol)

    action = signal.get('action')
    score = signal.get('score')
    accuracy = signal.get('accuracy')
    price = signal.get('entry_price')
    reason = signal.get('reason')

    emoji = "🟢" if action.upper() == "BUY" else "🔴"
    action_text = f"{emoji} {action.upper()}"

    # Step 3: Preview Alert at 10th Second
    preview_msg = (
        f"⚠️ **10s SIGNAL PREVIEW** ⚠️\n\n"
        f"**Pair:** {symbol}\n"
        f"**Direction:** {action_text}\n"
        f"**Dynamic Score:** {score}/100 ({accuracy}) 🔥\n"
        f"**Reason:** {reason}\n\n"
        f"⏱️ *5s Countdown Starting... Get Ready!*"
    )

    try:
        requests.post(url, json={
            "chat_id": target_chat,
            "text": preview_msg,
            "parse_mode": "Markdown"
        })

        # Step 4: 5 Seconds Countdown
        time.sleep(5)

        # Step 5: Final Execution Signal at 00s (New Candle Open)
        confirmed_msg = (
            f"🚨 **ENTER TRADE NOW (CANDLE OPEN)** 🚨\n\n"
            f"**Pair:** {symbol}\n"
            f"**Action:** {action_text}\n"
            f"**Entry Price:** {price}\n"
            f"**Expiry:** 15 Seconds ⏱️\n"
            f"**Dynamic Score:** {score}/100 ({accuracy}) 🚀\n"
            f"**Reason:** {reason}\n\n"
            f"⚡ *CLICK {action.upper()} RIGHT NOW!*"
        )

        requests.post(url, json={
            "chat_id": target_chat,
            "text": confirmed_msg,
            "parse_mode": "Markdown"
        })
    except Exception as e:
        print(f"Telegram Error: {e}")

@app.route('/')
def home():
    return "WebSocket Live Streamer Engine Active on Render!"

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        if "message" in data:
            message = data["message"]
            text = message.get("text", "").strip()
            chat_id = message.get("chat", {}).get("id")

            if text.startswith("/signal") or text.startswith("/getsignal"):
                parts = text.split()
                target_pair = parts[1].upper() if len(parts) > 1 else None
                threading.Thread(target=handle_user_command, args=(chat_id, target_pair)).start()

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def handle_user_command(chat_id, target_pair=None):
    active_pairs = get_scannable_pairs()

    if target_pair:
        matched = [p for p in PAIRS if target_pair in p.org() if target_pair in p.upper()]
        pairs_to_check = matched if matched else [target_pair]
    else:
        pairs_to_check = [active_pairs[0]] if active_pairs else ["EUR/USD-OTC"]

    pair_to_use = pairs_to_check[0]
    threading.Thread(target=send_telegram_signal_10s_countdown, args=(pair_to_use, chat_id)).start()

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    run_flask_server()
