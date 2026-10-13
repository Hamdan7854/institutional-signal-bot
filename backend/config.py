import os

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Pairs to Scan (Major Forex Pairs)
PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "EUR/GBP"]

# Institutional Strategy Configuration
CANDLE_DURATION_SEC = 60
BODY_MIN_RATIO = 0.60  # Candle body must be at least 60% of full range
RSI_PERIOD = 14
EMA_FAST = 9
EMA_SLOW = 21
STOCH_K = 14
STOCH_D = 3

# Safety Thresholds
MIN_QUALITY_SCORE = 85  # Institutional quality threshold
