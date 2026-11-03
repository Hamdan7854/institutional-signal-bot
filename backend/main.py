import time
import asyncio
import logging
from config import INSTRUMENTS
from data.oanda_client import OandaClient
from data.candle_builder import CandleBuilder
from features.feature_engine import FeatureEngine
from prediction.engine import PredictionEngine
from storage.database import DatabaseHandler
from telegram_bot import TelegramNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_pipeline():
    oanda = OandaClient()
    db = DatabaseHandler()
    notifier = TelegramNotifier()

    logger.info("Starting signal scanning round...")

    for pair in INSTRUMENTS:
        raw_candles = oanda.fetch_candles(instrument=pair, granularity="M5", count=100)
        if not raw_candles:
            continue

        df = CandleBuilder.parse_oanda_candles(raw_candles)
        df_featured = FeatureEngine.add_indicators(df)
        signal, confidence = PredictionEngine.generate_signal(df_featured)

        if signal in ["BUY", "SELL"] and confidence >= 0.80:
            logger.info(f"Valid signal detected for {pair}: {signal}")
            db.save_signal(pair, signal, confidence)
            await notifier.send_signal_alert(pair, signal, confidence)

async def main():
    while True:
        try:
            await run_pipeline()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
