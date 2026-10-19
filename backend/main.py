
import os
import time
import logging
import threading
import datetime
import requests
from flask import Flask, jsonify, request

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from market_data import MarketDataProvider
from strategy import Strategy

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

provider = MarketDataProvider()
TELEGRAM_API_TIMEOUT = 10
SIGNAL_EXPIRY_SECONDS = 60


def send_telegram_message(chat_id, message):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        app.logger.error("Telegram bot token or chat ID is missing.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=TELEGRAM_API_TIMEOUT,
        )
        response.raise_for_status()
        return bool(response.json().get("ok", False))
    except requests.RequestException:
        app.logger.exception("Telegram message could not be sent.")
        return False


def normalize_pair(pair):
    pair = str(pair).strip().upper().replace(" ", "")

    if pair.endswith("_OTC"):
        return pair

    pair = pair.replace("-", "/")

    if "/" not in pair and len(pair) == 6 and pair.isalpha():
        pair = pair[:3] + "/" + pair[3:]

    return pair


def wait_until_signal_time():
    """Wait until the next minute's 50-second mark."""
    now = datetime.datetime.now()
    elapsed = now.second + now.microsecond / 1_000_000
    seconds = 50 - elapsed if elapsed < 50 else 110 - elapsed

    if seconds > 0:
        time.sleep(seconds)


def get_score_text(result):
    score = result.get("score", 0)

    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0.0

    score = max(0.0, min(100.0, score))
    return f"{score:.0f}%"


def generate_telegram_signal(symbol, chat_id):
    symbol = normalize_pair(symbol)

    try:
        wait_until_signal_time()

        df = provider.get_historical_data(symbol)

        if df is None or df.empty:
            result = {
                "signal": "WAIT",
                "action": "WAIT",
                "score": 0,
                "reason": "Market candle data is unavailable.",
                "entry_price": None,
                "rsi": None,
                "ema20": None,
                "ema50": None,
            }
        else:
            # Use the strategy's own rules; do not create new entry rules here.
            engine = Strategy()
            result = engine.analyze_market(df=df)

        signal = str(
            result.get("signal", result.get("action", "WAIT"))
        ).upper()

        if signal not in ("CALL", "PUT", "WAIT"):
            signal = "WAIT"

        score_text = get_score_text(result)
        reason = str(result.get("reason", "Conditions not confirmed."))
        price = result.get("entry_price", result.get("close"))

        try:
            price_text = f"{float(price):.5f}" if price is not None else "N/A"
        except (TypeError, ValueError):
            price_text = "N/A"

        rsi = result.get("rsi")
        try:
            rsi_text = f"{float(rsi):.2f}" if rsi is not None else "N/A"
        except (TypeError, ValueError):
            rsi_text = "N/A"

        ema20 = result.get("ema20")
        ema50 = result.get("ema50")

        try:
            ema_text = (
                f"EMA20: {float(ema20):.5f} | EMA50: {float(ema50):.5f}"
                if ema20 is not None and ema50 is not None
                else "EMA values: N/A"
            )
        except (TypeError, ValueError):
            ema_text = "EMA values: N/A"

        emoji = {
            "CALL": "🟢",
            "PUT": "🔴",
            "WAIT": "🔵",
        }[signal]

        if signal == "CALL":
            action_text = "CALL — bullish setup"
        elif signal == "PUT":
            action_text = "PUT — bearish setup"
        else:
            action_text = "WAIT — no confirmed setup"

        message = (
            "📊 1-MINUTE SIGNAL\n\n"
            f"Pair: {symbol}\n"
            f"Signal: {emoji} {action_text}\n"
            f"Prediction Score (rule-based): {score_text}\n"
            f"Reference Price: {price_text}\n"
            f"RSI: {rsi_text}\n"
            f"{ema_text}\n"
            f"Expiry Reference: {SIGNAL_EXPIRY_SECONDS} seconds\n\n"
            f"Strategy Reason: {reason}\n\n"
            "⚠️ Score is not a verified win probability. "
            "Market outcomes are uncertain. Confirm the live chart "
            "before making any decision. No trade was placed."
        )

        send_telegram_message(chat_id, message)

    except Exception:
        app.logger.exception("Signal generation failed for %s", symbol)
        send_telegram_message(
            chat_id,
            f"⚠️ Signal error for {symbol}.\n"
            "Please check market_data.py, strategy.py and Render logs."
        )


@app.route("/", methods=["GET"])
def home():
    return "Telegram Signal Engine is running."


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "strategy": "Existing Strategy.analyze_market",
        "signal_expiry_seconds": SIGNAL_EXPIRY_SECONDS,
        "timestamp": time.time(),
    })


@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    try:
        update = request.get_json(silent=True) or {}
        message = update.get("message") or update.get("edited_message")

        if not message:
            return jsonify({"status": "ignored"}), 200

        text = (message.get("text") or "").strip()
        chat_id = (message.get("chat") or {}).get("id")

        if not text or not chat_id:
            return jsonify({"status": "ignored"}), 200

        if text.startswith("/start") or text.startswith("/help"):
            send_telegram_message(
                chat_id,
                "Welcome to the Signal Bot.\n\n"
                "Request a signal by sending:\n"
                "/signal EUR/USD\n"
                "/signal GBP/USD\n"
                "/signal USD/JPY\n\n"
                "You will receive CALL, PUT or WAIT with a "
                "rule-based strategy score."
            )

        elif text.startswith(("/signal", "/getsignal")):
            parts = text.split(maxsplit=1)

            if len(parts) < 2:
                send_telegram_message(
                    chat_id,
                    "Please include a pair.\nExample: /signal EUR/USD"
                )
            else:
                symbol = normalize_pair(parts[1])

                threading.Thread(
                    target=generate_telegram_signal,
                    args=(symbol, chat_id),
                    daemon=True,
                ).start()

                send_telegram_message(
                    chat_id,
                    f"⏳ Request received for {symbol}.\n"
                    "Preparing a signal using the configured strategy."
                )

        return jsonify({"status": "ok"}), 200

    except Exception:
        app.logger.exception("Webhook handling failed.")
        return jsonify({"status": "error"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
