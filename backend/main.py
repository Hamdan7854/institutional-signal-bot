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
    msg = (
        "<b>5-Minute Forex Signal System Active</b>\n\n"
        "Commands:\n"
        "• <code>/signal EUR/USD</code> - Calculate signal for a specific pair\n"
        "• <code>/scan</code> - Scan all monitored currency pairs\n"
        "• <code>/pairs</code> - List active currency pairs"
    )
    await update.message.reply_text(msg, parse_mode='HTML')

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: <code>/signal EUR/USD</code>", parse_mode='HTML')
        return

    raw_pair = context.args[0].upper()
    pair = f"{raw_pair[:3]}/{raw_pair[3:]}" if "/" not in raw_pair and len(raw_pair) == 6 else raw_pair

    await update.message.reply_text(f"Analyzing 5M market structures for <b>{pair}</b>...", parse_mode='HTML')

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
                f"<b>HIGH ACCURACY 5M SIGNAL</b>\n\n"
                f"<b>Asset:</b> {pair}\n"
                f"<b>Direction:</b> {direction_label}\n"
                f"<b>Entry Price:</b> {res['price']:.5f}\n"
                f"<b>Timeframe:</b> 5 Minutes\n"
                f"<b>Expiry Duration:</b> 5 Minutes\n"
                f"<b>Confidence Rating:</b> {res['confidence']}%\n\n"
                f"<b>Confluence Mechanics:</b>\n• " + "\n• ".join(res['reasons'])
            )
        await update.message.reply_text(output, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error evaluating pair {pair}: {e}")
        await update.message.reply_text(f"❌ Processing Error: {str(e)}")

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Initiating cross-pair matrix scan...")
    signals_found = 0

    for pair in config.FOREX_PAIRS:
        try:
            df = await data_provider.fetch_ohlcv(pair)
            res = strategy_engine.generate_signal(df)
            if res['signal'] != "NEUTRAL":
                signals_found += 1
                direction_label = "🟢 CALL" if res['signal'] == "CALL" else "🔴 PUT"
                output = (
                    f"🎯 <b>ALERT: {pair}</b>\n"
                    f"<b>Direction:</b> {direction_label} | <b>Expiry:</b> 5M\n"
                    f"<b>Entry:</b> {res['price']:.5f} | <b>Confidence:</b> {res['confidence']}%"
                )
                await update.message.reply_text(output, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Scan failure on {pair}: {e}")

    if signals_found == 0:
        await update.message.reply_text("ℹ️ Matrix Scan Complete: No pairs currently meet strict confluence criteria.")

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

    # Embedded HTTP server to satisfy Render port binding health checks
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
