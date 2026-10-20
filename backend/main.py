import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import config
from market_data import MarketDataProvider
from strategy import HighProbabilityStrategy

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

data_provider = MarketDataProvider()
strategy_engine = HighProbabilityStrategy()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = (
        "<b>5-Minute Forex Signal System Active</b>\n\n"
        f"Your Chat ID: <code>{chat_id}</code>\n\n"
        "Commands:\n"
        "• <code>/signal</code> - Scan all monitored pairs and get active signals\n"
        "• <code>/signal EUR/USD</code> - Calculate signal for a specific pair\n"
        "• <code>/scan</code> - Quick scan all pairs\n"
        "• <code>/pairs</code> - List active currency pairs"
    )
    await update.message.reply_text(msg, parse_mode='HTML')

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Agar user ne sirf /signal bheja hai bina kisi pair ke, toh saare pairs scan honge jo criteria meet karenge
    if not context.args:
        await update.message.reply_text("🔎 Scanning all forex pairs for strategy criteria...", parse_mode='HTML')
        signals_found = 0

        for pair in config.FOREX_PAIRS:
            try:
                df = await data_provider.fetch_ohlcv(pair)
                res = strategy_engine.generate_signal(df)
                if res['signal'] != "NEUTRAL":
                    signals_found += 1
                    direction_label = "🟢 CALL (BUY)" if res['signal'] == "CALL" else "🔴 PUT (SELL)"
                    output = (
                        "<b>HIGH ACCURACY SM SIGNAL</b>\n\n"
                        f"• <b>Asset:</b> {pair}\n"
                        f"• <b>Direction:</b> {direction_label}\n"
                        f"• <b>Entry Price:</b> {res['price']:.5f}\n"
                        f"• <b>Timeframe:</b> 5 Minutes\n"
                        f"• <b>Expiry Duration:</b> 5 Minutes\n"
                        f"• <b>Confidence Rating:</b> {res['confidence']}%\n"
                        f"• <b>Confluence Mechanics:</b>\n" + "\n".join([f"  - {r}" for r in res['reasons']])
                    )
                    await update.message.reply_text(output, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Scan failure on {pair}: {e}")

        if signals_found == 0:
            await update.message.reply_text("ℹ️ Scan Complete: No pairs currently meet strict confluence criteria.")
        return

    # Agar user ne specific pair diya hai (e.g., /signal EURUSD)
    raw_pair = context.args[0].upper()
    pair = f"{raw_pair[:3]}/{raw_pair[3:]}" if "/" not in raw_pair and len(raw_pair) == 6 else raw_pair

    await update.message.reply_text(f"Analyzing SM market structures for <b>{pair}</b>...", parse_mode='HTML')

    try:
        df = await data_provider.fetch_ohlcv(pair)
        res = strategy_engine.generate_signal(df)

        if res['signal'] == "NEUTRAL":
            output = (
                f"<b>NO SIGNAL GENERATED ({pair})</b>\n\n"
                "<i>Market Regime: Neutral / High Friction</i>\n"
                "The engine has suppressed entry due to unaligned confluence criteria."
            )
        else:
            direction_label = "🟢 CALL (BUY)" if res['signal'] == "CALL" else "🔴 PUT (SELL)"
            output = (
                "<b>HIGH ACCURACY SM SIGNAL</b>\n\n"
                f"• <b>Asset:</b> {pair}\n"
                f"• <b>Direction:</b> {direction_label}\n"
                f"• <b>Entry Price:</b> {res['price']:.5f}\n"
                f"• <b>Timeframe:</b> 5 Minutes\n"
                f"• <b>Expiry Duration:</b> 5 Minutes\n"
                f"• <b>Confidence Rating:</b> {res['confidence']}%\n"
                f"• <b>Confluence Mechanics:</b>\n" + "\n".join([f"  - {r}" for r in res['reasons']])
            )
        await update.message.reply_text(output, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error evaluating pair {pair}: {e}")
        await update.message.reply_text(f"❌ Processing Error: {str(e)}")

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await signal_command(update, context)

async def handle_health_check(request):
    return web.Response(text="Signal Bot Daemon Alive", status=200)

async def main():
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("scan", scan_command))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    web_app = web.Application()
    web_app.router.add_get("/", handle_health_check)
    web_app.router.add_get("/health", handle_health_check)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()

    logger.info(f"Engine operational. HTTP Server running on port {config.PORT}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
