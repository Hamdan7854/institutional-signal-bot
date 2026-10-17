import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Real Forex & Pocket Option OTC Pairs Integrated
PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
    "EUR/GBP", "EUR/JPY", "GBP/JPY",
    "EUR/USD-OTC", "GBP/USD-OTC", "USD/JPY-OTC", "AUD/USD-OTC",
    "USD/CAD-OTC", "EUR/GBP-OTC", "NZD/USD-OTC", "GBP/JPY-OTC",
    "EUR/JPY-OTC", "USD/CHF-OTC"
]

CANDLE_DURATION_SEC = 15
COUNTDOWN_SECONDS = 5
EMA_FAST = 3
EMA_SLOW = 8
RSI_PERIOD = 5
MIN_QUALITY_SCORE = 85  # Strict High-Accuracy Filter for AmirFX Style Signals
