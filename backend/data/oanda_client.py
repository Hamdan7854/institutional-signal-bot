import requests
import logging
from config import BASE_URL, OANDA_API_KEY

logger = logging.getLogger(__name__)

class OandaClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {OANDA_API_KEY}",
            "Content-Type": "application/json"
        }

    def fetch_candles(self, instrument: str = "EUR_USD", granularity: str = "M5", count: int = 150):
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
            candles = data.get("candles", [])
            
            parsed = []
            for c in candles:
                if not c.get("complete", False):
                    continue
                mid = c.get("mid", {})
                parsed.append({
                    "time": c.get("time"),
                    "open": float(mid.get("o", 0)),
                    "high": float(mid.get("h", 0)),
                    "low": float(mid.get("l", 0)),
                    "close": float(mid.get("c", 0)),
                    "volume": int(c.get("volume", 0))
                })
            return parsed
        except Exception as e:
            logger.error(f"Error fetching candles for {instrument} [{granularity}]: {e}")
            return []
