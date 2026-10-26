import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union, List

class QuantitativeTradingStrategy:
    """
    Ultimate Hybrid Quantitative Trading Strategy Engine:
    Integrates Hurst Exponent Regime Filter, KAMA, Support & Resistance Rectangles, 
    RSI Momentum, ATR Volatility Guard, and Anti-Pullback Filters.
    """

    @staticmethod
    def calculate_sma(price_history: np.ndarray, period: int) -> Optional[float]:
        """Calculates Simple Moving Average over a specified historical period."""
        if len(price_history) < period:
            return None
        return float(np.mean(price_history[-period:]))

    @staticmethod
    def calculate_kama(price_series: np.ndarray, period: int = 10, fast: int = 2, slow: int = 30) -> np.ndarray:
        """Calculates Kaufman's Adaptive Moving Average (KAMA)."""
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
    def calculate_hurst_exponent(price_series: np.ndarray, max_lag: int = 100) -> float:
        """Calculates Hurst Exponent using Rescaled Range (R/S) Analysis."""
        try:
            prices = np.asarray(price_series, dtype=float)
            prices = prices[np.isfinite(prices)]
            if len(prices) < max_lag:
                max_lag = max(10, len(prices) // 4)
            if max_lag <= 5 or len(prices) < 20:
                return 0.5
            
            log_returns = np.diff(np.log(prices))
            if len(log_returns) < max_lag:
                return 0.5
            
            lags = np.arange(2, max_lag)
            rs_values = []
            
            for lag in lags:
                n_chunks = len(log_returns) // lag
                if n_chunks == 0:
                    continue
                sub_chunks = log_returns[:n_chunks * lag].reshape(n_chunks, lag)
                chunk_means = np.mean(sub_chunks, axis=1, keepdims=True)
                cum_dev = np.cumsum(sub_chunks - chunk_means, axis=1)
                r_range = np.max(cum_dev, axis=1) - np.min(cum_dev, axis=1)
                t_std = np.std(sub_chunks, axis=1, ddof=1)
                
                valid = t_std > 1e-12
                if not np.any(valid):
                    continue
                rs_val = np.mean(r_range[valid] / t_std[valid])
                if rs_val > 0 and np.isfinite(rs_val):
                    rs_values.append((lag, rs_val))
                    
            if len(rs_values) < 3:
                return 0.5
                
            lags_fitted, rs_fitted = zip(*rs_values)
            poly = np.polyfit(np.log(lags_fitted), np.log(rs_fitted), 1)
            return float(np.clip(poly[0], 0.0, 1.0))
        except Exception:
            return 0.5

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
        Evaluates signals combining Hurst Exponent, S&R Rectangle zones, KAMA, 
        RSI momentum, and anti-pullback filters.
        """
        prices = np.array(price_history, dtype=float)
        prices = prices[np.isfinite(prices)]

        min_required_len = max(100, slow_period + 10, lookback_period + 10)
        if len(prices) < min_required_len:
            return "HOLD", "Insufficient clean data history."

        current_price = prices[-1]
        prev_price = prices[-2]

        # Highs and Lows arrays setup
        highs = np.array(high_history, dtype=float) if high_history is not None else prices
        lows = np.array(low_history, dtype=float) if low_history is not None else prices

        # 1. Support & Resistance Rectangle Levels Calculation
        recent_highs = highs[-lookback_period:-1]
        recent_lows = lows[-lookback_period:-1]
        resistance_level = float(np.max(recent_highs))
        support_level = float(np.min(recent_lows))

        # 2. Hurst Exponent Regime Filter Calculation
        hurst = cls.calculate_hurst_exponent(prices, max_lag=100)

        # 3. Moving Averages & KAMA Calculation
        sma_fast = cls.calculate_sma(prices, fast_period)
        sma_slow = cls.calculate_sma(prices, slow_period)
        kama_array = cls.calculate_kama(prices, period=10)
        kama_current = kama_array[-1] if len(kama_array) > 0 else current_price

        # 4. RSI & ATR Volatility Guards
        rsi_value = cls.calculate_rsi(prices, period=14)
        atr_val = cls.calculate_atr(highs, lows, prices, period=14)

        if atr_val > 0 and atr_val < (np.mean(prices) * 0.0005 * atr_threshold_multiplier):
            return "HOLD", f"Low Volatility Guard Triggered (ATR: {atr_val:.5f})"

        # 5. Anti-Pullback Candle Check
        is_last_candle_green = current_price > prev_price
        is_last_candle_red = current_price < prev_price

        # 6. Zone Proximity Check (S&R Touch)
        near_support = abs(current_price - support_level) <= (support_level * buffer_percent) or current_price <= support_level
        near_resistance = abs(current_price - resistance_level) <= (resistance_level * buffer_percent) or current_price >= resistance_level

        # 7. Hybrid Decision Logic incorporating Hurst Regime Filter
        # Agar Hurst se noisy/random market detect ho toh trade avoid karein
        if 0.45 <= hurst <= 0.55:
            return "HOLD", f"Random Walk / Noise Regime Detected (Hurst: {hurst:.2f})"

        # BUY / CALL Signal: S&R Support Bounce OR Trending Bullish Regime
        if near_support or (hurst > 0.55 and current_price > kama_current):
            if rsi_value < 70 and is_last_candle_green:
                return "CALL (BUY)", f"Hybrid Bullish | Hurst: {hurst:.2f} | Support Bounce | RSI: {rsi_value:.2f}"

        # SELL / PUT Signal: S&R Resistance Rejection OR Trending Bearish Regime
        if near_resistance or (hurst > 0.55 and current_price < kama_current):
            if rsi_value > 30 and is_last_candle_red:
                return "PUT (SELL)", f"Hybrid Bearish | Hurst: {hurst:.2f} | Resistance Rejection | RSI: {rsi_value:.2f}"

        return "HOLD", f"Inside S&R Range (Hurst: {hurst:.2f}, Supp: {support_level:.5f}, Res: {resistance_level:.5f})"
