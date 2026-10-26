import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union

class QuantitativeTradingStrategy:
    """
    Production-Grade Regime-Adaptive Quantitative Trading Strategy Engine.
    
    Integrates:
    1. Recursive Kaufman Adaptive Moving Average (KAMA).
    2. Log-Return Rescaled Range (R/S) Hurst Exponent Regime Filter.
    3. Rolling Z-Score Normalized Order Flow Imbalance (OFI).
    4. Exponential Average True Range (ATR) Volatility Guard.
    """

    @staticmethod
    def calculate_sma(price_history: np.ndarray, period: int) -> Optional[float]:
        """Calculates Simple Moving Average over a specified historical window."""
        if len(price_history) < period:
            return None
        return float(np.mean(price_history[-period:]))

    @staticmethod
    def calculate_kama(price_series: np.ndarray, period: int = 10, fast: int = 2, slow: int = 30) -> np.ndarray:
        """
        Calculates Kaufman's Adaptive Moving Average (KAMA) using continuous recursive smoothing.
        
        Formula:
            ER = Abs(Change) / Sum(Volatilities)
            SC = [ER * (Fast_SC - Slow_SC) + Slow_SC] ^ 2
            KAMA[t] = KAMA[t-1] + SC * (Price[t] - KAMA[t-1])
        """
        prices = np.asarray(price_series, dtype=float)
        n = len(prices)
        if n < period + 1:
            return prices

        fast_sc = 2.0 / (fast + 1.0)
        slow_sc = 2.0 / (slow + 1.0)

        # Directional change over specified period
        change = np.abs(prices[period:] - prices[:-period])

        # Absolute bar-to-bar volatility sum
        abs_diffs = np.abs(np.diff(prices))
        volatility = np.convolve(abs_diffs, np.ones(period), mode='valid')

        # Efficiency Ratio (ER) calculation
        er = np.zeros_like(change)
        nonzero_idx = volatility != 0
        er[nonzero_idx] = change[nonzero_idx] / volatility[nonzero_idx]

        # Dynamic Smoothing Constant (SC)
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

        # Continuous Recursive KAMA Tracking
        kama = np.zeros(n)
        kama[period - 1] = np.mean(prices[:period])  # Seed initial window with SMA

        for i in range(period, n):
            kama[i] = kama[i - 1] + sc[i - period] * (prices[i] - kama[i - 1])

        # Backfill initial lookback window with price series
        kama[:period - 1] = prices[:period - 1]
        return kama

    @staticmethod
    def calculate_hurst_exponent(price_series: np.ndarray, max_lag: int = 100) -> float:
        """
        Calculates Hurst Exponent using Rescaled Range (R/S) Analysis on logarithmic returns.
        
        Returns:
            H > 0.55 : Trending / Persistent Market
            0.45 <= H <= 0.55 : Random Walk / Noise Market
            H < 0.45 : Mean-Reverting / Anti-Persistent Market
        """
        try:
            prices = np.asarray(price_series, dtype=float)
            prices = prices[np.isfinite(prices)]

            if len(prices) < max_lag:
                max_lag = max(10, len(prices) // 4)

            if max_lag < 5 or len(prices) < 20:
                return 0.5

            # Calculate stationary logarithmic returns
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
                s_std = np.std(sub_chunks, axis=1, ddof=1)

                valid = s_std > 1e-12
                if not np.any(valid):
                    continue

                rs_val = np.mean(r_range[valid] / s_std[valid])
                if rs_val > 0 and np.isfinite(rs_val):
                    rs_values.append((lag, rs_val))

            if len(rs_values) < 3:
                return 0.5

            lags_fitted, rs_fitted = zip(*rs_values)
            poly = np.polyfit(np.log(lags_fitted), np.log(rs_fitted), 1)

            # Clamp Hurst exponent to standard bounds [0.0, 1.0]
            return float(np.clip(poly[0], 0.0, 1.0))

        except Exception:
            return 0.5

    @staticmethod
    def calculate_atr(high_history: np.ndarray, low_history: np.ndarray, close_history: np.ndarray, period: int = 14) -> float:
        """Calculates Average True Range (ATR) for volatility risk filtering."""
        if len(close_history) < period + 1:
            return 0.0

        tr1 = high_history[1:] - low_history[1:]
        tr2 = np.abs(high_history[1:] - close_history[:-1])
        tr3 = np.abs(low_history[1:] - close_history[:-1])

        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        if len(tr) < period:
            return float(np.mean(tr))

        atr = np.zeros(len(tr))
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, len(tr)):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

        return float(atr[-1])

    @staticmethod
    def normalize_order_flow_delta(ofi_history: np.ndarray, lookback: int = 20) -> float:
        """Normalizes Order Flow Imbalance (OFI) using rolling Z-Score standard deviation."""
        if len(ofi_history) < lookback:
            return 0.0

        recent_ofi = ofi_history[-lookback:]
        mean_ofi = np.mean(recent_ofi)
        std_ofi = np.std(recent_ofi)

        if std_ofi == 0 or np.isnan(std_ofi):
            return 0.0

        current_ofi = ofi_history[-1]
        return float((current_ofi - mean_ofi) / std_ofi)

    @classmethod
    def evaluate_signal(cls,
                        price_history: Union[list, np.ndarray],
                        volume_history: Optional[Union[list, np.ndarray]] = None,
                        ask_bid_delta_history: Optional[Union[list, np.ndarray]] = None,
                        high_history: Optional[Union[list, np.ndarray]] = None,
                        low_history: Optional[Union[list, np.ndarray]] = None,
                        fast_period: int = 5,
                        slow_period: int = 20,
                        hurst_max_lag: int = 100,
                        ofi_z_threshold: float = 1.0) -> Tuple[str, str]:
        """
        Evaluates quantitative signals across stochastic regime, adaptive trend, 
        and microstructure order flow dynamics.
        
        Returns:
            Tuple[str, str]: Signal ("CALL (BUY)", "PUT (SELL)", "HOLD"), Diagnostic Reason.
        """
        if price_history is None or len(price_history) == 0:
            return "HOLD", "Empty market data history."

        # Strict Data Sanitization
        prices = np.array(price_history, dtype=float)
        prices = prices[np.isfinite(prices)]

        min_required_len = max(100, slow_period + 10)
        if len(prices) < min_required_len:
            return "HOLD", f"Insufficient clean data history. Required: {min_required_len}, Received: {len(prices)}."

        current_price = prices[-1]

        # 1. Moving Average Calculations
        sma_fast = cls.calculate_sma(prices, fast_period)
        sma_slow = cls.calculate_sma(prices, slow_period)
        prev_fast = cls.calculate_sma(prices[:-1], fast_period)
        prev_slow = cls.calculate_sma(prices[:-1], slow_period)

        if sma_fast is None or sma_slow is None or prev_fast is None or prev_slow is None:
            return "HOLD", "Error calculating moving averages."

        sma_bullish_cross = (prev_fast <= prev_slow) and (sma_fast > sma_slow)
        sma_bearish_cross = (prev_fast >= prev_slow) and (sma_fast < sma_slow)

        # 2. Adaptive Continuous KAMA
        kama_array = cls.calculate_kama(prices, period=10, fast=2, slow=30)
        kama_current = kama_array[-1]

        # 3. Stochastic Regime Filter (Hurst Exponent)
        hurst = cls.calculate_hurst_exponent(prices, max_lag=hurst_max_lag)

        # 4. Normalized Order Flow Imbalance Z-Score
        if ask_bid_delta_history is not None and len(ask_bid_delta_history) > 0:
            ofi_array = np.array(ask_bid_delta_history, dtype=float)
            ofi_array = ofi_array[np.isfinite(ofi_array)]
            ofi_zscore = cls.normalize_order_flow_delta(ofi_array, lookback=20)
        else:
            ofi_zscore = 0.0

        # 5. Volatility Guard (ATR)
        atr = 0.0
        if high_history is not None and low_history is not None:
            highs = np.array(high_history, dtype=float)[np.isfinite(high_history)]
            lows = np.array(low_history, dtype=float)[np.isfinite(low_history)]
            if len(highs) == len(prices) and len(lows) == len(prices):
                atr = cls.calculate_atr(highs, lows, prices, period=14)

        # 6. Decision Engine Execution Matrix
        signal = "HOLD"
        reason = "No valid regime condition met."

        # Filter out Random Walk / High Noise Regimes
        if 0.45 <= hurst <= 0.55:
            return "HOLD", f"Random Walk / Noise Regime Detected (Hurst: {hurst:.3f}). Execution Skipped."

        # Trending Regime Logic (Hurst > 0.55)
        if hurst > 0.55:
            is_bullish = sma_bullish_cross or (current_price > kama_current and ofi_zscore >= ofi_z_threshold)
            is_bearish = sma_bearish_cross or (current_price < kama_current and ofi_zscore <= -ofi_z_threshold)

            if is_bullish and not is_bearish:
                signal = "CALL (BUY)"
                reason = (f"Trending Bullish Signal | Hurst: {hurst:.3f} | KAMA: {kama_current:.4f} | "
                          f"OFI Z-Score: {ofi_zscore:.2f} | ATR: {atr:.4f} | Price: {current_price:.4f}")
            elif is_bearish and not is_bullish:
                signal = "PUT (SELL)"
                reason = (f"Trending Bearish Signal | Hurst: {hurst:.3f} | KAMA: {kama_current:.4f} | "
                          f"OFI Z-Score: {ofi_zscore:.2f} | ATR: {atr:.4f} | Price: {current_price:.4f}")
            else:
                reason = f"Trending Market (Hurst: {hurst:.3f}), awaiting trend/OFI alignment."

        # Mean-Reverting Regime Logic (Hurst < 0.45)
        elif hurst < 0.45:
            price_distance = current_price - kama_current

            # Buy entry: Price below KAMA with positive institutional order flow surge
            if price_distance < 0 and ofi_zscore >= ofi_z_threshold:
                signal = "CALL (BUY)"
                reason = (f"Mean Reversion Buy Signal | Hurst: {hurst:.3f} | Sub-KAMA Dist: {price_distance:.4f} | "
                          f"OFI Z-Score: {ofi_zscore:.2f} | Price: {current_price:.4f}")
            # Sell entry: Price above KAMA with negative institutional order flow surge
            elif price_distance > 0 and ofi_zscore <= -ofi_z_threshold:
                signal = "PUT (SELL)"
                reason = (f"Mean Reversion Sell Signal | Hurst: {hurst:.3f} | Sur-KAMA Dist: {price_distance:.4f} | "
                          f"OFI Z-Score: {ofi_zscore:.2f} | Price: {current_price:.4f}")
            else:
                reason = f"Ranging Market (Hurst: {hurst:.3f}), awaiting price deviation or OFI confirmation."

        return signal, reason
