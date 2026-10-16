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
            return {"pair": pair, "action": "CALL", "score": 75, "expiry": "15 Seconds"}

        self.calculate_indicators()
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        rsi = last['rsi']
        ema_fast = last['ema_fast']
        ema_slow = last['ema_slow']
        is_green = last['close'] >= last['open']
        
        # Candle Body Strength (Scalping Volatility Check)
        candle_body = abs(last['close'] - last['open'])
        avg_body = abs(self.df['close'] - self.df['open']).tail(5).mean()

        # ----------------------------------------------------
        # 15-Second Scalping Logic & Quality Score Calculation
        # ----------------------------------------------------
        base_score = 60  # Starting base score

        # Check Signal Direction
        if ema_fast >= ema_slow or rsi > 50 or is_green:
            action = "CALL"
            reason = "Bullish Scalp Momentum & Buyer Pressure"

            # 1. Trend Alignment (EMA 3 > EMA 8)
            if ema_fast > ema_slow:
                base_score += 15

            # 2. Strong RSI Momentum
            if rsi > 55:
                base_score += 10
            elif rsi > 65:
                base_score += 15

            # 3. Candle Confirmation & Volatility
            if is_green:
                base_score += 5
            if candle_body > avg_body:
                base_score += 5  # Strong momentum candle

        else:
            action = "PUT"
            reason = "Bearish Scalp Pressure & Seller Trend"

            # 1. Trend Alignment (EMA 3 < EMA 8)
            if ema_fast < ema_slow:
                base_score += 15

            # 2. Strong RSI Bearish Momentum
            if rsi < 45:
                base_score += 10
            elif rsi < 35:
                base_score += 15

            # 3. Candle Confirmation & Volatility
            if not is_green:
                base_score += 5
            if candle_body > avg_body:
                base_score += 5  # Strong momentum candle

        # Cap Quality Score at max 100
        score = min(base_score, 100)

        return {
            "pair": pair,
            "action": action,
            "score": score,
            "reason": reason,
            "expiry": "15 Seconds",
            "entry_price": round(last['close'], 5)
        }
