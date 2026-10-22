import os
import logging
import sys
import threading
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests

from strategy import QuantitativeTradingStrategy

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

def fetch_instant_live_data(symbol):
    """
    Fetches the absolute latest available market price instantly.
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
            
            # Get latest live market price from meta or quote
            meta_price = result["meta"].get("regularMarketPrice")
            prices = result["indicators"]["quote"][0]["close"]
            valid_prices = [float(p) for p in prices if p is not None]
            
            if meta_price is not None and valid_prices:
                valid_prices[-1] = float(meta_price)
            
            return valid_prices
    except Exception as e:
        logging.error(f"Error fetching instant data for {symbol}: {e}")
    return []

async def handle_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires signals INSTANTLY without any delay or waiting upon command.
    """
    try:
        await update.message.reply_text("⚡ Scanning live markets instantly...")
        
        now = datetime.now()
        expiry_time = (now + timedelta(minutes=5)).strftime("%I:%M:%S %p")

        report_lines = [
            "📊 **POCKET OPTION FOREX SIGNALS**",
            f"⏰ **Expiry Time:** {expiry_time} (5 Mins)\n"
        ]

        signals_found = 0

        for pair_name, symbol in FOREX_PAIRS.items():
            prices = fetch_instant_live_data(symbol)

            if len(prices) >= 50:
                signal, reason = QuantitativeTradingStrategy.evaluate_signal(price_history=prices)
                live_entry_price = prices[-1]

                if signal != "HOLD":
                    report_lines.append(
                        f"💱 **{pair_name}**\n"
                        f"💵 Live Price: `{live_entry_price:.5f}`\n"
                        f"🎯 Signal: **{signal}**\n"
                    )
                    signals_found += 1

        if signals_found == 0:
            await update.message.reply_text("⚠️ No high-probability setup found at this exact moment. Try again in a minute.")
            return

        response_text = "\n".join(report_lines)
        await update.message.reply_text(response_text, parse_mode="Markdown")

    except Exception as ec:
        logging.error(f"Error in signal command: {ec}")
        await update.message.reply_text(f"⚠️ Error generating signals: {ec}")

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send /signal for instant live market signals.")

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", handle_start_command))
    application.add_handler(CommandHandler("signal", handle_signal_command))

    logging.info("Starting Instant Telegram Signal Bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
