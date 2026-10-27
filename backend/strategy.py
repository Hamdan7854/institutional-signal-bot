import numpy as np
import pandas as pd

class QuantitativeTradingStrategy:
    
    @staticmethod
    def calculate_sma(price_history, period):
        if len(price_history) < period:
            return None
        return float(sum(price_history[-period:]) / period)

    @staticmethod
    def calculate_hurst_exponent(price_series, max_lag=20):
        prices = np.asarray(price_series, dtype=float)
        prices = prices[np.isfinite(prices)]
        if len(prices) < max_lag * 2:
            return 0.5
        lags = range(2, max_lag)
        tau = [np.std(np.subtract(prices[lag:], prices[:-lag])) for lag in lags]
        try:
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return float(poly[0])
        except Exception:
            return 0.5

    @staticmethod
    def calculate_kama(price_series, period=10, fast=2, slow=30):
        prices = np.asarray(price_series, dtype=float)
        if len(prices) < period + 1:
            return float(prices[-1])
        change = abs(prices[-1] - prices[-period - 1])
        volatility = sum(abs(prices[i] - prices[i - 1]) for i in range(-period, 0))
        if volatility == 0:
            er = 0
        else:
            er = change / volatility
        sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
        kama = prices[-period - 1] + sc * (prices[-1] - prices[-period - 1])
        return float(kama)

    @classmethod
    def evaluate_signal(cls, price_history=None, volume_history=None, ask_bid_delta=None, pair_name=None, df=None, **kwargs):
        if price_history is None and df is not None and isinstance(df, pd.DataFrame) and "close" in df.columns:
            price_history = df["close"].values

        if price_history is None or len(price_history) == 0:
            return "HOLD", "No price history provided."

        min_required_len = max(50, 30 + 2)
        if len(price_history) < min_required_len:
            return "HOLD", "Insufficient market data history."

        prices = np.array(price_history, dtype=float)
        current_price = prices[-1]

        sma_fast = cls.calculate_sma(prices, 5)
        sma_slow = cls.calculate_sma(prices, 30)
        prev_fast = cls.calculate_sma(prices[:-1], 5)
        prev_slow = cls.calculate_sma(prices[:-1], 30)

        if not (sma_fast and sma_slow and prev_fast and prev_slow):
            return "HOLD", "Calculating Moving Averages..."

        sma_bullish_cross = (prev_fast < prev_slow) and (sma_fast > sma_slow)
        sma_bearish_cross = (prev_fast > prev_slow) and (sma_fast < sma_slow)

        hurst = cls.calculate_hurst_exponent(prices)
        kama_current = cls.calculate_kama(prices)

        signal = "HOLD"
        reason = "No valid crossover or institutional confirmation."

        if 0.45 <= hurst <= 0.55:
            return "HOLD", f"Random Walk / Noise Detected (Hurst: {hurst:.2f})"

        if hurst > 0.55:
            if sma_bullish_cross or (current_price > kama_current and sma_fast > sma_slow):
                signal = "CALL (BUY)"
                reason = f"Bullish Trend (Hurst: {hurst:.2f}), KAMA: {kama_current:.4f}"
            elif sma_bearish_cross or (current_price < kama_current and sma_fast < sma_slow):
                signal = "PUT (SELL)"
                reason = f"Bearish Trend (Hurst: {hurst:.2f}), KAMA: {kama_current:.4f}"
            else:
                reason = f"Trending Market (Hurst: {hurst:.2f}), awaiting setup"
        elif hurst < 0.45:
            if current_price < kama_current:
                signal = "CALL (BUY)"
                reason = f"Mean Reversion Reversal (Hurst: {hurst:.2f})"
            elif current_price > kama_current:
                signal = "PUT (SELL)"
                reason = f"Mean Reversion Reversal (Hurst: {hurst:.2f})"
            else:
                reason = f"Ranging Market (Hurst: {hurst:.2f}), awaiting setup"

        return signal, reason
