import os

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Scan Pairs (Major Forex Pairs)
PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "EUR/GBP"]

# Timing & Execution Rules
CANDLE_DURATION_SEC = 60
BODY_MIN_RATIO = 0.60  # Minimum 60% solid body for strong breakout
COUNTDOWN_SECONDS = 5   # Warning alert before candle close

# Layer 1: Trend Filter (EMA 21 & EMA 50)
EMA_FAST = 21
EMA_SLOW = 50

# Layer 3: Momentum Indicators
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ADX_PERIOD = 14
ADX_MIN_THRESHOLD = 25  # Strong trending market confirmation

# Backtesting & Key Levels Window
LOOKBACK_CANDLES = 50

# Layer 5: Strict Institutional Scoring
MIN_QUALITY_SCORE = 90  # High-grade institutional confluence requirement
