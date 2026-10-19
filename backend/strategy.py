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
        # 1. Keltner Channels (20 EMA baseline, 2 ATR outer bands)
        df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
        
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        df['kc_upper'] = df['EMA_20'] + (2 * df['atr'])
        df['kc_lower'] = df['EMA_20'] - (2 * df['atr'])
        
        # 2. RSI 14 (50 Midline Momentum Threshold)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 3. Trend Filter (EMA 9 & EMA 21)
        df['EMA_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['EMA_21'] = df['close'].ewm(span=21, adjust=False).mean()
        
        return df

    def analyze_market(self, df: pd.DataFrame = None):
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            df = self.data
            
        if df is None or df.empty or len(df) < 20:
            df = pd.DataFrame({
                'open': [1.0]*25, 'high': [1.1]*25, 
                'low': [0.9]*25, 'close': [1.05]*25, 'volume': [100]*25
            })
            
        df = self.calculate_indicators(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        close = latest['close']
        upper = latest['kc_upper']
        lower = latest['kc_lower']
        rsi = latest['RSI']
        prev_rsi = prev['RSI']
        ema9 = latest['EMA_9']
        ema21 = latest['EMA_21']

        action = "HOLD"
        score = 50
        reason = "Market consolidating / Waiting for Keltner Setup"

        if pd.isna(rsi):
            rsi = 50

        # Cristian AP Strategy Implementation (80-85% Win Rate Logic)
        if close <= lower and rsi > 50 and prev_rsi <= 50 and ema9 >= ema21:
            action = "BUY"
            score = 88
            reason = "Keltner Lower Band Touch + RSI 50 Bullish Crossover"[cite: 20]
        elif close >= upper and rsi < 50 and prev_rsi >= 50 and ema9 <= ema21:
            action = "SELL"
            score = 88
            reason = "Keltner Upper Band Touch + RSI 50 Bearish Crossover"[cite: 20]
        else:
            # High Probability Trend Continuation Backup
            if ema9 > ema21 and rsi > 52:
                action = "BUY"
                score = 76
                reason = f"1m Trend Momentum Buy (RSI: {int(rsi)})"
            elif ema9 < ema21 and rsi < 48:
                action = "SELL"
                score = 76
                reason = f"1m Trend Momentum Sell (RSI: {int(rsi)})"
            else:
                action = "HOLD"
                score = 50
                reason = "No Clean Setup / Avoiding False Breakout"

        score = max(50, min(score, 95))

        return {
            "action": action,
            "entry_price": float(close),
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
