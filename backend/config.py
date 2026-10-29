import os

# Telegram Bot Token Ingestion
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# Default Market Analysis Parameters (1-minute timeframe set kiya hai)
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "EURUSD")
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1m")
DEFAULT_PERIOD = os.getenv("DEFAULT_PERIOD", "1d")

# Sabhi Major aur Minor Forex Pairs ki List
SUPPORTED_FOREX_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "USDCHF",
    "EURGBP", "EURJPY", "EURAUD", "EURCAD", "EURNZD", "EURCHF",
    "GBPJPY", "GBPAUD", "GBPCAD", "GBPNZD", "GBPCHF",
    "AUDJPY", "AUDCAD", "AUDNZD", "AUDCHF",
    "CADJPY", "CADCHF", "NZDJPY", "NZDCHF"
]

# Analytical Hyperparameters
SWING_LOOKBACK = int(os.getenv("SWING_LOOKBACK", "5"))
VOLUME_PROFILE_BINS = int(os.getenv("VOLUME_PROFILE_BINS", "50"))

# Cloud Server Port Configuration
PORT = int(os.getenv("PORT", "8080"))
