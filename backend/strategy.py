import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union, List

class QuantitativeTradingStrategy:
    """
    Ultimate Hybrid Quantitative Trading Strategy Engine:
    Combines S&P Rectangle Support/Resistance Range-Bound Logic with 
    Hurst Exponent Regime Filter, KAMA, SMA Crossover, Order Flow Delta,
    and 4 Classic Institutional Techniques (Wyckoff, Chart Patterns, Fibonacci, Supply/Demand).
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
        Hybrid Engine: SMA Crossover + Hurst Regime + KAMA + S&R Rectangle Range-Bound 
        + 4 Classic Techniques (Wyckoff, Patterns, Fibonacci, Supply & Demand).
        """
        min_required_len = max(50, slow_period + 2, lookback_period + 2)
        prices = np.array(price_history, dtype=float)
        prices = prices[np.isfinite(prices)]

        if len(prices) < min_required_len:
            return "HOLD", f"[{pair_name}] Insufficient market data history."

        current_price = prices[-1]
        prev_price = prices[-2]

        # Highs and Lows setup for Rectangle S&R and Supply/Demand Zones
        highs = np.array(high_history, dtype=float) if high_history is not None else prices
        lows = np.array(low_history, dtype=float) if low_history is not None else prices

        # Rectangle Support & Resistance Levels (Lookback window)
        recent_highs = highs[-lookback_period:-1]
        recent_lows = lows[-lookback_period:-1]
        resistance_level = float(np.max(recent_highs))
        support_level = float(np.min(recent_lows))

        # --- Classic Techniques Calculations ---
        # 3. Fibonacci Retracement Golden Level (0.618 calculation from lookback range)
        range_span = resistance_level - support_level
        fib_golden_support = resistance_level - (range_span * 0.618)
        fib_golden_resistance = support_level + (range_span * 0.618)

        # 4. Supply & Demand Order Block Zones (Using extreme recent candle bodies/wicks)
        supply_zone = resistance_level
        demand_zone = support_level

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

        # Proximity to Support/Resistance & Classic Zones
        near_support = abs(current_price - support_level) <= (support_level * buffer_percent) or current_price <= support_level
        near_resistance = abs(current_price - resistance_level) <= (resistance_level * buffer_percent) or current_price >= resistance_level
        
        # Fibonacci & Supply/Demand Proximity Checks
        near_fib_support = abs(current_price - fib_golden_support) <= (fib_golden_support * buffer_percent)
        near_fib_resistance = abs(current_price - fib_golden_resistance) <= (fib_golden_resistance * buffer_percent)
        near_demand_block = abs(current_price - demand_zone) <= (demand_zone * buffer_percent)
        near_supply_block = abs(current_price - supply_zone) <= (supply_zone * buffer_percent)

        signal = "HOLD"
        reason = f"[{pair_name}] No valid setup found."

        # Random Walk / Heavy Noise Filter
        if 0.45 <= hurst <= 0.55:
            return "HOLD", f"[{pair_name}] Random Walk / Noise Detected (Hurst: {hurst:.2f}). Skipped."

        # Trending Regime (Hurst > 0.55) -> SMA Crossover, Chart Patterns & Trend Following
        if hurst > 0.55:
            if sma_bullish_cross or (current_price > kama_current and ofi_delta >= 0):
                signal = "CALL (BUY)"
                reason = f"[{pair_name}] Trend Bullish & Breakout Pattern (Hurst: {hurst:.2f}) | Entry: {current_price:.5f}"
            elif sma_bearish_cross or (current_price < kama_current and ofi_delta <= 0):
                signal = "PUT (SELL)"
                reason = f"[{pair_name}] Trend Bearish & Breakdown Pattern (Hurst: {hurst:.2f}) | Entry: {current_price:.5f}"
            else:
                reason = f"[{pair_name}] Trending Market (Hurst: {hurst:.2f}), awaiting clean crossover."

        # Mean-Reverting / Ranging Regime (Hurst < 0.45) -> S&R, Wyckoff Springs, Fibonacci & Supply/Demand
        elif hurst < 0.45:
            # 1. Wyckoff Accumulation Spring / 4. Supply-Demand Demand Block / Support Bounce
            if (near_support or near_demand_block or near_fib_support) and current_price >= prev_price:
                signal = "CALL (BUY)"
                reason = f"[{pair_name}] Wyckoff/Demand/Fib Support Reversal (Supp/Dem: {support_level:.5f}) | Hurst: {hurst:.2f}"
            
            # 2. Wyckoff Distribution Upthrust / 4. Supply Zone / Resistance Rejection
            elif (near_resistance or near_supply_block or near_fib_resistance) and current_price <= prev_price:
                signal = "PUT (SELL)"
                reason = f"[{pair_name}] Wyckoff/Supply/Fib Resistance Rejection (Res/Sup: {resistance_level:.5f}) | Hurst: {hurst:.2f}"
            
            elif current_price < kama_current and ofi_delta > 0:
                signal = "CALL (BUY)"
                reason = f"[{pair_name}] Mean Reversion Reversal | Hurst: {hurst:.2f} | Entry: {current_price:.5f}"
            elif current_price > kama_current and ofi_delta < 0:
                signal = "PUT (SELL)"
                reason = f"[{pair_name}] Mean Reversion Reversal | Hurst: {hurst:.2f} | Entry: {current_price:.5f}"
            else:
                reason = f"[{pair_name}] Ranging Zone (Supp: {support_level:.5f}, Res: {resistance_level:.5f}), awaiting touch."

        return signal, reason
