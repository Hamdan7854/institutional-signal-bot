import os
from dotenv import load_dotenv

load_dotenv()

OANDA_API_KEY = os.getenv("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT", "practice")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

OANDA_URLS = {
    "practice": "https://api-fxpractice.oanda.com/v3",
    "live": "https://api-fxtrade.oanda.com/v3"
}

BASE_URL = OANDA_URLS.get(OANDA_ENVIRONMENT, OANDA_URLS["practice"])

# Verified OANDA Live Forex Pairs matching Pocket Option Live Currencies
INSTRUMENTS = [
    "EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "EUR_GBP",
    "NZD_USD", "USD_CHF", "CAD_JPY", "EUR_JPY", "AUD_JPY", "GBP_JPY"
]

# MICP-60 Timeframes mapping (1 min to 60 mins)
TIMEFRAMES = {
    "M1": "1 Minute",
    "M5": "5 Minutes",
    "M15": "15 Minutes",
    "M30": "30 Minutes",
    "H1": "60 Minutes"
}
