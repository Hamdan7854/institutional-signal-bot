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
INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "EUR_GBP"]
TIMEFRAME = "M5"
