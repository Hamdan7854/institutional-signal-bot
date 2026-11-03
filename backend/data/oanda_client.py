import requests
import logging
from backend.config import BASE_URL, OANDA_API_KEY

logger = logging.getLogger(__name__)

class OandaClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {OANDA_API_KEY}",
            "Content-Type": "application/json"
        }

    def fetch_candles(self, instrument: str = "EUR_USD", granularity: str = "M5", count: int = 100):
        url = f"{BASE_URL}/instruments/{instrument}/candles"
        params = {
            "count": count,
            "granularity": granularity,
            "price": "M"
        }
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("candles", [])
        except Exception as e:
            logger.error(f"Error fetching candles for {instrument}: {e}")
            return []
