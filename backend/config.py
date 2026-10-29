import os

# Telegram Bot Setup
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# Major Forex Pairs
FOREX_PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
    "USDCAD=X", "USDCHF=X", "NZDUSD=X", "EURGBP=X",
    "EURJPY=X", "GBPJPY=X"
]

# Timeframe Settings for Multi-Timeframe Analysis
PRIMARY_TIMEFRAME = "5m"  # Base candle timeframe
HTF_TIMEFRAME = "1h"       # Higher timeframe context
LOOKBACK_PERIOD = 100     # Candle lookback length
