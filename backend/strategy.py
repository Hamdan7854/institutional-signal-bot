import pandas as pd
import numpy as np
import ta

class InstitutionalEngine:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def calculate_indicators(self):
        # 15-second scalping indicators
        self.df['ema_fast'] = ta.trend.ema_indicator(self.df['close'], window=3)
        self.df['ema_slow'] = ta.trend.ema_indicator(self.df['close'], window=8)
        self.df['rsi'] = ta.momentum.rsi(self.df['close'], window=5)

    def evaluate_signal(self, pair: str) -> dict:
        if len(self.df) < 10:
            return {"pair": pair, "action": "NO_TRADE", "score": 0, "accuracy": "0%", "reason": "Insufficient Data"}

        self.calculate_indicators()
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        rsi = last['rsi']
        ema_fast = last['ema_fast']
        ema_slow = last['ema_slow']
        prev_ema_fast = prev['ema_fast']
        prev_ema_slow = prev['ema_slow']

        is_green = last['close'] >= last['open']
        candle_body = abs(last['close'] - last['open'])
        avg_body = abs(self.df['close'] - self.df['open']).tail(5).mean()

        score = 65  # Base score for high probability
        action = "NO_TRADE"
        reason = ""

        # Bullish conditions
        bullish_cross = (prev_ema_fast <= prev_ema_slow) and (ema_fast > ema_slow)
        bullish_trend = ema_fast > ema_slow

        if bullish_trend and (rsi > 50) and is_green:
            score += 15
            if bullish_cross:
                score += 10
            if rsi > 60:
                score += 5
            if candle_body > avg_body:
                score += 5

            if score >= 85:
                action = "CALL"
                reason = "Strong Bullish Momentum & EMA Cross"

        # Bearish conditions
        bearish_cross = (prev_ema_fast >= prev_ema_slow) and (ema_fast < ema_slow)
        bearish_trend = ema_fast < ema_slow

        if bearish_trend and (rsi < 50) and (not is_green):
            score += 15
            if bearish_cross:
                score += 10
            if rsi < 40:
                score += 5
            if candle_body > avg_body:
                score += 5

            if score >= 85:
                action = "PUT"
                reason = "Strong Bearish Momentum & EMA Cross"

        score = min(score, 98)
        accuracy_str = f"{score}%"

        if action == "NO_TRADE":
            return {"pair": pair, "action": "NO_TRADE", "score": 0, "accuracy": "0%", "reason": "No Clear Setup"}

        return {
            "pair": pair,
            "action": action,
            "score": score,
            "accuracy": accuracy_str,
            "reason": reason,
            "expiry": "15 Seconds",
            "entry_price": round(last['close'], 5)
        }
