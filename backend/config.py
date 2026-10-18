import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 100% Real Market Forex Pairs (OTC Pairs Removed)
PAIRS = [
    "EUR/JPY", "GBP/JPY", "EUR/CAD", "AUD/CAD", "AUD/CHF", "AUD/USD",
    "CAD/CHF", "CAD/JPY", "CHF/JPY", "EUR/CHF", "EUR/GBP", "EUR/USD",
    "GBP/AUD", "GBP/CAD", "GBP/CHF", "GBP/USD", "USD/CAD", "USD/CHF",
    "USD/JPY", "AUD/JPY", "EUR/AUD"
]

CANDLE_DURATION_SEC = 15
COUNTDOWN_SECONDS = 5
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
MIN_QUALITY_SCORE = 80  # Strict High-Accuracy Filter
