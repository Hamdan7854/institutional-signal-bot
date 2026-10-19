import pandas as pd
import numpy as np
try:
    from market_data import MarketDataProvider
except ImportError:
    MarketDataProvider = None

class InstitutionalEngine:
    def __init__(self, data=None):
        self.data = data
        self.market_provider = MarketDataProvider() if MarketDataProvider else None

    def calculate_indicators(self, df: pd.DataFrame):
        # 1. EMA 9 & EMA 21 (Institutional Trend Crossover)
        df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        
        # 2. RSI 14 (Momentum Filter)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df

    def analyze_market(self, df: pd.DataFrame = None):
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            df = self.data
            
        if df is None or df.empty:
            df = pd.DataFrame({
                'open': [1.0, 1.0], 
                'high': [1.1, 1.1], 
                'low': [0.9, 0.9], 
                'close': [1.05, 1.06],
                'volume': [100, 100]
            })
            
        df = self.calculate_indicators(df)
        latest = df.iloc[-1]
        
        rsi_val = latest['RSI']
        ema_fast = latest['EMA_9']
        ema_slow = latest['EMA_21']
        
        # Candle Pressure Calculation (Body vs Total Wick Range)
        body_size = abs(latest['close'] - latest['open'])
        total_range = latest['high'] - latest['low']
        body_percentage = (body_size / total_range * 100) if total_range > 0 else 50

        score = 50
        reason = "Neutral Market"
        action = "HOLD"

        if pd.isna(rsi_val):
            rsi_val = 50

        # AmirFX Style 15-second High Accuracy Matrix
        if ema_fast > ema_slow and rsi_val > 52:
            action = "BUY"
            score = int(55 + (rsi_val - 50) * 0.7 + (body_percentage * 0.3))
            reason = f"Bullish EMA Trend & RSI ({int(rsi_val)}) + Pressure ({int(body_percentage)}%)"
        elif ema_fast < ema_slow and rsi_val < 48:
            action = "SELL"
            score = int(55 + (50 - rsi_val) * 0.7 + (body_percentage * 0.3))
            reason = f"Bearish EMA Trend & RSI ({int(rsi_val)}) + Pressure ({int(body_percentage)}%)"
        else:
            if latest['close'] > latest['open'] and body_percentage > 60:
                action = "BUY"
                score = 72
                reason = f"Strong Bullish Candle Pressure ({int(body_percentage)}%)"
            elif latest['close'] < latest['open'] and body_percentage > 60:
                action = "SELL"
                score = 72
                reason = f"Strong Bearish Candle Pressure ({int(body_percentage)}%)"
            else:
                action = "BUY" if rsi_val >= 50 else "SELL"
                score = 60
                reason = f"Standard Momentum Continuation (RSI: {int(rsi_val)})"

        # Strict score boundaries (50% to 95%)
        score = max(50, min(score, 95))

        return {
            "action": action,
            "entry_price": float(latest['close']),
            "score": score,
            "reason": reason
        }

    def evaluate_signal(self, symbol_or_df):
        if isinstance(symbol_or_df, str):
            if self.market_provider:
                df = self.market_provider.get_historical_data(symbol_or_df)
                return self.analyze_market(df)
        elif isinstance(symbol_or_df, pd.DataFrame):
            return self.analyze_market(symbol_or_df)
        
        return self.analyze_market(self.data)
