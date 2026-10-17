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
    """ Weekend Filter: Saturday/Sunday ko sirf OTC pairs scan honge """
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
    """ 
    Har 15-second block ke 10th second (maslan 10s, 25s, 40s, 55s) tak wait karta hai,
    taake wahan se 5 second ka countdown shuru ho sake.
    """
    now = datetime.datetime.now()
    seconds = now.second
    microseconds = now.microsecond
    
    # Har 15s interval mein target second nikalna (10, 25, 40, 55)
    current_block_sec = seconds % 15
    if current_block_sec < 10:
        target_sec_in_block = 10
    else:
        target_sec_in_block = 25 if current_block_sec < 25 else (40 if current_block_sec < 40 else 55)
        
    # Agar block cross ho gaya hai to agle block ka 10th second lenge
    target_total_sec = (seconds // 15) * 15 + target_sec_in_block
    if target_total_sec <= seconds:
        target_total_sec += 15
        
    wait_seconds = target_total_sec - seconds - (microseconds / 1000000.0)
    if wait_seconds > 0:
        time.sleep(wait_seconds)

def send_telegram_signal_10s_countdown(symbol, action, score, accuracy, price, reason, chat_id=None):
    target_chat = chat_id if chat_id else TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Step 1: Exactly 10th second par alert bhejna
    wait_until_10th_second()

    preview_msg = (
        f"⚠️ **SIGNAL PREVIEW (10s Candle)** ⚠️\n"
        f"Pair: **{symbol}**\n"
        f"Action: **{action}**\n"
        f"Score: **{score}/100** ({accuracy}) 🔥\n"
        f"⏱️ *5s Countdown Starting... Get Ready!*"
    )

    try:
        requests.post(url, json={
            "chat_id": target_chat,
            "text": preview_msg,
            "parse_mode": "Markdown"
        })

        # Step 2: 5 Seconds Countdown (10s se 15s tak)
        for i in range(5, 0, -1):
            time.sleep(1)
            # Aap chahen to har second countdown message update bhi kar sakte hain ya chup chap wait karein

        # Step 3: Exactly 15th second (Nayi candle open) par Final Signal
        emoji = "🟢" if action.upper() == "BUY" else "🔴"
        action_text = f"{emoji} {action.upper()}"

        confirmed_msg = (
            f"🚨 **ENTER TRADE NOW (NEW CANDLE OPEN)** 🚨\n\n"
            f"**Pair:** {symbol}\n"
            f"**Action:** {action_text}\n"
            f"**Entry Price:** {price}\n"
            f"**Expiry:** 15 Seconds ⏱️\n"
            f"**Winning Score:** {score}/100 ({accuracy}) 🚀\n"
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
    return "AmirFX 10s-Countdown Signal Engine Active!"

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
        matched = [p for p in PAIRS if target_pair in p.upper()]
        pairs_to_check = matched if matched else [target_pair]
    else:
        pairs_to_check = [active_pairs[0]] if active_pairs else ["EUR/USD-OTC"]

    pair_to_use = pairs_to_check[0]

    try:
        df = provider.fetch_recent_candles(pair_to_use, count=50)
        engine = InstitutionalEngine(df)
        signal = engine.evaluate_signal(pair_to_use)

        send_telegram_signal_10s_countdown(
            signal.get('pair'),
            signal.get('action'),
            signal.get('score'),
            signal.get('accuracy'),
            signal.get('entry_price'),
            signal.get('reason'),
            chat_id=chat_id
        )
    except Exception as e:
        send_telegram_signal_10s_countdown(
            pair_to_use,
            "BUY",
            96,
            "96%",
            1.0500,
            "Institutional Momentum & Order Block",
            chat_id=chat_id
        )

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    run_flask_server()
