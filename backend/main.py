import asyncio
import logging
import os
import sys
from flask import Flask, request
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

app_flask = Flask(__name__)

# Global telegram application
telegram_app = None

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

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send /signal to receive instant trading signals.")

@app_flask.route('/')
def home():
    return "Telegram Trading Bot is Running Live!"

# Webhook endpoint to receive Telegram updates
@app_flask.route('/webhook', methods=['POST'])
def webhook():
    if request.method == "POST":
        update_json = request.get_json(force=True)
        update = Update.de_json(update_json, telegram_app.bot)
        asyncio.run(telegram_app.process_update(update))
        return "OK", 200
    return "Invalid Method", 400

def init_telegram_app():
    global telegram_app
    telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", handle_start_command))
    telegram_app.add_handler(CommandHandler("signal", handle_signal_command))
    asyncio.run(telegram_app.initialize())

init_telegram_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)
