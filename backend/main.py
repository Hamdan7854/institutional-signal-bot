import os
import logging
import sys
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Import Quantitative Strategy Engine
from strategy import QuantitativeTradingStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Pocket Option Forex Signal Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# All Major and Minor Real Forex Pairs for Pocket Option (Yahoo Finance Symbols)
FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X",
    "USD/CHF": "CHF=X",
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
    """Fetches M5 candle historical price data via Yahoo Finance API."""
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
            # Filter out None values
            valid_prices = [float(p) for p in prices if p is not None]
            return valid_prices
    except Exception as e:
        logging.error(f"Error fetching forex data for {symbol}: {e}")
    
    return []

def get_next_m5_expiry():
    """
    Calculates exact Next M5 Candle Expiry Time.
    If commanded 20s before candle close, aligns perfectly with the upcoming new candle expiration.
    """
    now = datetime.now()
    minutes_to_add = 5 - (now.minute % 5)
    
    # If exactly on the candle close moment (0 seconds left), project to full next 5 min
    if minutes_to_add == 0 and now.second > 40:
        minutes_to_add = 5
        
    next_expiry = (now + timedelta(minutes=minutes_to_add)).replace(second=0, microsecond=0)
    return next_expiry.strftime("%I:%M:%S %p")

async def handle_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates signals for Pocket Option Real Forex pairs aligned with M5 Candle Close."""
    try:
        await update.message.reply_text("🔍 Scanning Real Forex Markets for Pocket Option...")

        expiry_time = get_next_m5_expiry()

        report_lines = [
            "📊 **POCKET OPTION FOREX SIGNALS**",
            f"⏰ **Expiry Time:** {expiry_time} (5 Mins)\n"
        ]

        signals_found = 0

        for pair_name, symbol in FOREX_PAIRS.items():
            prices = fetch_forex_prices(symbol)

            # Ensure sufficient historical prices for M5 Analysis
            if len(prices) >= 50:
                # Use fully closed candle history (excluding active forming tick)
                closed_prices = prices[:-1]
                
                # Evaluate via 3-Tier Institutional Strategy Engine
                signal, reason = QuantitativeTradingStrategy.evaluate_signal(closed_prices)

                if signal != "HOLD":
                    current_price = closed_prices[-1]
                    emoji = "🔴" if "PUT" in signal else "🟢"
                    
                    report_lines.append(
                        f"💲 **{pair_name}**\n"
                        f"💵 Price: {current_price:.5f}\n"
                        f"🎯 Signal: {signal} {emoji}\n"
                    )
                    signals_found += 1

        if signals_found == 0:
            await update.message.reply_text("⚠️ No high-probability signals found at candle close. Market in noise/ranging state.")
            return

        response_text = "\n".join(report_lines)
        await update.message.reply_text(response_text)

    except Exception as e:
        logging.error(f"Error in signal command: {e}")
        await update.message.reply_text(f"⚠️ Error generating signals: {e}")

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send /signal to get live Pocket Option Forex signals.")

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "8027147070:AAFey07CVktMYqH...")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", handle_start_command))
    application.add_handler(CommandHandler("signal", handle_signal_command))

    logging.info("Starting Telegram bot for Pocket Option Forex signals.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
