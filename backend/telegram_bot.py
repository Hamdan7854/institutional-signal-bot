"""Telegram: message bhejna + commands sunna (/status, /edge, /pause, /resume, /help). Sirf TELEGRAM_BOT_CHAT_ID wali chat ki commands manzoor hoti hain."""
import threading
import time
import requests
import config


def _get_token():
    return getattr(config, "TELEGRAM_BOT_TOKEN", None) or getattr(config, "TELEGRAM_TOKEN", None)


def _get_chat_id():
    return getattr(config, "TELEGRAM_BOT_CHAT_ID", None) or getattr(config, "TELEGRAM_CHAT_ID", None)


def send(text: str):
    token = _get_token()
    chat_id = _get_chat_id()
    if not (token and chat_id):
        print("[TELEGRAM-OFF]", text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text}, timeout=10)
    except requests.RequestException as e:
        print("telegram error:", e)


def start_listener(handlers):
    """handlers: {'/status': callable -> str, ...}. Background daemon thread mein long-polling."""
    token = _get_token()
    chat_id = _get_chat_id()
    if not (token and chat_id):
        print("[TELEGRAM] token/chat id nahi, commands band")
        return None

    def loop():
        offset = None
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        while True:
            try:
                params = {"timeout": 25}
                if offset is not None:
                    params["offset"] = offset
                r = requests.get(url, params=params, timeout=35).json()
                for u in r.get("result", []):
                    offset = u["update_id"] + 1
                    m = u.get("message") or {}
                    if str(m.get("chat", {}).get("id")) != str(chat_id):
                        continue                         # ghair chat ignore
                    text = (m.get("text") or "").strip()
                    if not text.startswith("/"):
                        continue
                    cmd = text.split()[0].split("@")[0].lower()
                    h = handlers.get(cmd)
                    if h:
                        send(h())
            except Exception as e:
                print("telegram listener error:", e)
                time.sleep(5)

    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return th
