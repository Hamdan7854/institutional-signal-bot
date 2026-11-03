import pandas as pd

class PredictionEngine:
    @staticmethod
    def generate_signal(df: pd.DataFrame):
        if df.empty or len(df) < 2:
            return None, 0.0

        latest = df.iloc[-1]
        rsi = latest.get('rsi', 50)
        close = latest.get('close', 0)
        sma = latest.get('sma_20', 0)

        if rsi < 30 and close > sma:
            return "BUY", 0.85
        elif rsi > 70 and close < sma:
            return "SELL", 0.85

        return "HOLD", 0.50
