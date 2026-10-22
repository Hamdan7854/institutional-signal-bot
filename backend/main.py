import os
import logging
import sys
import threading
import asyncio
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests

# Import Quantitative Trading Strategy
from strategy import QuantitativeTradingStrategy

# Configure Logging
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

# 1. Complete Real Forex Pairs for Pocket Option (Yahoo Finance Symbols)
FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",
    "NZD/USD": "NZDUSD=X",
    "EUR/GBP": "EURGBP=X",
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "AUD/JPY": "AUDJPY=X",
    "EUR/AUD": "EURAUD=X",
    "EUR/CAD": "EURCAD=X",
    "GBP/CHF": "GBPCHF=X",
    "AUD/CAD": "AUDCAD=X",
    "CAD/JPY": "CADJPY=X",
    "CHF/JPY": "CHFJPY=X",
    "GBP/CAD": "GBPCAD=X",
    "GBP/AUD": "GBPAUD=X",
    "NZD/JPY": "NZDJPY=X"
}

def fetch_forex_prices(symbol):
    """
    Fetches exact 5-Minute (M5) timeframe price history via Yahoo Finance API
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=5m&range=1d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            result = data["chart"]["result"][0]
            prices = result["indicators"]["quote"][0]["close"]
            # Filter out None values and cast to float
            valid_prices = [float(p) for p in prices if p is not None]
            return valid_prices
    except Exception as e:
        logging.error(f"Error fetching forex data for {symbol}: {e}")
    return []

async def handle_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Generates signals for Pocket Option Real Forex pairs synchronized with M5 Candle Close
    """
    try:
        now = datetime.now()
        
        # Calculate seconds remaining until current M5 candle closes
        seconds_into_m5 = (now.minute % 5) * 60 + now.second
        seconds_remaining = 300 - seconds_into_m5

        # If user commands 20s before candle close, wait briefly for new candle open
        if seconds_remaining <= 30:
            await update.message.reply_text(f"⏳ Candle closing in {seconds_remaining}s. Synchronizing live entry price...")
            await asyncio.sleep(seconds_remaining + 1)
            now = datetime.now()

        # Calculate exact 5-Minute Expiry Duration
        expiry_minutes = 5 - (now.minute % 5)
        expiry_time = (now + timedelta(minutes=expiry_minutes)).strftime("%I:%M:%S %p")

        await update.message.reply_text("🔍 Scanning Real Forex Markets for Pocket Option (M5 Close Sync)...")

        report_lines = [
            "📊 **POCKET OPTION FOREX SIGNALS**",
            f"⏰ **Expiry Time:** {expiry_time} (5 Mins)\n"
        ]

        signals_found = 0

        for pair_name, symbol in FOREX_PAIRS.items():
            prices = fetch_forex_prices(symbol)

            if len(prices) >= 50:
                # Use strategy engine to calculate signal based on latest closed candle
                signal, reason = QuantitativeTradingStrategy.evaluate_signal(price_history=prices)

                # Ensure entry price is strictly the LIVE latest price
                live_entry_price = prices[-1]

                if signal != "HOLD":
                    report_lines.append(
                        f"💱 **{pair_name}**\n"
                        f"💵 Price: `{live_entry_price:.5f}`\n"
                        f"🎯 Signal: **{signal}**\n"
                    )
                    signals_found += 1

        if signals_found == 0:
            await update.message.reply_text("⚠️ No high-probability signals found on closed candle completion. Market is in noise phase.")
            return

        response_text = "\n".join(report_lines)
        await update.message.reply_text(response_text, parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Error in signal command: {e}")
        await update.message.reply_text(f"⚠️ Error generating signals: {e}")

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send /signal to get live Pocket Option signals synced with M5 candle close.")

def main():
    # Run Flask in background thread for hosting health check
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", handle_start_command))
    application.add_handler(CommandHandler("signal", handle_signal_command))

    logging.info("Starting Telegram bot for Pocket Option Forex signals...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
