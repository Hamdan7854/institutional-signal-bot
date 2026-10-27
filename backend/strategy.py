import numpy as np
import pandas as pd
from market_dayallta import MarketAnalyzer

class QuantitativeTradingStrategy:

@staticmethod
    def calculate_sma(price_history, period):
        """ Original Baseline: Simple Moving Average Calculation """
        if len(price_history) < period:
            return None
        return sum(price_history[-period:]) / period

@staticmethod
    def calculate_hurst_exponent(price_series, max_lag=20):
        """ 1. Stochastic Regime Filter (Hurst Exponent) H > 0.55 -> Trending Market H < 0.45 -> Mean-Reverting / Ranging Market 0.45 <= H <= 0.55 -> Random Walk / Noise """
        if len(price_series) < max_lag * 2:
            return 0.5  # Neutral / Noise
        
        lags = range(2, max_lag)
        tau = [np.std(np.subtract(price_series[lag:], price_series[:-lag])) for lag in lags]
        
        # Linear fit to calculate Hurst Exponent
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0]

@staticmethod
    def calculate_kama(price_series, period=10, fast=2, slow=30):
        """ 3. Kaufman's Adaptive Moving Average (KAMA) - Fixed Array Invalidation Bug """
        if len(price_series) < period + 1:
            return price_series[-1]

        change = abs(price_series[-1] - price_series[-period - 1])
        volatility = sum(abs(price_series[i] - price_series[i - 1]) for i in range(-period, 0))
        
        if volatility == 0:
            er = 0
        else:
            er = change / volatility # Efficiency Ratio
            
        sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
        
        # Precise Real-time KAMA Calculation
        kama = price_series[-period - 1] + sc * (price_series[-1] - price_series[-period - 1])
        return kama

@classmethod
    def evaluate_signal(cls, price_history, volume_history=None, ask_bid_delta=None, fast_period=5, slow_period=20):
        """ Hybrid Engine: Original SMA Crossover + Hurst Regime + KAMA + Order Flow Delta """
        min_required_len = max(50, slow_period + 2)
        if len(price_history) < min_required_len:
            return "HOLD", "Insufficient market data history."

        # Strictly enforce latest fresh price array
        prices = np.array(price_history, dtype=float)
        current_price = prices[-1]

        # --- 1. Original SMA Crossover Detection ---
        sma_fast = cls.calculate_sma(prices, fast_period)
        sma_slow = cls.calculate_sma(prices, slow_period)
        prev_fast = cls.calculate_sma(prices[:-1], fast_period)
        prev_slow = cls.calculate_sma(prices[:-1], slow_period)

        if not (sma_fast and sma_slow and prev_fast and prev_slow):
            return "HOLD", "Calculating Moving Averages..."

        sma_bullish_cross = (prev_fast <= prev_slow) and (sma_fast > sma_slow)
        sma_bearish_cross = (prev_fast >= prev_slow) and (sma_fast < sma_slow)

        # --- 2. Advanced Quantitative Engine (Hurst & KAMA) ---
        hurst = cls.calculate_hurst_exponent(prices)
        kama_current = cls.calculate_kama(prices)
        ofi_delta = ask_bid_delta if ask_bid_delta is not None else 0

        # --- 3. Decision Engine Logic ---
        signal = "HOLD"
        reason = "No valid crossover or institutional confirmation."

        # Random Walk / Heavy Noise Filter
        if 0.45 <= hurst <= 0.55:
            return "HOLD", f"Random Walk / Noise Detected (Hurst: {hurst:.2f}). Trade Skipped."

        # Trending Regime (Hurst > 0.55)
        if hurst > 0.55:
            if sma_bullish_cross or (current_price > kama_current and ofi_delta >= 0):
                signal = "CALL (BUY)"
                reason = f"Bullish Trend (Hurst: {hurst:.2f}, KAMA: {kama_current:.5f}) | Entry: {current_price:.5f}"
            elif sma_bearish_cross or (current_price < kama_current and ofi_delta <= 0):
                signal = "PUT (SELL)"
                reason = f"Bearish Trend (Hurst: {hurst:.2f}, KAMA: {kama_current:.5f}) | Entry: {current_price:.5f}"
            else:
                reason = f"Trending Market (Hurst: {hurst:.2f}), awaiting clean crossover."

        # Mean-Reverting / Ranging Regime (Hurst < 0.45)
        elif hurst < 0.45:
            if current_price < kama_current and ofi_delta > 0:
                signal = "CALL (BUY)"
                reason = f"Mean Reversion Reversal (Hurst: {hurst:.2f}) | Entry: {current_price:.5f}"
            elif current_price > kama_current and ofi_delta < 0:
                signal = "PUT (SELL)"
                reason = f"Mean Reversion Reversal (Hurst: {hurst:.2f}) | Entry: {current_price:.5f}"
            else:
                reason = f"Ranging Market (Hurst: {hurst:.2f}), awaiting exhaustion."

        return signal, reason
