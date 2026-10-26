import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union, List

class QuantitativeTradingStrategy:
    """
    Production-Grade Regime-Adaptive Quantitative Trading Strategy Engine 
    with Anti-Pullback Candle Filters, RSI Momentum, and ATR Filters.
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
        higher_tf_prices: Optional[Union[List, np.ndarray]] = None,
        volume_history: Optional[Union[List, np.ndarray]] = None,
        ask_bid_delta_history: Optional[Union[List, np.ndarray]] = None,
        high_history: Optional[Union[List, np.ndarray]] = None,
        low_history: Optional[Union[List, np.ndarray]] = None,
        fast_period: int = 5,
        slow_period: int = 20,
        hurst_max_lag: int = 100,
        ofi_z_threshold: float = 1.0,
        atr_threshold_multiplier: float = 1.5
    ) -> Tuple[str, str]:
        """
        Evaluates signals using Real Multi-Timeframe trend check, RSI Momentum, 
        ATR Volatility Guard, and Anti-Pullback Candle Filters.
        """
        prices = np.array(price_history, dtype=float)
        prices = prices[np.isfinite(prices)]

        min_required_len = max(100, slow_period + 10)
        if len(prices) < min_required_len:
            return "HOLD", "Insufficient clean data history."

        current_price = prices[-1]
        prev_close = prices[-2]
        prev_prev_close = prices[-3] if len(prices) >= 3 else prev_close

        # Candle color check (Green = Close up, Red = Close down)
        is_last_candle_green = current_price > prev_close
        is_prev_candle_green = prev_close > prev_prev_close

        is_last_candle_red = current_price < prev_close
        is_prev_candle_red = prev_close < prev_prev_close

        # 1. Moving Average Calculations (Fast & Slow)
        sma_fast = cls.calculate_sma(prices, fast_period)
        sma_slow = cls.calculate_sma(prices, slow_period)
        
        # 2. Real Multi-Timeframe Trend Confirmation Check
        is_macro_bullish = True
        is_macro_bearish = True

        if higher_tf_prices is not None and len(higher_tf_prices) >= 20:
            htf_prices = np.array(higher_tf_prices, dtype=float)
            htf_sma = cls.calculate_sma(htf_prices, 20)
            if htf_sma:
                current_htf_price = htf_prices[-1]
                is_macro_bullish = current_htf_price > htf_sma
                is_macro_bearish = current_htf_price < htf_sma
        else:
            macro_sma = cls.calculate_sma(prices, 50)
            if macro_sma:
                is_macro_bullish = current_price > macro_sma
                is_macro_bearish = current_price < macro_sma

        # 3. RSI Momentum Filter
        rsi_value = cls.calculate_rsi(prices, period=14)

        # 4. Volatility Guard (ATR Threshold)
        atr_val = 0.0
        if high_history is not None and low_history is not None:
            highs = np.array(high_history, dtype=float)
            lows = np.array(low_history, dtype=float)
            atr_val = cls.calculate_atr(highs, lows, prices, period=14)
        
        if atr_val > 0 and atr_val < (np.mean(prices) * 0.0005 * atr_threshold_multiplier):
            return "HOLD", f"Low Volatility Guard Triggered (ATR: {atr_val:.5f})"

        # 5. Decision Engine with Anti-Pullback Filters Enforced
        if sma_fast and sma_slow and sma_fast > sma_slow:
            # BUY Condition: Macro Bullish + RSI < 70 + Check for red pullback candles
            if is_macro_bullish and rsi_value < 70:
                if is_last_candle_green and is_prev_candle_green:
                    return "CALL (BUY)", f"Bullish Confirmed | No Red Pullback | RSI: {rsi_value:.2f}"
                else:
                    return "HOLD", "Pullback Detected (Red Candles): Skipping Buy Signal"

        elif sma_fast and sma_slow and sma_fast < sma_slow:
            # SELL Condition: Macro Bearish + RSI > 30 + Check for green pullback candles
            if is_macro_bearish and rsi_value > 30:
                if is_last_candle_red and is_prev_candle_red:
                    return "PUT (SELL)", f"Bearish Confirmed | No Green Pullback | RSI: {rsi_value:.2f}"
                else:
                    return "HOLD", "Pullback Detected (Green Candles): Skipping Sell Signal"

        return "HOLD", "No valid multi-filtered condition met."
