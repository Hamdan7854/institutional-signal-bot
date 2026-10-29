import os

# Telegram Bot Token Ingestion
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# Default Market Analysis Parameters
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "BTC-USD")
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1h")
DEFAULT_PERIOD = os.getenv("DEFAULT_PERIOD", "1mo")

# Analytical Hyperparameters
SWING_LOOKBACK = int(os.getenv("SWING_LOOKBACK", "5"))
VOLUME_PROFILE_BINS = int(os.getenv("VOLUME_PROFILE_BINS", "50"))

# Cloud Server Port Configuration
PORT = int(os.getenv("PORT", "8080"))
