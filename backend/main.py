import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import config
from market_dayallta import MarketDataReader
from startegy import SMCStartegyEngine

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
        "and Volume Profile Analysis to predict next-candle price targets.\n\n"
        "*Usage*:\n"
        "`/signal [symbol] [timeframe]`\n\n"
        "*Examples*:\n"
        "`/signal BTC-USD 1h`\n"
        "`/signal ETH-USD 15m`\n"
        "`/signal EURUSD=X 4h`"
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

        # Step 3: Format and Send Telegram Markdown Output
        direction_icon = "🟢" if signal['bias'] == "BULLISH" else "🔴"
        
        report_message = (
            f"🎯 *INSTITUTIONAL SIGNAL REPORT*\n"
            f"────────────────────────\n"
            f"📌 *Asset*: `{signal['symbol']}`\n"
            f"⏱ *Timeframe*: `{timeframe}`\n"
            f"💵 *Current Price*: `{signal['current_price']:.2f}`\n"
            f"{direction_icon} *Market Structure Bias*: *{signal['bias']}*\n\n"
            f"🔮 *PREDICTED NEXT CANDLE TARGET*: `{signal['predicted_target_price']:.2f}`\n\n"
            f"📊 *Institutional Level Mapping*:\n"
            f"• *Point of Control (POC)*: `{signal['poc_price']:.2f}`\n"
            f"• *Buy-Side Liquidity (BSL)*: `{signal['bsl_target']:.2f}`\n"
            f"• *Sell-Side Liquidity (SSL)*: `{signal['ssl_target']:.2f}`\n\n"
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
