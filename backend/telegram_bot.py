"""Telegram: message bhejna + commands sunna (/status, /edge, /pause, /resume, /help). Sirf TELEGRAM_CHAT_ID wali chat ki commands manzoor hoti hain."""
import threading
import time
import requests
import config


def send(text: str):
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        print("[TELEGRAM-OFF]", text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text}, timeout=10)
    except requests.RequestException as e:
        print("telegram error:", e)


def start_listener(handlers):
    """handlers: {'/status': callable -> str, ...}. Background daemon thread mein long-polling."""
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        print("[TELEGRAM] token/chat id nahi, commands band")
        return None

    def loop():
        offset = None
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getUpdates"
        while True:
            try:
                params = {"timeout": 25}
                if offset is not None:
                    params["offset"] = offset
                r = requests.get(url, params=params, timeout=35).json()
                for u in r.get("result", []):
                    offset = u["update_id"] + 1
                    m = u.get("message") or {}
                    if str(m.get("chat", {}).get("id")) != str(config.TELEGRAM_CHAT_ID):
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
