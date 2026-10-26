import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union, List

class QuantitativeTradingStrategy:
    """
    Production-Grade Regime-Adaptive Quantitative Trading Strategy Engine 
    with Momentum, Volatility, and Multi-Timeframe Filters.
    """

    @staticmethod
    def calculate_sma(price_history: np.ndarray, period: int) -> Optional[float]:
        """Calculates Simple Moving Average over a specified historical period."""
        if len(price_history) < period:
            return None
        return float(np.mean(price_history[-period:]))

    @staticmethod
    def calculate_kama(price_series: np.ndarray, period: int = 10, fast: int = 2, slow: int = 30) -> np.ndarray:
        prices = np.asarray(price_series, dtype=float)
        n = len(prices)
        if n < period + 1:
            return prices

        fast_sc = 2.0 / (fast + 1.0)
        slow_sc = 2.0 / (slow + 1.0)

        change = np.abs(prices[period:] - prices[:-period])
        abs_diffs = np.abs(np.diff(prices))
        volatility = np.convolve(abs_diffs, np.ones(period), mode='valid')

        er = np.zeros_like(change)
        nonzero_idxs = volatility != 0
        er[nonzero_idxs] = change[nonzero_idxs] / volatility[nonzero_idxs]

        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

        kama = np.zeros(n)
        kama[period - 1] = np.mean(prices[:period])

        for i in range(period, n):
            kama[i] = kama[i - 1] + sc[i - period] * (prices[i] - kama[i - 1])

        kama[:period - 1] = prices[:period - 1]
        return kama

    @staticmethod
    def calculate_rsi(price_history: np.ndarray, period: int = 14) -> float:
        """Calculates Relative Strength Index (RSI) for Momentum Filtering."""
        if len(price_history) < period + 1:
            return 50.0  # Neutral default
        deltas = np.diff(price_history)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        if down == 0:
            return 100.0
        rs = up / down
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return float(rsi)

    @staticmethod
    def calculate_atr(high_history: np.ndarray, low_history: np.ndarray, close_history: np.ndarray, period: int = 14) -> float:
        """Calculates Average True Range (ATR) for strict Volatility Filtering."""
        if len(close_history) < period + 1:
            return 0.0
        tr1 = high_history[1:] - low_history[1:]
        tr2 = np.abs(high_history[1:] - close_history[:-1])
        tr3 = np.abs(low_history[1:] - close_history[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        if len(tr) < period:
            return float(np.mean(tr))
        return float(np.mean(tr[-period:]))

    @classmethod
    def evaluate_signal(
        cls,
        price_history: Union[List, np.ndarray],
        volume_history: Optional[Union[List, np.ndarray]] = None,
        ask_bid_delta_history: Optional[Union[List, np.ndarray]] = None,
        high_history: Optional[Union[List, np.ndarray]] = None,
        low_history: Optional[Union[List, np.ndarray]] = None,
        fast_period: int = 5,
        slow_period: int = 20,
        hurst_max_lag: int = 100,
        ofi_z_threshold: float = 1.0,
        atr_threshold_multiplier: float = 1.5 # Volatility Guard threshold barhane ke liye
    ) -> Tuple[str, str]:
        """
        Evaluates quantitative signals incorporating Multi-Timeframe, RSI Momentum, 
        Strict ATR Volatility Thresholds, and Candle Confirmation logic.
        """
        prices = np.array(price_history, dtype=float)
        prices = prices[np.isfinite(prices)]

        min_required_len = max(100, slow_period + 10)
        if len(prices) < min_required_len:
            return "HOLD", "Insufficient clean data history."

        current_price = prices[-1]
        prev_candle_close = prices[-2] # Confirmation check ke liye previous candle ka close

        # 1. Moving Average Calculations (Fast & Slow)
        sma_fast = cls.calculate_sma(prices, fast_period)
        sma_slow = cls.calculate_sma(prices, slow_period)
        
        # Multi-Timeframe / Macro Trend Filter (e.g., 50-period SMA as higher timeframe proxy)
        macro_sma = cls.calculate_sma(prices, 50)
        is_macro_bullish = current_price > macro_sma if macro_sma else True
        is_macro_bearish = current_price < macro_sma if macro_sma else True

        # 2. RSI Momentum Filter
        rsi_value = cls.calculate_rsi(prices, period=14)

        # 3. Volatility Guard (ATR Threshold)
        atr_val = 0.0
        if high_history is not None and low_history is not None:
            highs = np.array(high_history, dtype=float)
            lows = np.array(low_history, dtype=float)
            atr_val = cls.calculate_atr(highs, lows, prices, period=14)
        
        # Agar market ki volatility bohat low ho (choppy/dead market), to trade skip kardein
        if atr_val > 0 and atr_val < (np.mean(prices) * 0.0005 * atr_threshold_multiplier):
            return "HOLD", f"Low Volatility Guard Triggered (ATR: {atr_val:.5f})"

        # 4. Decision Engine with Filters Applied
        # BUY Logic: Macro Trend Bullish + RSI not Overbought (< 70) + Price closing above previous confirmation
        if sma_fast and sma_slow and sma_fast > sma_slow:
            if is_macro_bullish and rsi_value < 70 and current_price >= prev_candle_close:
                return "CALL (BUY)", f"Filtered Bullish Signal | RSI: {rsi_value:.2f} | Macro Trend Confirmed"

        # SELL Logic: Macro Trend Bearish + RSI not Oversold (> 30) + Price closing below previous confirmation
        elif sma_fast and sma_slow and sma_fast < sma_slow:
            if is_macro_bearish and rsi_value > 30 and current_price <= prev_candle_close:
                return "PUT (SELL)", f"Filtered Bearish Signal | RSI: {rsi_value:.2f} | Macro Trend Confirmed"

        return "HOLD", "No valid filtered condition met."
