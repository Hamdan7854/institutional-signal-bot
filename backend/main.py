
import os
import time
import logging
import threading
import requests
from flask import Flask, jsonify, request

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SIGNAL_EXPIRY_SECONDS,
    TELEGRAM_API_TIMEOUT,
)
from market_data import MarketDataProvider
from strategy import Strategy

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

provider = MarketDataProvider()


def send_telegram_message(chat_id, message):
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        app.logger.error("Telegram token or chat ID is missing.")
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=TELEGRAM_API_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("ok", False)

    except requests.RequestException:
        app.logger.exception("Telegram message failed.")
        return False


def normalize_pair(pair):
    pair = str(pair).strip().upper()
    pair = pair.replace(" ", "").replace("-", "").replace("/", "")

    if len(pair) == 6 and pair.isalpha():
        return pair[:3] + "/" + pair[3:]

    return pair


def create_signal(symbol):
    df = provider.get_historical_data(symbol)

    if df is None or df.empty:
        return {
            "signal": "WAIT",
            "score": 0,
            "reason": "No market candle data available.",
            "close": None,
            "rsi": None,
            "ema20": None,
            "ema50": None,
        }

    engine = Strategy()
    return engine.analyze_market(df=df)


def send_signal_request(symbol, chat_id):
    try:
        result = create_signal(symbol)

        signal = str(
            result.get("signal", result.get("action", "WAIT"))
        ).upper()

        if signal not in ("CALL", "PUT", "WAIT"):
            signal = "WAIT"

        try:
            score = float(result.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        score = max(0, min(100, score))
        score_text = f"{score:.0f}%"

        price = result.get("close", result.get("entry_price"))
        rsi = result.get("rsi")
        ema20 = result.get("ema20")
        ema50 = result.get("ema50")

        try:
            price_text = f"{float(price):.5f}" if price is not None else "N/A"
        except (TypeError, ValueError):
            price_text = "N/A"

        try:
            rsi_text = f"{float(rsi):.2f}" if rsi is not None else "N/A"
        except (TypeError, ValueError):
            rsi_text = "N/A"

        try:
            ema_text = (
                f"EMA20: {float(ema20):.5f} | "
                f"EMA50: {float(ema50):.5f}"
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

        message = (
            "📊 1-MINUTE FOREX SIGNAL\n\n"
            f"Pair: {symbol}\n"
            f"Signal: {emoji} {signal}\n"
            f"Strategy Score: {score_text}\n"
            f"Reference Price: {price_text}\n"
            f"RSI: {rsi_text}\n"
            f"{ema_text}\n"
            f"Expiry Reference: {SIGNAL_EXPIRY_SECONDS} seconds\n\n"
            f"Reason: {result.get('reason', 'No reason provided.')}\n\n"
            "Note: The score is a rule-based strategy score, "
            "not a verified win probability. Market data may be "
            "delayed or incomplete. Confirm the live chart manually. "
            "No trade was placed."
        )

        send_telegram_message(chat_id, message)

    except Exception:
        app.logger.exception("Signal request failed for %s", symbol)
        send_telegram_message(
            chat_id,
            f"⚠️ Unable to generate a signal for {symbol}. "
            "Please check the Render logs."
        )


@app.route("/", methods=["GET"])
def home():
    return "Telegram Forex Signal Bot is running."


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "strategy": "RSI + Keltner Channel + EMA20/EMA50",
        "timestamp": time.time(),
    })


@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message")

    if not message:
        return jsonify({"status": "ignored"}), 200

    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return jsonify({"status": "ignored"}), 200

    if text.startswith(("/start", "/help")):
        send_telegram_message(
            chat_id,
            "Welcome to the Forex Signal Bot.\n\n"
            "Commands:\n"
            "/signal EUR/USD\n"
            "/signal GBP/USD\n"
            "/signal USD/JPY\n"
            "/help\n\n"
            "The bot returns CALL, PUT or WAIT with a "
            "rule-based strategy score."
        )

    elif text.startswith(("/signal", "/getsignal")):
        parts = text.split(maxsplit=1)

        if len(parts) != 2:
            send_telegram_message(
                chat_id,
                "Please provide a pair.\n"
                "Example: /signal EUR/USD"
            )
        else:
            symbol = normalize_pair(parts[1])

            if (
                len(symbol) != 7
                or symbol[3] != "/"
                or not symbol.replace("/", "").isalpha()
            ):
                send_telegram_message(
                    chat_id,
                    "Invalid pair format.\n"
                    "Example: /signal EUR/USD"
                )
            else:
                send_telegram_message(
                    chat_id,
                    f"⏳ Request received for {symbol}. "
                    "Checking market data and strategy conditions..."
                )

                threading.Thread(
                    target=send_signal_request,
                    args=(symbol, chat_id),
                    daemon=True,
                ).start()

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
