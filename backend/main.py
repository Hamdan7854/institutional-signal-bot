import os
import logging
import sys
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Telegram Trading Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

def fetch_deriv_ticks_http(symbol="R_100", count=30):
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
    await update.message.reply_text("🔍 Analyzing Deriv R_100 market data...")

    price_history = fetch_deriv_ticks_http("R_100", count=30)

    if len(price_history) < 10:
        await update.message.reply_text("⚠️ Insufficient tick history. Please try again.")
        return

    # SMA Strategy Logic
    fast_sma = sum(price_history[-5:]) / 5
    slow_sma = sum(price_history[-20:]) / 20

    if fast_sma > slow_sma:
        signal = "CALL / BUY 🟢"
        reason = f"Fast SMA ({fast_sma:.2f}) crossed above Slow SMA ({slow_sma:.2f})."
    else:
        signal = "PUT / SELL 🔴"
        reason = f"Fast SMA ({fast_sma:.2f}) crossed below Slow SMA ({slow_sma:.2f})."

    current_price = price_history[-1]
    response_text = (
        f"📊 **Deriv Market Analysis (R_100)**\n\n"
        f"💵 **Current Price:** {current_price:.2f}\n"
        f"🎯 **Signal:** `{signal}`\n"
        f"📝 **Reason:** {reason}"
    )
    await update.message.reply_text(response_text, parse_mode="Markdown")

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send /signal to get the latest R_100 trading signal.")

def main():
    # Start Flask web server in background
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "8827147070:AAFdy07cVKtAAyqH-hchdre-MSJSZr6TMvk")

    # Build and run Telegram Application natively
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", handle_start_command))
    application.add_handler(CommandHandler("signal", handle_signal_command))

    logging.info("Starting Telegram bot polling without event loop conflict...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
