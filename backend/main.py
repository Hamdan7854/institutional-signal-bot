import logging
import os
from flask import Flask
import threading
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, FOREX_PAIRS
from strategy import scan_all

logging.basicConfig(level=logging.INFO)

# 1. Flask App (Render port binding ke liye)
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
    Saare pairs ko foran parallel scan karta hai aur matching signals return karta hai.
    """
    await update.message.reply_text("🔎 *Institutional Scan Active...* Pairs check kiye ja rahe hain...", parse_mode="Markdown")
    
    # Sary pairs ko scan_all ke zariye parallel run karna
    pairs_to_scan = FOREX_PAIRS if 'FOREX_PAIRS' in globals() or 'FOREX_PAIRS' in locals() else None
    result = await scan_all(pairs_to_scan)
    
    signals = result.get("signals", [])
    signals_sent = 0

    for s in signals:
        signals_sent += 1
        factors_str = "\n• ".join(s['confirmations'])
        
        # Color & Emoji for Direction
        if s['direction'] == "BUY":
            direction_str = "🟢 BUY"
        else:
            direction_str = "🔴 SELL"
        
        msg = (
            f"🎯 *PRECISION SIGNAL MATCH* 🎯\n\n"
            f"🔤 *Pair:* `{s['pair']}`\n"
            f"📈 *Direction:* {direction_str}\n"
            f"📍 *Entry Price:* `{s['entry']}`\n"
            f"🛑 *Stop Loss:* `{s['stop_loss']}`\n"
            f"🎯 *Target:* `{s['target']}`\n\n"
            f"📊 *Confirmations & Mechanics:*\n• {factors_str}\n\n"
            f"🔥 *Score:* `{s['score']}/8` | *R:R:* `{s['risk_reward']}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
            
    if signals_sent == 0:
        await update.message.reply_text("⚠️ Abhi kisi bhi pair par high-confluence setup match nahi hua. Kuch dair baad dobara koshish karein.", parse_mode="Markdown")

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("signal", signal_command))
    print("Bot & Flask server are running with lightning-fast async scanning...")
    app.run_polling()

if __name__ == "__main__":
    main()
