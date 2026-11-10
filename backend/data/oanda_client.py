"""OANDA v20 REST client (sirf requests, koi extra library nahi)."""
import time
import requests
import config

HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaClient:
    def __init__(self, token=None, env=None):
        self.token = token or getattr(config, "OANDA_API_KEY", None) or getattr(config, "OANDA_TOKEN", None)
        env_val = env or getattr(config, "OANDA_ENVIRONMENT", None) or getattr(config, "OANDA_ENV", "practice")
        self.base = HOSTS.get(env_val, HOSTS["practice"])
        
        if not self.token:
            raise RuntimeError("OANDA_API_KEY set nahi hai (environment variable).")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {self.token}"})

    def _get(self, path, params=None, retries=3):
        for i in range(retries):
            try:
                r = self.s.get(self.base + path, params=params, timeout=15)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (i + 1))
                    continue
                raise RuntimeError(f"OANDA {r.status_code}: {r.text[:200]}")
            except requests.RequestException:
                time.sleep(1.5 * (i + 1))
        raise RuntimeError("OANDA request baar baar fail hui")

    def candles(self, instrument, granularity="M1", count=500, to_time=None, price="MBA"):
        """price: M=mid, MBA=mid+bid+ask (spread ke liye)."""
        params = {"granularity": granularity, "price": price, "count": count}
        if to_time:
            params["to"] = to_time
        return self._get(f"/v3/instruments/{instrument}/candles", params).get("candles", [])

    def history(self, instrument, n=30000, granularity="M1", price="MBA"):
        """Peeche ki taraf paginate kar ke n complete candles (max 5000 per call)."""
        out, to_time = [], None
        while len(out) < n:
            batch = self.candles(instrument, granularity, min(5000, n - len(out) + 1), to_time, price)
            batch = [c for c in batch if c.get("complete") and (to_time is None or c["time"] < to_time)]
            if not batch:
                break
            out = batch + out
            to_time = batch[0]["time"]
        return out[-n:]
