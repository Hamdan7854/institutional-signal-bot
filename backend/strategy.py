import pandas as pd
import numpy as np
import ta

class InstitutionalEngine:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def calculate_indicators(self):
        self.df['ema_fast'] = ta.trend.ema_indicator(self.df['close'], window=3)
        self.df['ema_slow'] = ta.trend.ema_indicator(self.df['close'], window=8)
        self.df['rsi'] = ta.momentum.rsi(self.df['close'], window=5)

    def evaluate_signal(self, pair: str) -> dict:
        if len(self.df) < 10:
            return {"pair": pair, "action": "CALL", "score": 95, "expiry": "15 Seconds", "reason": "Fast Momentum"}

        self.calculate_indicators()
        last = self.df.iloc[-1]
        
        rsi = last['rsi']
        ema_fast = last['ema_fast']
        ema_slow = last['ema_slow']
        is_green = last['close'] >= last['open']

        if ema_fast >= ema_slow or rsi > 50 or is_green:
            action = "CALL"
            reason = "Bullish Momentum & Buyer Pressure"
            score = 92
        else:
            action = "PUT"
            reason = "Bearish Pressure & Seller Trend"
            score = 88

        return {
            "pair": pair,
            "action": action,
            "score": score,
            "reason": reason,
            "expiry": "15 Seconds",
            "entry_price": round(last['close'], 5)
        }
