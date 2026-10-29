import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config
from market_dayallta import MarketDataReader
from strategy import SMCStrategyEngine

# Logging Configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask Web Server Instance for Render Binding
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Institutional Predictive Signal Bot is Active.", 200

def run_http_server():
    app.run(host="0.0.0.0", port=config.PORT)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Handles the Telegram /start command. """
    welcome_text = (
        "🤖 *Institutional Market Structure Signal Bot*\n\n"
        "Sending `/signal` without arguments will now scan *all* Forex pairs on **1-minute candles** automatically!\n\n"
        "*Usage*:\n"
        "`/signal` -> Scans all Forex pairs on 1m\n"
        "`/signal EURUSD 1m` -> Scans a specific pair"
    )
    await update.message.reply_markdown(welcome_text)

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Scans all or specific forex pairs on 1-minute timeframe and sends reports. """
    args = context.args
    
    if len(args) > 0:
        symbols_to_scan = [args[0].upper()]
        timeframe = args[1] if len(args) > 1 else "1m"
    else:
        symbols_to_scan = config.SUPPORTED_FOREX_PAIRS
        timeframe = "1m"

    await update.message.reply_text(f"🔍 Scanning market structure across available Forex pairs on {timeframe} timeframe...")

    reader = MarketDataReader()
    engine = SMCStrategyEngine(
        swing_lookback=config.SWING_LOOKBACK,
        volume_bins=config.VOLUME_PROFILE_BINS
    )

    success_count = 0
    for symbol in symbols_to_scan:
        try:
            df = reader.fetch_ohlcv(symbol=symbol, period=config.DEFAULT_PERIOD, interval=timeframe)
            signal = engine.generate_predictive_signal(df, symbol=symbol)

            is_forex = "=X" in symbol or len(symbol.replace("/", "").replace("-", "")) == 6
            precision = 5 if is_forex else 2
            fmt = f"{{:.{precision}f}}"

            duration_map = {
                "1m": "1 to 3 Candles (approx. 1-3 minutes)",
                "5m": "1 to 3 Candles (approx. 5-15 minutes)",
                "15m": "1 to 3 Candles (approx. 15-45 minutes)",
                "1h": "1 to 3 Candles (approx. 1 to 3 hours)"
            }
            estimated_time = duration_map.get(timeframe.lower(), "Next 1 to 3 Candles")

            direction_icon = "🟢" if signal['bias'] == "BULLISH" else "🔴"
            
            current_price_str = fmt.format(signal['current_price'])
            predicted_target_str = fmt.format(signal['predicted_target_price'])
            poc_str = fmt.format(signal['poc_price'])
            bsl_str = fmt.format(signal['bsl_target'])
            ssl_str = fmt.format(signal['ssl_target'])

            report_message = (
                f"🎯 *INSTITUTIONAL SIGNAL REPORT*\n"
                f"────────────────────────\n"
                f"📌 *Asset*: `{signal['symbol']}`\n"
                f"⏱ *Timeframe*: `{timeframe}`\n"
                f"💵 *Current Price*: `{current_price_str}`\n"
                f"{direction_icon} *Market Structure Bias*: *{signal['bias']}*\n\n"
                f"🔮 *PREDICTED NEXT CANDLE TARGET*: `{predicted_target_str}`\n"
                f"⏳ *Estimated Target Duration*: `{estimated_time}`\n\n"
                f"📊 *Institutional Level Mapping*:\n"
                f"• *Point of Control (POC)*: `{poc_str}`\n"
                f"• *Buy-Side Liquidity (BSL)*: `{bsl_str}`\n"
                f"• *Sell-Side Liquidity (SSL)*: `{ssl_str}`\n\n"
                f"🧠 *Confluence Rationale*:\n_{signal['confluence_reason']}_\n"
                f"────────────────────────"
            )
            await update.message.reply_markdown(report_message)
            success_count += 1
        except Exception as err:
            logger.error(f"Skipping {symbol} due to error: {str(err)}")
            continue

    if success_count == 0:
        await update.message.reply_text("❌ Kisi bhi pair ka live data fetch nahi ho saka. Dobara try karein.")

def main():
    server_thread = threading.Thread(target=run_http_server)
    server_thread.daemon = True
    server_thread.start()

    if config.TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("TELEGRAM_BOT_TOKEN is unconfigured.")
        return

    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("signal", signal_command))

    logger.info("Signal Bot daemon started successfully.")
    application.run_polling()

if __name__ == '__main__':
    main()
