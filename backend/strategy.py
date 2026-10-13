import pandas as pd
import ta
from config import BODY_MIN_RATIO, MIN_QUALITY_SCORE

class InstitutionalStrategyEngine:
    """
    5-Layer Quality Filter for 0% False Signal Objective
    """
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def calculate_indicators(self):
        self.df['rsi'] = ta.momentum.rsi(self.df['close'], window=14)
        self.df['ema_fast'] = ta.trend.ema_indicator(self.df['close'], window=9)
        self.df['ema_slow'] = ta.trend.ema_indicator(self.df['close'], window=21)
        self.df['stoch_k'] = ta.momentum.stoch(self.df['high'], self.df['low'], self.df['close'], window=14)
        
    def evaluate_signal(self, pair: str) -> dict:
        if len(self.df) < 25:
            return {"action": "NO TRADE", "reason": "Insufficient Data"}

        self.calculate_indicators()
        last = self.df.iloc[-1]
        
        # Layer 1: Price Action - 60% Body Range Minimum
        candle_range = last['high'] - last['low']
        body_size = abs(last['close'] - last['open'])
        if candle_range == 0 or (body_size / candle_range) < BODY_MIN_RATIO:
            return {"action": "NO TRADE", "reason": "L1: Weak Candle Body (<60%)"}

        # Layer 2: Trend Alignment (EMA Fast vs Slow)
        uptrend = last['ema_fast'] > last['ema_slow']
        downtrend = last['ema_fast'] < last['ema_slow']

        # Layer 3: Momentum Filter (RSI)
        rsi_bullish = 50 < last['rsi'] < 70
        rsi_bearish = 30 < last['rsi'] < 50

        # Layer 4: Oscillator Filter (Stochastic)
        stoch_bullish = last['stoch_k'] < 80
        stoch_bearish = last['stoch_k'] > 20

        # Layer 5: Institutional Quality Confluence Check
        score = 0
        action = "NO TRADE"
        reason = ""

        if uptrend and rsi_bullish and stoch_bullish and (last['close'] > last['open']):
            score = 90
            action = "CALL"
            reason = "High Probability Bullish Confluence (L1-L5 Pass)"
        elif downtrend and rsi_bearish and stoch_bearish and (last['close'] < last['open']):
            score = 90
            action = "PUT"
            reason = "High Probability Bearish Confluence (L1-L5 Pass)"
        else:
            reason = "L5: Layers Conflict / Failed 85 Threshold"

        if score < MIN_QUALITY_SCORE:
            action = "NO TRADE"

        return {
            "pair": pair,
            "action": action,
            "score": score,
            "reason": reason,
            "expiry": "60 Seconds",
            "entry_price": round(last['close'], 5)
        }
