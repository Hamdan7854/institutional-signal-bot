import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_signal(signal_data: dict):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Token/Chat ID missing. Skipping Telegram notification.")
        return

    if signal_data["action"] == "NO TRADE":
        return

    emoji = "🟢 CALL (BUY)" if signal_data["action"] == "CALL" else "🔴 PUT (SELL)"
    
    message = (
        f"🚨 <b>INSTITUTIONAL SIGNAL DETECTED</b> 🚨\n\n"
        f"<b>Pair:</b> {signal_data['pair']}\n"
        f"<b>Action:</b> {emoji}\n"
        f"<b>Entry Price:</b> {signal_data['entry_price']}\n"
        f"<b>Expiry Time:</b> {signal_data['expiry']}\n"
        f"<b>Quality Score:</b> {signal_data['score']}/100\n"
        f"<b>Confluence Reason:</b> {signal_data['reason']}\n\n"
        f"⚠️ <i>Execute manually on Pocket Option immediately!</i>"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
        print(f"[Telegram] Signal sent for {signal_data['pair']}")
    except Exception as e:
        print(f"[Telegram Error] {e}")
