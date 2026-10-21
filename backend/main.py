import asyncio
import json
import logging
import sys
import websockets
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config import (
    TELEGRAM_BOT_TOKEN, APP_ID, DERIV_TOKEN, SYMBOL,
    SMA_FAST_PERIOD, SMA_SLOW_PERIOD
)
from strategy import TradingStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

class TelegramSignalBot:
    def __init__(self):
        self.ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"
        self.price_history = []

    async def fetch_live_ticks(self):
        """Background task with additional_headers to bypass connection blocks."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        while True:
            try:
                # Fixed: extra_headers changed to additional_headers
                async with websockets.connect(self.ws_url, additional_headers=headers) as ws:
                    await ws.send(json.dumps({"authorize": DERIV_TOKEN}))
                    await ws.recv()
                    
                    await ws.send(json.dumps({"ticks": SYMBOL, "subscribe": 1}))
                    
                    async for message in ws:
                        data = json.loads(message)
                        if data.get("msg_type") == "tick":
                            price = float(data["tick"]["quote"])
                            self.price_history.append(price)
                            if len(self.price_history) > 150:
                                self.price_history.pop(0)
            except Exception as e:
                logging.error(f"Deriv WS Connection error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def handle_signal_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Triggered instantly when user sends /signal on Telegram."""
        await update.message.reply_text("🔍 Analyzing market data across platforms within seconds...")

        if len(self.price_history) < SMA_SLOW_PERIOD:
            await update.message.reply_text("⚠️ Still collecting tick history. Please try again in 5 seconds.")
            return

        signal, reason = TradingStrategy.evaluate_signal(
            self.price_history, SMA_FAST_PERIOD, SMA_SLOW_PERIOD
        )

        current_price = self.price_history[-1] if self.price_history else 0.0
        response_text = (
            f"📊 **Market Analysis Report** ({SYMBOL})\n\n"
            f"💵 **Current Price:** {current_price}\n"
            f"🎯 **Generated Signal:** `{signal}`\n"
            f"📝 **Details:** {reason}"
        )
        await update.message.reply_text(response_text, parse_mode="Markdown")

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.fetch_live_ticks())

        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("signal", self.handle_signal_command))
        
        logging.info("Telegram Bot is starting polling...")
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    bot = TelegramSignalBot()
    bot.run()
