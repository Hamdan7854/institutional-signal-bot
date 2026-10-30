import os

# Telegram Bot Setup
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# All Major Forex Pairs
FOREX_PAIRS = [
    "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "EURGBP"
]

# Timeframe Settings for Multi-Timeframe Analysis
PRIMARY_TIMEFRAME = "5m"  # Base candle timeframe
HTF_TIMEFRAME = "1h"       # Higher timeframe context
LOOKBACK_PERIOD = 100     # Candle lookback length
