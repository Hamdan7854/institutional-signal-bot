import logging
import os
from flask import Flask
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, FOREX_PAIRS
from strategy import analyze_next_candle_target

logging.basicConfig(level=logging.INFO)

# 1. Flask App (Render ke port requirement ko poora karne ke liye)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Institutional Signal Bot is Running Successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# 2. Telegram Bot Command Handler
async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /signal command execution handler.
    Multi-pair scanning complete karke exact Next Candle Target report karta hai.
    """
    await update.message.reply_text("🔎 *Institutional Order Flow & Liquidity Engine Active...*\nMajor Forex pairs scan ho rahe hain...", parse_mode="Markdown")
    
    signals_sent = 0
    for symbol in FOREX_PAIRS:
        result = analyze_next_candle_target(symbol)
        if result:
            signals_sent += 1
            factors_str = "\n• ".join(result['confluences'])
            
            msg = (
                f"🎯 *PRECISION PREDICTIVE SIGNAL* 🎯\n\n"
                f"🔤 *Pair:* `{result['pair']}`\n"
                f"📍 *Current Price:* `{result['current_price']}`\n"
                f"📈 *Direction:* {result['direction']}\n\n"
                f"⚡ *NEXT CANDLE TARGET PRICE:* `{result['predicted_target']}`\n"
                f"🎯 *Prediction Claim:* Next candle MUST hit or touch `{result['predicted_target']}`.\n\n"
                f"📊 *Confluence Matrix & Strategy Mechanics:*\n• {factors_str}\n\n"
                f"🔥 *Algorithmic Confidence:* `{result['confidence']}%`\n"
                f"⏳ *Expiry Window:* **Only Next 1 Candle**"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
            
    if signals_sent == 0:
        await update.message.reply_text("⚠️ Abhi market me exact high-confluence targets match nahi huay. Refresh karke dobara /signal bhein.")

def main():
    # Flask ko alag thread me run karein taake port block na ho
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Telegram Bot Start
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("signal", signal_command))
    print("Bot & Flask server are running...")
    app.run_polling()

if __name__ == "__main__":
    main()
