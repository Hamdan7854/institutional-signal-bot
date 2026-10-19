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
            if "_OTC" in pair or "_otc" in pair.lower():
                scannable.append(pair)
        else:
            if "_OTC" not in pair and "_otc" not in pair.lower():
                scannable.append(pair)
    return scannable

def wait_until_1m_countdown():
    # Wait until the 50th second of the current minute so preview starts, and execution hits at 00th second
    now = datetime.datetime.now()
    seconds = now.second
    microseconds = now.microsecond
    
    if seconds >= 50:
        target_wait = (60 - seconds) + 50 - (microseconds / 1000000.0)
    else:
        target_wait = 50 - seconds - (microseconds / 1000000.0)
        
    if target_wait > 0:
        time.sleep(target_wait)

def send_telegram_signal_1m_countdown(symbol, chat_id=None):
    target_chat = chat_id if chat_id else TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Step 1: Wait until 50th second of the minute
    wait_until_1m_countdown()
    
    # Step 2: Fetch data & evaluate 1-minute signal
    try:
        df = provider.get_historical_data(symbol)
        engine = InstitutionalEngine(df)
        signal = engine.evaluate_signal(symbol if df is None or df.empty else df)
    except Exception as e:
        engine = InstitutionalEngine()
        signal = engine.evaluate_signal(symbol)
        
    action = signal.get('action', 'HOLD')
    score = signal.get('score', 75)
    raw_price = signal.get('entry_price', 1.0)
    price = round(raw_price, 5)  # Clean 5-digit real forex format
    reason = signal.get('reason', '1m Technical Confluence')
    
    emoji = "🟢" if action.upper() == "BUY" else "🔴"
    action_text = f"{emoji} {action.upper()}"
    
    # Step 3: Preview Alert at 50th Second
    preview_msg = (
        f"⚠️ **1m SIGNAL PREVIEW** ⚠️\n\n"
        f"📌 **Pair:** {symbol}\n"
        f"🎯 **Direction:** {action_text}\n"
        f"🔥 **Dynamic Score:** {score}/100 ({score}%)\n"
        f"💡 **Reason:** {reason}\n\n"
        f"⏱️ **10s Countdown to 1-Minute Candle Open... Get Ready!**"
    )
    
    try:
        requests.post(url, json={
            "chat_id": target_chat,
            "text": preview_msg,
            "parse_mode": "Markdown"
        })
    except:
        pass
        
    # Step 4: 10 Seconds Countdown to exact minute close/open
    time.sleep(10)
    
    # Step 5: Final Execution Signal at exact 00th second (1-Minute Expiry)
    confirmed_msg = (
        f"🚨 **ENTER 1m TRADE NOW (CANDLE OPEN)** 🚨\n\n"
        f"📌 **Pair:** {symbol}\n"
        f"🎯 **Action:** {action_text}\n"
        f"💵 **Entry Price:** {price}\n"
        f"⏱️ **Expiry:** 1 Minute ⏱️\n"
        f"🚀 **Dynamic Score:** {score}/100 ({score}%)\n"
        f"💡 **Reason:** {reason}\n\n"
        f"⚡ **CLICK {action.upper()} RIGHT NOW!**"
    )
    
    try:
        requests.post(url, json={
            "chat_id": target_chat,
            "text": confirmed_msg,
            "parse_mode": "Markdown"
        })
    except Exception as e:
        print(f"Telegram Error: {e}")

@app.route('/')
def home():
    return "1-Minute Real Forex Signal Engine Active on Render!"

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        if 'message' in data:
            message = data['message']
            text = message.get('text', '').strip()
            chat_id = message.get('chat', {}).get('id')
            
            if text.startswith('/signal') or text.startswith('/getsignal'):
                parts = text.split()
                target_pair = parts[1].upper() if len(parts) > 1 else "EUR/USD"
                threading.Thread(target=send_telegram_signal_1m_countdown, args=(target_pair, chat_id)).start()
                
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": time.time()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
