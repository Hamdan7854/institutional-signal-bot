import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, INSTRUMENTS, TIMEFRAMES
from data.oanda_client import OandaClient
from features.micp_features import MICPFeatureEngine
from prediction.micp_engine import MICPPredictionEngine
from storage.database import DatabaseHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def micp_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id, 
        text="🧠 **MICP-60 Engine Initiated:** Scanning 1 to 60 Minutes multi-timeframe intelligence across Forex pairs..."
    )

    oanda = OandaClient()
    db = DatabaseHandler()

    for pair in INSTRUMENTS[:3]: # Top pairs to avoid Telegram message limits
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
            
            # Save to Database
            db.save_signal(pair, f"{tf_code}_{direction}", confidence)

        full_message = "\n".join(report_lines)
        await context.bot.send_message(chat_id=chat_id, text=full_message, parse_mode="HTML")
        await asyncio.sleep(1)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram Bot Token missing!")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("signal", micp_signal_command))

    logger.info("MICP-60 Telegram Bot is live and listening for /signal...")
    application.run_polling()

if __name__ == "__main__":
    main()
