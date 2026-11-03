import pandas as pd
import numpy as np

class MICPFeatureEngine:
    @staticmethod
    def process_features(candles_data):
        if not candles_data or len(candles_data) < 30:
            return None
        
        df = pd.DataFrame(candles_data)
        df['time'] = pd.to_datetime(df['time'])
        
        # Moving Averages & Trend
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        
        # RSI Momentum
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volatility / ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        df['atr'] = ranges.max(axis=1).rolling(14).mean()

        return df.fillna(0)
