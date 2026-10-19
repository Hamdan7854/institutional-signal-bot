import os
import time
import datetime
import threading
import requests
from flask import Flask, jsonify, request

from config import PAIRS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from market_data import MarketDataProvider
from strategy import Strategy

app = Flask(__name__)
provider = MarketDataProvider()
TELEGRAM_API_TIMEOUT = 10
SIGNAL_EXPIRY_SECONDS = 60


def get_scannable_pairs():
    """Use OTC pairs on weekends and non-OTC pairs on weekdays."""
    is_weekend = datetime.datetime.now().weekday() in (5, 6)
    result = []
    for pair in PAIRS:
        is_otc = "_OTC" in str(pair).upper()
        if (is_weekend and is_otc) or (not is_weekend and not is_otc):
            result.append(str(pair))
    return result


def wait_until_1m_countdown():
    """Wait until the next minute's :50 second."""
    now = datetime.datetime.now()
    elapsed = now.second + now.microsecond / 1_000_000
    wait_seconds = 50 - elapsed if elapsed < 50 else 110 - elapsed
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def _send_telegram_message(chat_id, text):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        print("Telegram message skipped: bot token or chat ID is not configured.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url, json={"chat_id": chat_id, "text": text},
            timeout=TELEGRAM_API_TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            print(f"Telegram API error: {payload}")
            return False
        return True
    except requests.RequestException as exc:
        print(f"Telegram send error: {exc}")
        return False


def _format_price(value):
    try:
        return f"{float(value):.5f}"
    except (TypeError, ValueError):
        return "N/A"


def send_telegram_signal_1m_countdown(symbol, chat_id=None):
    """Generate manual CALL/PUT/WAIT signals; never places trades."""
    target_chat = chat_id if chat_id is not None else TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        print("Telegram is not configured.")
        return

    wait_until_1m_countdown()

    try:
        df = provider.get_historical_data(symbol)
        if df is None or getattr(df, "empty", True):
            result = {
                "signal": "WAIT",
                "reason": "No candle data received from market_data provider.",
                "close": None, "rsi": None, "ema20": None, "ema50": None
            }
        else:
            engine = Strategy(
                rsi_period=14,
                ema_fast_period=20,
                ema_slow_period=50,
                keltner_period=20,
                atr_period=20,
                atr_multiplier=2.0,
                expiry_seconds=SIGNAL_EXPIRY_SECONDS,
                timeframe="1m",
                min_candles=60,
            )
            result = engine.generate_signal(df=df, symbol=symbol)
    except Exception as exc:
        app.logger.exception("Signal generation failed for %s", symbol)
        result = {
            "signal": "WAIT", "reason": f"Signal/data error: {exc}",
            "close": None, "rsi": None, "ema20": None, "ema50": None
        }

    signal = str(result.get("signal", "WAIT")).upper()
    if signal not in {"CALL", "PUT", "WAIT"}:
        signal = "WAIT"

    emoji = {"CALL": "🟢", "PUT": "🔴", "WAIT": "🔵"}[signal]
    reason = str(result.get("reason", "Conditions not confirmed."))
    price = _format_price(result.get("close"))
    rsi = result.get("rsi")
    rsi_text = f"{float(rsi):.2f}" if isinstance(rsi, (int, float)) else "N/A"
    ema20, ema50 = result.get("ema20"), result.get("ema50")
    ema_text = (
        f"EMA20: {_format_price(ema20)} | EMA50: {_format_price(ema50)}"
        if ema20 is not None and ema50 is not None else "EMA values: N/A"
    )

    if signal == "CALL":
        action_text = "CALL — bullish setup detected"
    elif signal == "PUT":
        action_text = "PUT — bearish setup detected"
    else:
        action_text = "WAIT — do not trade; conditions are not aligned"

    preview_msg = (
        "⚠️ 1-MINUTE SIGNAL PREVIEW\n\n"
        f"Pair: {symbol}\nDirection: {emoji} {action_text}\n"
        f"Latest close: {price}\nRSI: {rsi_text}\n{ema_text}\n"
        f"Expiry reference: {SIGNAL_EXPIRY_SECONDS} seconds\n"
        f"Reason: {reason}\n\n"
        "Preview only. Confirm candle timing and live price manually."
    )
    _send_telegram_message(target_chat, preview_msg)

    time.sleep(10)

    final_action = (
        "WAIT — DO NOT TRADE" if signal == "WAIT"
        else f"{signal} — manual entry only; confirm the live chart"
    )
    confirmed_msg = (
        "📣 1-MINUTE SIGNAL\n\n"
        f"Pair: {symbol}\nAction: {emoji} {final_action}\n"
        f"Reference price: {price}\nExpiry reference: {SIGNAL_EXPIRY_SECONDS} seconds\n"
        f"RSI: {rsi_text}\n{ema_text}\nReason: {reason}\n\n"
        "Signals only: no trade was placed. Results are not guaranteed."
    )
    _send_telegram_message(target_chat, confirmed_msg)


@app.route("/", methods=["GET"])
def home():
    return "1-Minute RSI + Keltner + EMA Signal Engine is active."


@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message") or data.get("edited_message")
        if not message:
            return jsonify({"status": "ignored", "reason": "No message in update"}), 200

        message_text = (message.get("text") or "").strip()
        chat_id = (message.get("chat") or {}).get("id")
        if message_text.startswith(("/signal", "/getsignal")):
            parts = message_text.split()
            pair = parts[1].upper() if len(parts) > 1 else "EUR/USD"
            threading.Thread(
                target=send_telegram_signal_1m_countdown,
                args=(pair, chat_id),
                daemon=True,
            ).start()
        return jsonify({"status": "ok"}), 200
    except Exception as exc:
        app.logger.exception("Webhook handling failed")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "strategy": "RSI-50 + Keltner Channel + EMA20/EMA50",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
