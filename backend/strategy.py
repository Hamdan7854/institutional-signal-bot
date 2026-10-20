import pandas as pd
import numpy as np
import config

class HighProbabilityStrategy:
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Ensure column name compatibility (lowercase close)
        close_col = 'close' if 'close' in df.columns else 'Close'
        close = df[close_col]

        # Exponential Moving Averages
        df['ema_fast'] = close.ewm(span=config.EMA_FAST, adjust=False).mean()
        df['ema_slow'] = close.ewm(span=config.EMA_SLOW, adjust=False).mean()
        df['ema_trend'] = close.ewm(span=config.EMA_TREND, adjust=False).mean()

        # Relative Strength Index
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=config.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=config.RSI_PERIOD).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # Bollinger Bands
        df['bb_mid'] = close.rolling(window=config.BB_PERIOD).mean()
        std = close.rolling(window=config.BB_PERIOD).std()
        df['bb_upper'] = df['bb_mid'] + (config.BB_STD_DEV * std)
        df['bb_lower'] = df['bb_mid'] - (config.BB_STD_DEV * std)

        return df

    def generate_signal(self, df: pd.DataFrame) -> dict:
        df = self.calculate_indicators(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        signal = "NEUTRAL"
        confidence = 0
        reasons = []

        close_col = 'close' if 'close' in df.columns else 'Close'
        close_price = latest[close_col]
        ema_trend = latest['ema_trend']
        rsi = latest['rsi']
        macd_hist = latest['macd_hist']
        bb_upper = latest['bb_upper']
        bb_lower = latest['bb_lower']

        # Bullish Evaluation
        is_uptrend = close_price > ema_trend
        ema_cross_up = (prev['ema_fast'] <= prev['ema_slow']) and (latest['ema_fast'] > latest['ema_slow'])
        rsi_bullish = config.RSI_BUY_MIN <= rsi <= config.RSI_BUY_MAX
        macd_bullish = macd_hist > 0
        not_overbought_bb = close_price < (bb_upper - 0.00005)

        # Bearish Evaluation
        is_downtrend = close_price < ema_trend
        ema_cross_down = (prev['ema_fast'] >= prev['ema_slow']) and (latest['ema_fast'] < latest['ema_slow'])
        rsi_bearish = config.RSI_SELL_MIN <= rsi <= config.RSI_SELL_MAX
        macd_bearish = macd_hist < 0
        not_oversold_bb = close_price > (bb_lower + 0.00005)

        if is_uptrend and ema_cross_up and rsi_bullish and macd_bullish:
            signal = "CALL"
            confidence = 91
            reasons = [
                "Macro Uptrend (Price > EMA 50)",
                "Bullish EMA 9/21 Crossover",
                f"RSI Bullish Zone (RSI: {rsi:.1f})",
                "MACD Acceleration Positive",
                "Price Positioned Inside Bollinger Bands"
            ]
        elif is_downtrend and ema_cross_down and rsi_bearish and macd_bearish:
            signal = "PUT"
            confidence = 91
            reasons = [
                "Macro Downtrend (Price < EMA 50)",
                "Bearish EMA 9/21 Crossover",
                f"RSI Bearish Zone (RSI: {rsi:.1f})",
                "MACD Acceleration Negative",
                "Price Positioned Inside Bollinger Bands"
            ]

        return {
            "signal": signal,
            "confidence": confidence,
            "price": close_price,
            "rsi": rsi,
            "reasons": reasons
        }
