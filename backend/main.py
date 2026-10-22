import os
import logging
import sys
import threading
from datetime import datetime, timedelta
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
    return "Pocket Option Forex Signal Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# Real Forex Pairs for Pocket Option (Yahoo Finance Symbols)
FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X"
}

def fetch_forex_prices(symbol):
    """Fetches real-time Forex market data via Yahoo Finance API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=30m"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            result = data["chart"]["result"][0]
            prices = result["indicators"]["quote"][0]["close"]
            # Filter out None values
            valid_prices = [float(p) for p in prices if p is not None]
            return valid_prices
    except Exception as e:
        logging.error(f"Error fetching forex data for {symbol}: {e}")
    
    return []

async def handle_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates signals for Pocket Option Real Forex pairs with exact expiry time."""
    try:
        await update.message.reply_text("🔍 Scanning Real Forex Markets for Pocket Option...")

        # 5-Minute Expiry Duration calculation
        now = datetime.now()
        expiry_time = (now + timedelta(minutes=5)).strftime("%I:%M:%S %p")

        report_lines = [
            "📊 **POCKET OPTION FOREX SIGNALS**",
            f"⏰ **Expiry Time:** {expiry_time} (5 Mins)\n"
        ]
        
        signals_found = 0

        for pair_name, symbol in FOREX_PAIRS.items():
            prices = fetch_forex_prices(symbol)

            if len(prices) >= 15:
                fast_sma = sum(prices[-5:]) / 5
                slow_sma = sum(prices[-15:]) / 15
                current_price = prices[-1]

                if fast_sma > slow_sma:
                    signal = "CALL / HIGHER 🟢"
                else:
                    signal = "PUT / LOWER 🔴"

                report_lines.append(
                    f"💱 **{pair_name}**\n"
                    f"💵 Price: {current_price:.5f}\n"
                    f"🎯 Signal: {signal}\n"
                )
                signals_found += 1

        if signals_found == 0:
            await update.message.reply_text("⚠️ Market data temporarily unavailable. Please try again.")
            return

        response_text = "\n".join(report_lines)
        await update.message.reply_text(response_text)

    except Exception as e:
        logging.error(f"Error in signal command: {e}")
        await update.message.reply_text(f"⚠️ Error generating signals: {str(e)}")

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send /signal to get live Pocket Option Forex signals with exact expiry times.")

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "8827147070:AAFdy07cVKtAAyqH-hchdre-MSJSZr6TMvk")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", handle_start_command))
    application.add_handler(CommandHandler("signal", handle_signal_command))

    logging.info("Starting Telegram bot for Pocket Option Forex signals...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
