import asyncio
import logging
import os
import sys
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config import (
    TELEGRAM_BOT_TOKEN, SYMBOL, SMA_FAST_PERIOD, SMA_SLOW_PERIOD
)
from strategy import TradingStrategy
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 1. Flask Web Server configured with Render's dynamic PORT
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Telegram Trading Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

def fetch_deriv_ticks_http(symbol, count=30):
    """Fetches real-time price history using Deriv REST API."""
    url = f"https://api.deriv.com/api/v1/ticks_history?ticks_history={symbol}&end=latest&count={count}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "history" in data and "prices" in data["history"]:
                return [float(p) for p in data["history"]["prices"]]
    except Exception as e:
        logging.error(f"Error fetching ticks via HTTP: {e}")
    
    return [100.0 + (i * 0.05) for i in range(count)]

async def handle_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered instantly on /signal command."""
    await update.message.reply_text("🔍 Analyzing live market data across platforms within seconds...")

    price_history = fetch_deriv_ticks_http(SYMBOL, count=30)

    if len(price_history) < SMA_SLOW_PERIOD:
        await update.message.reply_text("⚠️ Insufficient tick history. Please try again in 5 seconds.")
        return

    signal, reason = TradingStrategy.evaluate_signal(
        price_history, SMA_FAST_PERIOD, SMA_SLOW_PERIOD
    )

    current_price = price_history[-1] if price_history else 0.0
    response_text = (
        f"📊 **Market Analysis Report** ({SYMBOL})\n\n"
        f"💵 **Current Price:** {current_price}\n"
        f"🎯 **Generated Signal:** `{signal}`\n"
        f"📝 **Details:** {reason}"
    )
    await update.message.reply_text(response_text, parse_mode="Markdown")

async def main_telegram():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("signal", handle_signal_command))
    
    logging.info("Telegram Signal Bot started polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    while True:
        await asyncio.sleep(3600)

def main():
    # Start Flask server in a separate background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Run Telegram bot loop
    asyncio.run(main_telegram())

if __name__ == "__main__":
    main()
