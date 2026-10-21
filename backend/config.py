import os

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_HERE")

# Deriv & Strategy Configuration
APP_ID = int(os.getenv("DERIV_APP_ID", 1089))
DERIV_TOKEN = os.getenv("DERIV_API_TOKEN", "YOUR_DERIV_API_TOKEN_HERE")
SYMBOL = os.getenv("DERIV_SYMBOL", "R_100")  # Volatility 100 Index
STAKE_BASE = float(os.getenv("STAKE_BASE", 1.0))
MARTINGALE_MULTIPLIER = float(os.getenv("MARTINGALE_MULTIPLIER", 2.0))
MAX_MARTINGALE_STEPS = int(os.getenv("MAX_MARTINGALE_STEPS", 3))
SMA_FAST_PERIOD = int(os.getenv("SMA_FAST_PERIOD", 5))
SMA_SLOW_PERIOD = int(os.getenv("SMA_SLOW_PERIOD", 15))
