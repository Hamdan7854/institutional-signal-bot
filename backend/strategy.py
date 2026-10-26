import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union, List

class QuantitativeTradingStrategy:
    """
    Hybrid Quantitative Trading Strategy Engine:
    Combines Support & Resistance Rectangle Levels with Multi-Timeframe, 
    RSI Momentum, ATR Volatility Guard, and Anti-Pullback Candle Filters.
    """

    @staticmethod
    def calculate_sma(price_history: np.ndarray, period: int) -> Optional[float]:
        """Calculates Simple Moving Average over a specified historical period."""
        if len(price_history) < period:
            return None
        return float(np.mean(price_history[-period:]))

    @staticmethod
    def calculate_rsi(price_history: np.ndarray, period: int = 14) -> float:
        """Calculates Relative Strength Index (RSI) for Momentum Filtering."""
        if len(price_history) < period + 1:
            return 50.0
        deltas = np.diff(price_history)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        if down == 0:
            return 100.0
        rs = up / down
        return float(100.0 - (100.0 / (1.0 + rs)))

    @staticmethod
    def calculate_atr(high_history: np.ndarray, low_history: np.ndarray, close_history: np.ndarray, period: int = 14) -> float:
        """Calculates Average True Range (ATR) for volatility filtering."""
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
        lookback_period: int = 20,
        buffer_percent: float = 0.0005,
        atr_threshold_multiplier: float = 1.5
    ) -> Tuple[str, str]:
        """
        Evaluates signals combining S&R Rectangle ranges with trend, momentum, 
        and anti-pullback filters.
        """
        prices = np.array(price_history, dtype=float)
        prices = prices[np.isfinite(prices)]

        min_required_len = max(100, slow_period + 10, lookback_period + 10)
        if len(prices) < min_required_len:
            return "HOLD", "Insufficient clean data history."

        current_price = prices[-1]
        prev_price = prices[-2]
        prev_prev_close = prices[-3] if len(prices) >= 3 else prev_price

        # Highs and Lows arrays setup
        highs = np.array(high_history, dtype=float) if high_history is not None else prices
        lows = np.array(low_history, dtype=float) if low_history is not None else prices

        # 1. Support & Resistance Rectangle Levels Calculation
        recent_highs = highs[-lookback_period:-1]
        recent_lows = lows[-lookback_period:-1]
        resistance_level = float(np.max(recent_highs))
        support_level = float(np.min(recent_lows))

        # 2. Moving Averages & Trend Filtering
        sma_fast = cls.calculate_sma(prices, fast_period)
        sma_slow = cls.calculate_sma(prices, slow_period)

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

        # 3. RSI & ATR Volatility Guards
        rsi_value = cls.calculate_rsi(prices, period=14)
        atr_val = cls.calculate_atr(highs, lows, prices, period=14)

        if atr_val > 0 and atr_val < (np.mean(prices) * 0.0005 * atr_threshold_multiplier):
            return "HOLD", f"Low Volatility Guard Triggered (ATR: {atr_val:.5f})"

        # 4. Anti-Pullback Candle Check
        is_last_candle_green = current_price > prev_price
        is_last_candle_red = current_price < prev_price

        # 5. Zone Proximity Check (S&R Touch)
        near_support = abs(current_price - support_level) <= (support_level * buffer_percent) or current_price <= support_level
        near_resistance = abs(current_price - resistance_level) <= (resistance_level * buffer_percent) or current_price >= resistance_level

        # 6. Hybrid Decision Logic
        # BUY / CALL Signal: Near Support Rectangle OR Bullish Trend without red pullbacks
        if near_support or (sma_fast and sma_slow and sma_fast > sma_slow):
            if is_macro_bullish and rsi_value < 70 and is_last_candle_green:
                return "CALL (BUY)", f"Hybrid Bullish | S&R Support Bounce | RSI: {rsi_value:.2f}"

        # SELL / PUT Signal: Near Resistance Rectangle OR Bearish Trend without green pullbacks
        if near_resistance or (sma_fast and sma_slow and sma_fast < sma_slow):
            if is_macro_bearish and rsi_value > 30 and is_last_candle_red:
                return "PUT (SELL)", f"Hybrid Bearish | S&R Resistance Rejection | RSI: {rsi_value:.2f}"

        return "HOLD", f"Inside S&R Range (Supp: {support_level:.5f}, Res: {resistance_level:.5f})"
