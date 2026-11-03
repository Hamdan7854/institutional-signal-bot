import logging
from telegram import Bot
from backend.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.bot = Bot(token=self.token) if self.token else None

    async def send_signal_alert(self, instrument: str, signal: str, confidence: float):
        if not self.bot or not self.chat_id:
            logger.warning("Telegram credentials not fully configured.")
            return

        message = (
            f"🚨 <b>INSTITUTIONAL SIGNAL ALERT</b> 🚨\n\n"
            f"📈 <b>Instrument:</b> {instrument}\n"
            f"⚡ <b>Signal:</b> {signal}\n"
            f"🎯 <b>Confidence:</b> {confidence * 100:.1f}%\n"
            f"⏱️ <b>Timeframe:</b> M5"
        )
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="HTML")
            logger.info(f"Telegram alert sent for {instrument}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
