import pandas as pd

class CandleBuilder:
    @staticmethod
    def parse_oanda_candles(candles_data):
        parsed = []
        for c in candles_data:
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
        df = pd.DataFrame(parsed)
        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])
        return df
