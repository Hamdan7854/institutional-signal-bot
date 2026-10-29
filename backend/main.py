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
        "This bot applies Smart Money Concepts (SMC), Fair Value Gaps (FVG), "
        "and Volume Profile Analysis to predict next-candle price targets with 5-digit precision.\n\n"
        "*Usage*:\n"
        "`/signal [symbol] [timeframe]`\n\n"
        "*Examples*:\n"
        "`/signal EURUSD 1h`\n"
        "`/signal USDJPY 15m`\n"
        "`/signal AUDCAD 5m`"
    )
    await update.message.reply_markdown(welcome_text)

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Handles the Telegram /signal command and formats target price reports. """
    args = context.args
    symbol = args[0].upper() if len(args) > 0 else config.DEFAULT_SYMBOL
    timeframe = args[1] if len(args) > 1 else config.DEFAULT_TIMEFRAME

    await update.message.reply_text(f"🔍 Analyzing market structure & calculating targets for {symbol} ({timeframe})...")

    try:
        # Step 1: Ingest Market Data
        reader = MarketDataReader()
        df = reader.fetch_ohlcv(symbol=symbol, period=config.DEFAULT_PERIOD, interval=timeframe)

        # Step 2: Compute Predictive Strategy Metrics
        engine = SMCStrategyEngine(
            swing_lookback=config.SWING_LOOKBACK,
            volume_bins=config.VOLUME_PROFILE_BINS
        )
        signal = engine.generate_predictive_signal(df, symbol=symbol)

        # Determine decimal formatting based on asset type (5 digits for forex, 2 for crypto/others)
        is_forex = "=X" in symbol or len(symbol.replace("/", "").replace("-", "")) == 6
        precision = 5 if is_forex else 2
        fmt = f"{{:.{precision}f}}"

        # Estimate target duration based on timeframe string
        duration_map = {
            "1m": "1 to 3 Candles (approx. 1-3 minutes)",
            "5m": "1 to 3 Candles (approx. 5-15 minutes)",
            "15m": "1 to 3 Candles (approx. 15-45 minutes)",
            "1h": "1 to 3 Candles (approx. 1 to 3 hours)",
            "4h": "1 to 3 Candles (approx. 4 to 12 hours)",
            "1d": "1 to 3 Candles (approx. 1 to 3 days)"
        }
        estimated_time = duration_map.get(timeframe.lower(), "Next 1 to 3 Candles")

        # Step 3: Format and Send Telegram Markdown Output
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

    except Exception as error:
        logger.error(f"Error processing signal: {str(error)}")
        await update.message.reply_text(f"❌ Error generating signal for {symbol}: {str(error)}")

def main():
    # Launch HTTP server thread for Render web service binding
    server_thread = threading.Thread(target=run_http_server)
    server_thread.daemon = True
    server_thread.start()

    if config.TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("TELEGRAM_BOT_TOKEN is unconfigured. Set the environment variable.")
        return

    # Initialize Telegram Application
    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("signal", signal_command))

    logger.info("Signal Bot daemon started. Beginning polling loop...")
    application.run_polling()

if __name__ == '__main__':
    main()
