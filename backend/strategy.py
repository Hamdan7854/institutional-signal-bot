import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union, List

class QuantitativeTradingStrategy:
    """
    Ultimate Hybrid Quantitative Trading Strategy Engine:
    Combines S&P Rectangle Support/Resistance Range-Bound Logic with 
    Hurst Exponent Regime Filter, KAMA, SMA Crossover, and Order Flow Delta.
    """

    @staticmethod
    def calculate_sma(price_history: np.ndarray, period: int) -> Optional[float]:
        """Original Baseline: Simple Moving Average Calculation"""
        if len(price_history) < period:
            return None
        return float(np.mean(price_history[-period:]))

    @staticmethod
    def calculate_hurst_exponent(price_series: np.ndarray, max_lag: int = 20) -> float:
        """1. Stochastic Regime Filter (Hurst Exponent)"""
        prices = np.asarray(price_series, dtype=float)
        prices = prices[np.isfinite(prices)]
        if len(prices) < max_lag * 2:
            return 0.5  
        
        lags = range(2, max_lag)
        tau = [np.std(np.subtract(prices[lag:], prices[:-lag])) for lag in lags]
        
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return float(poly[0])

    @staticmethod
    def calculate_kama(price_series: np.ndarray, period: int = 10, fast: int = 2, slow: int = 30) -> float:
        """3. Kaufman's Adaptive Moving Average (KAMA)"""
        prices = np.asarray(price_series, dtype=float)
        if len(prices) < period + 1:
            return float(prices[-1])

        change = abs(prices[-1] - prices[-period - 1])
        volatility = sum(abs(prices[i] - prices[i - 1]) for i in range(-period, 0))
        
        if volatility == 0:
            er = 0.0
        else:
            er = change / volatility 
            
        sc = (er * (2.0 / (fast + 1) - 2.0 / (slow + 1)) + 2.0 / (slow + 1)) ** 2
        kama = float(prices[-period - 1] + sc * (prices[-1] - prices[-period - 1]))
        return kama

    @classmethod
    def evaluate_signal(
        cls,
        price_history: Union[List, np.ndarray],
        volume_history: Optional[Union[List, np.ndarray]] = None,
        ask_bid_delta: Optional[float] = None,
        high_history: Optional[Union[List, np.ndarray]] = None,
        low_history: Optional[Union[List, np.ndarray]] = None,
        fast_period: int = 5,
        slow_period: int = 20,
        lookback_period: int = 20,
        buffer_percent: float = 0.0005,
        pair_name: str = "ASSET_PAIR"
    ) -> Tuple[str, str]:
        """
        Hybrid Engine: SMA Crossover + Hurst Regime + KAMA + S&R Rectangle Range-Bound Strategy.
        """
        min_required_len = max(50, slow_period + 2, lookback_period + 2)
        prices = np.array(price_history, dtype=float)
        prices = prices[np.isfinite(prices)]

        if len(prices) < min_required_len:
            return "HOLD", f"[{pair_name}] Insufficient market data history."

        current_price = prices[-1]
        prev_price = prices[-2]

        # Highs and Lows setup for Rectangle S&R
        highs = np.array(high_history, dtype=float) if high_history is not None else prices
        lows = np.array(low_history, dtype=float) if low_history is not None else prices

        # Rectangle Support & Resistance Levels (Lookback window)
        recent_highs = highs[-lookback_period:-1]
        recent_lows = lows[-lookback_period:-1]
        resistance_level = float(np.max(recent_highs))
        support_level = float(np.min(recent_lows))

        # --- 1. SMA Crossover Detection ---
        sma_fast = cls.calculate_sma(prices, fast_period)
        sma_slow = cls.calculate_sma(prices, slow_period)
        prev_fast = cls.calculate_sma(prices[:-1], fast_period)
        prev_slow = cls.calculate_sma(prices[:-1], slow_period)

        if not (sma_fast and sma_slow and prev_fast and prev_slow):
            return "HOLD", f"[{pair_name}] Calculating Moving Averages..."

        sma_bullish_cross = (prev_fast <= prev_slow) and (sma_fast > sma_slow)
        sma_bearish_cross = (prev_fast >= prev_slow) and (sma_fast < sma_slow)

        # --- 2. Advanced Quantitative Engine (Hurst & KAMA) ---
        hurst = cls.calculate_hurst_exponent(prices)
        kama_current = cls.calculate_kama(prices)
        ofi_delta = ask_bid_delta if ask_bid_delta is not None else 0.0

        # Proximity to Support/Resistance Zones (Rectangle Check)
        near_support = abs(current_price - support_level) <= (support_level * buffer_percent) or current_price <= support_level
        near_resistance = abs(current_price - resistance_level) <= (resistance_level * buffer_percent) or current_price >= resistance_level

        signal = "HOLD"
        reason = f"[{pair_name}] No valid setup found."

        # Random Walk / Heavy Noise Filter
        if 0.45 <= hurst <= 0.55:
            return "HOLD", f"[{pair_name}] Random Walk / Noise Detected (Hurst: {hurst:.2f}). Skipped."

        # Trending Regime (Hurst > 0.55) -> SMA Crossover & Trend Following
        if hurst > 0.55:
            if sma_bullish_cross or (current_price > kama_current and ofi_delta >= 0):
                signal = "CALL (BUY)"
                reason = f"[{pair_name}] Trend Bullish (Hurst: {hurst:.2f}, KAMA: {kama_current:.5f}) | Entry: {current_price:.5f}"
            elif sma_bearish_cross or (current_price < kama_current and ofi_delta <= 0):
                signal = "PUT (SELL)"
                reason = f"[{pair_name}] Trend Bearish (Hurst: {hurst:.2f}, KAMA: {kama_current:.5f}) | Entry: {current_price:.5f}"
            else:
                reason = f"[{pair_name}] Trending Market (Hurst: {hurst:.2f}), awaiting clean crossover."

        # Mean-Reverting / Ranging Regime (Hurst < 0.45) -> S&R Rectangle Range Strategy
        elif hurst < 0.45:
            if near_support and current_price >= prev_price:
                signal = "CALL (BUY)"
                reason = f"[{pair_name}] S&R Rectangle Support Bounce (Supp: {support_level:.5f}) | Hurst: {hurst:.2f}"
            elif near_resistance and current_price <= prev_price:
                signal = "PUT (SELL)"
                reason = f"[{pair_name}] S&R Rectangle Resistance Rejection (Res: {resistance_level:.5f}) | Hurst: {hurst:.2f}"
            elif current_price < kama_current and ofi_delta > 0:
                signal = "CALL (BUY)"
                reason = f"[{pair_name}] Mean Reversion Reversal | Hurst: {hurst:.2f} | Entry: {current_price:.5f}"
            elif current_price > kama_current and ofi_delta < 0:
                signal = "PUT (SELL)"
                reason = f"[{pair_name}] Mean Reversion Reversal | Hurst: {hurst:.2f} | Entry: {current_price:.5f}"
            else:
                reason = f"[{pair_name}] Ranging S&R Zone (Supp: {support_level:.5f}, Res: {resistance_level:.5f}), awaiting touch."

        return signal, reason
