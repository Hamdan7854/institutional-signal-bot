import logging
import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, INSTRUMENTS, TIMEFRAMES
from data.oanda_client import OandaClient
from features.micp_features import MICPFeatureEngine
from prediction.micp_engine import MICPPredictionEngine
from storage.database import DatabaseHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Flask app taake Render Web Service active rahe
app = Flask(__name__)

@app.route('/')
def home():
    return "MICP-60 Trading Bot is Live and Running!"

async def micp_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id, 
        text="🧠 <b>MICP-60 Engine Initiated:</b> Scanning 1 to 60 Minutes multi-timeframe intelligence across Forex pairs..."
    )

    oanda = OandaClient()
    db = DatabaseHandler()

    for pair in INSTRUMENTS[:3]:
        report_lines = [f"📊 <b>MICP-60 REPORT: {pair}</b>\n"]
        
        for tf_code, tf_name in TIMEFRAMES.items():
            raw_candles = oanda.fetch_candles(instrument=pair, granularity=tf_code, count=100)
            if not raw_candles:
                continue

            df = MICPFeatureEngine.process_features(raw_candles)
            direction, confidence, exp_close = MICPPredictionEngine.predict_next_candle(df)

            report_lines.append(
                f"⏱️ <b>{tf_name} ({tf_code}):</b> {direction}\n"
                f"🎯 Confidence: {confidence * 100:.0f}% | Exp. Close: {exp_close}\n"
            )
            
            db.save_signal(pair, f"{tf_code}_{direction}", confidence)

        full_message = "\n".join(report_lines)
        await context.bot.send_message(chat_id=chat_id, text=full_message, parse_mode="HTML")

def run_bot_polling():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN is missing!")
        return

    logger.info("🚀 Starting Telegram Bot Application...")
    try:
        application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        application.add_handler(CommandHandler("signal", micp_signal_command))
        
        logger.info("✅ Telegram Bot is now polling for messages...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"❌ Error in Telegram polling: {e}")

if __name__ == "__main__":
    # Start Telegram Bot in background thread
    bot_thread = threading.Thread(target=run_bot_polling)
    bot_thread.daemon = True
    bot_thread.start()

    # Run Flask Web Server
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
