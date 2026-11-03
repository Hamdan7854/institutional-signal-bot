import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, INSTRUMENTS
from data.oanda_client import OandaClient
from data.candle_builder import CandleBuilder
from features.feature_engine import FeatureEngine
from prediction.engine import PredictionEngine
from storage.database import DatabaseHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def scan_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="🔍 Market scan shuru ho gaya hai, please wait...")

    oanda = OandaClient()
    db = DatabaseHandler()
    
    signals_found = 0

    for pair in INSTRUMENTS:
        raw_candles = oanda.fetch_candles(instrument=pair, granularity="M5", count=100)
        if not raw_candles:
            continue

        df = CandleBuilder.parse_oanda_candles(raw_candles)
        df_featured = FeatureEngine.add_indicators(df)
        signal, confidence = PredictionEngine.generate_signal(df_featured)

        if signal in ["BUY", "SELL"] and confidence >= 0.80:
            signals_found += 1
            db.save_signal(pair, signal, confidence)
            message = (
                f"🚨 <b>INSTITUTIONAL SIGNAL ALERT</b> 🚨\n\n"
                f"📈 <b>Instrument:</b> {pair}\n"
                f"⚡ <b>Signal:</b> {signal}\n"
                f"🎯 <b>Confidence:</b> {confidence * 100:.1f}%\n"
                f"⏱️ <b>Timeframe:</b> M5"
            )
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")

    if signals_found == 0:
        await context.bot.send_message(chat_id=chat_id, text="ℹ️ Filhal kisi bhi pair par strong signal nahi mila (All HOLD).")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram Bot Token missing!")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # /signal command handler
    application.add_handler(CommandHandler("signal", scan_market))

    logger.info("Bot is running and listening for /signal command...")
    application.run_polling()

if __name__ == "__main__":
    main()
