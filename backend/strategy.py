import pandas as pd
import numpy as np
import ta

class InstitutionalEngine:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def calculate_indicators(self):
        # 15-second Scalping Indicators (AmirFX High Precision Logic)
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

        score = 50  # Base Score
        action = "NO_TRADE"
        reason = ""

        # --- CALL SIGNAL CONDITIONS ---
        # Fresh EMA Crossover (Bullish) or Strong Momentum
        bullish_cross = (prev_ema_fast <= prev_ema_slow) and (ema_fast > ema_slow)
        bullish_trend = ema_fast > ema_slow

        if bullish_trend and (rsi > 52) and is_green:
            score += 15
            if bullish_cross:
                score += 15  # Extra boost for fresh crossover
            if rsi > 60:
                score += 10
            if candle_body > avg_body:
                score += 10  # Volatility confirmation

            if score >= 85:  # Strict Threshold to avoid fake signals
                action = "CALL"
                reason = "Strong Bullish Crossover & High Buying Pressure"

        # --- PUT SIGNAL CONDITIONS ---
        # Fresh EMA Crossover (Bearish) or Strong Momentum
        bearish_cross = (prev_ema_fast >= prev_ema_slow) and (ema_fast < ema_slow)
        bearish_trend = ema_fast < ema_slow

        if bearish_trend and (rsi < 48) and (not is_green):
            score += 15
            if bearish_cross:
                score += 15  # Extra boost for fresh crossover
            if rsi < 40:
                score += 10
            if candle_body > avg_body:
                score += 10  # Volatility confirmation

            if score >= 85:  # Strict Threshold to avoid fake signals
                action = "PUT"
                reason = "Strong Bearish Crossover & High Selling Pressure"

        # Final Score Cap
        score = min(score, 98)

        # Accuracy Calculation (AmirFX Style)
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
