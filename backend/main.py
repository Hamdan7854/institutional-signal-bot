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
    return "Forex Signal Trading Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# Major Forex Pairs List
FOREX_PAIRS = {
    "EURUSD": "frxEURUSD",
    "GBPUSD": "frxGBPUSD",
    "USDJPY": "frxUSDJPY",
    "AUDUSD": "frxAUDUSD",
    "USDCAD": "frxUSDCAD"
}

def fetch_deriv_ticks_http(symbol, count=30):
    """Fetches real-time market data for Forex pairs via Deriv API."""
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
        logging.error(f"Error fetching ticks for {symbol}: {e}")
    
    return []

async def handle_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates signals for all major Real Forex Pairs with exact expiry time."""
    try:
        await update.message.reply_text("🔍 Scanning Real Forex Market Pairs...")

        # Exact Expiry Calculation (5-Minute Trade Duration)
        now = datetime.now()
        expiry_time = (now + timedelta(minutes=5)).strftime("%I:%M:%S %p")

        report_lines = [f"📊 **REAL FOREX MARKET SIGNALS**", f"⏰ **Expiry Time:** {expiry_time} (5 Min Duration)\n"]
        signals_found = 0

        for pair_name, pair_symbol in FOREX_PAIRS.items():
            price_history = fetch_deriv_ticks_http(pair_symbol, count=30)

            if len(price_history) >= 20:
                fast_sma = sum(price_history[-5:]) / 5
                slow_sma = sum(price_history[-20:]) / 20
                current_price = price_history[-1]

                if fast_sma > slow_sma:
                    signal = "BUY / CALL 🟢"
                else:
                    signal = "SELL / PUT 🔴"

                report_lines.append(
                    f"💱 **{pair_name}**\n"
                    f"💵 Price: {current_price}\n"
                    f"🎯 Signal: {signal}\n"
                )
                signals_found += 1

        if signals_found == 0:
            await update.message.reply_text("⚠️ Real Forex Market is currently closed or data unavailable.")
            return

        response_text = "\n".join(report_lines)
        await update.message.reply_text(response_text)

    except Exception as e:
        logging.error(f"Error in signal command: {e}")
        await update.message.reply_text(f"⚠️ Error scanning forex pairs: {str(e)}")

async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Send /signal to get real-time Real Forex Market signals with exact expiry times.")

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "8827147070:AAFdy07cVKtAAyqH-hchdre-MSJSZr6TMvk")

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", handle_start_command))
    application.add_handler(CommandHandler("signal", handle_signal_command))

    logging.info("Starting Telegram bot for Forex signals...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
