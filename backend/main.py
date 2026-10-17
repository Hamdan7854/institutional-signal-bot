import os
import time
import datetime
import threading
import requests
from flask import Flask, jsonify, request
from config import PAIRS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, MIN_QUALITY_SCORE
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

def send_telegram_signal_with_countdown(symbol, action, score, accuracy, price, reason, chat_id=None):
    target_chat = chat_id if chat_id else TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Step 1: Preview Alert (Buy/Sell, Quality Score, Pair, and Countdown)
    preview_msg = (
        f"⚠️ **SIGNAL PREVIEW & COUNTDOWN ALERT** ⚠️\n"
        f"Pair: **{symbol}**\n"
        f"Expected Action: **{action}**\n"
        f"Quality Score: **{score}/100**\n"
        f"Winning Accuracy: **{accuracy}** 🔥\n"
        f"Countdown: **5s - 4, 3, 2, 1...**\n"
        f"_Get ready on Pocket Option. Signal finalizing!_"
    )

    try:
        requests.post(url, json={
            "chat_id": target_chat,
            "text": preview_msg,
            "parse_mode": "Markdown"
        })

        # 5 seconds countdown wait
        time.sleep(5)

        # Step 2: Final Confirmed Trade Alert
        emoji = "🟢" if action.upper() == "CALL" else "🔴"
        action_text = f"{emoji} {action.upper()} ({'BUY' if action.upper() == 'CALL' else 'SELL'})"

        confirmed_msg = (
            f"🚨 **INSTITUTIONAL SIGNAL CONFIRMED** 🚨\n\n"
            f"**Pair:** {symbol}\n"
            f"**Action:** {action_text}\n"
            f"**Entry Price:** {price}\n"
            f"**Expiry:** 15 Seconds ⏱️\n"
            f"**Quality Score:** {score}/100\n"
            f"**Winning Accuracy:** {accuracy} 🚀\n"
            f"**Reason:** {reason}\n\n"
            f"⚡ *Execute trade immediately on 15s candle open!*"
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
    return "AmirFX Style Command Signal Bot Active!"

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """ Telegram bot commands handle karne ke liye webhook """
    try:
        data = request.get_json()
        if "message" in data:
            message = data["message"]
            text = message.get("text", "").strip()
            chat_id = message.get("chat", {}).get("id")

            # Agar user /signal ya /getsignal likhe
            if text.startswith("/signal") or text.startswith("/getsignal"):
                parts = text.split()
                target_pair = None
                if len(parts) > 1:
                    target_pair = parts[1].upper() # e.g. /signal EUR/USD-OTC

                threading.Thread(target=handle_user_command, args=(chat_id, target_pair)).start()

        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def handle_user_command(chat_id, target_pair):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    active_pairs = get_scannable_pairs()

    if target_pair:
        # Agar user ne specific pair manga hai
        if target_pair in PAIRS or any(target_pair in p for p in PAIRS):
            # Match exact or partial
            matched = [p for p in PAIRS if target_pair in p]
            pairs_to_check = matched if matched else [target_pair]
        else:
            requests.post(url, json={
                "chat_id": chat_id,
                "text": f"⚠️ Pair '{target_pair}' valid list mein mojood nahi hai!"
            })
            return
    else:
        pairs_to_check = active_pairs

    found = False
    for pair in pairs_to_check:
        try:
            df = provider.fetch_recent_candles(pair, count=50)
            if df is None or df.empty:
                continue

            engine = InstitutionalEngine(df)
            signal = engine.evaluate_signal(pair)

            # Data staleness / validity check & instant signal trigger
            if signal.get('action') in ['CALL', 'PUT']:
                send_telegram_signal_with_countdown(
                    pair,
                    signal.get('action'),
                    signal.get('score'),
                    signal.get('accuracy'),
                    signal.get('entry_price'),
                    signal.get('reason'),
                    chat_id=chat_id
                )
                found = True
                break
        except Exception as e:
            print(f"Error checking {pair}: {e}")

    if not found:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": "⚠️ Is waqt is pair par 15s scalping setup match nahi ho raha. Thori der baad dobara command dein!"
        })

def run_continuous_scanner():
    while True:
        try:
            active_pairs = get_scannable_pairs()
            for pair in active_pairs:
                df = provider.fetch_recent_candles(pair, count=50)
                if df is None or df.empty:
                    continue
                engine = InstitutionalEngine(df)
                signal = engine.evaluate_signal(pair)
                if signal.get('action') in ['CALL', 'PUT'] and signal.get('score', 0) >= MIN_QUALITY_SCORE:
                    send_telegram_signal_with_countdown(
                        pair,
                        signal.get('action'),
                        signal.get('score'),
                        signal.get('accuracy'),
                        signal.get('entry_price'),
                        signal.get('reason')
                    )
                    time.sleep(30)
            time.sleep(10)
        except Exception as e:
            print(f"Scanner Error: {e}")
            time.sleep(10)

def run_flask_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_continuous_scanner, daemon=True).start()
    run_flask_server()
