import numpy as np
import pandas as pd
from datetime import datetime

class QuantitativeTradingStrategy:

    @staticmethod
    def calculate_sma(price_history, period):
        """Simple Moving Average Calculation"""
        if len(price_history) < period:
            return None
        return sum(price_history[-period:]) / period

    @staticmethod
    def calculate_atr(high_prices, low_prices, close_prices, period=14):
        """Average True Range (ATR) Volatility Filter"""
        if len(close_prices) < period + 1:
            return 0.0
        
        tr_list = []
        for i in range(1, len(close_prices)):
            h = high_prices[i]
            l = low_prices[i]
            cp = close_prices[i-1]
            tr = max(h - l, abs(h - cp), abs(l - cp))
            tr_list.append(tr)
            
        return np.mean(tr_list[-period:])

    @staticmethod
    def calculate_hurst_exponent(price_series, volatility_ratio=1.0):
        """
        Dynamic Hurst Exponent Calculation (Regime Filter)
        Dynamic max_lag based on market volatility
        """
        # Dynamic Lag Optimization based on volatility
        if volatility_ratio > 1.2:
            max_lag = 12  # Fast market: smaller lag
        elif volatility_ratio < 0.8:
            max_lag = 28  # Slow market: larger lag
        else:
            max_lag = 20  # Standard lag

        if len(price_series) < max_lag * 2:
            return 0.5  # Neutral / Noise

        lags = range(2, max_lag)
        tau = [np.std(np.subtract(price_series[lag:], price_series[:-lag])) for lag in lags]
        
        # Avoid division or log issues
        tau = np.where(np.array(tau) == 0, 1e-8, tau)
        
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0]

    @staticmethod
    def calculate_kama(price_series, period=10, fast=2, slow=30):
        """Kaufman's Adaptive Moving Average (KAMA)"""
        if len(price_series) < period + 1:
            return price_series[-1]

        change = abs(price_series[-1] - price_series[-period - 1])
        volatility = sum(abs(price_series[i] - price_series[i - 1]) for i in range(-period, 0))

        if volatility == 0:
            er = 0
        else:
            er = change / volatility

        sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
        kama = price_series[-period - 1] + sc * (price_series[-1] - price_series[-period - 1])
        return kama

    @classmethod
    def evaluate_tf_regime(cls, price_history, high_prices=None, low_prices=None):
        """Single Timeframe Analysis: Returns 'BULLISH', 'BEARISH', or 'NEUTRAL'"""
        prices = np.array(price_history, dtype=float)
        if len(prices) < 50:
            return "NEUTRAL", 0.5

        # ATR Volatility check
        atr_val = 0.0
        if high_prices is not None and low_prices is not None:
            atr_val = cls.calculate_atr(high_prices, low_prices, prices)
        
        # Volatility ratio for Dynamic Hurst
        std_dev = np.std(prices[-20:])
        avg_std = np.mean([np.std(prices[i-20:i]) for i in range(30, len(prices))]) if len(prices) >= 50 else std_dev
        volatility_ratio = (std_dev / avg_std) if avg_std > 0 else 1.0

        hurst = cls.calculate_hurst_exponent(prices, volatility_ratio=volatility_ratio)
        kama = cls.calculate_kama(prices)
        current_price = prices[-1]

        # Check Trend Direction
        if hurst > 0.55: # Trending Regime
            if current_price > kama:
                return "BULLISH", hurst
            elif current_price < kama:
                return "BEARISH", hurst
        
        return "NEUTRAL", hurst

    @classmethod
    def evaluate_signal(cls, tf_data_dict, is_high_impact_news=False, ask_bid_delta=None):
        """
        Multi-Timeframe Hybrid Engine Decision Logic:
        tf_data_dict format: 
        {
          '1H': {'close': [...], 'high': [...], 'low': [...]},
          '30M': {'close': [...], 'high': [...], 'low': [...]},
          '15M': {'close': [...], 'high': [...], 'low': [...]},
          '5M': {'close': [...], 'high': [...], 'low': [...]}
        }
        """
        # 1. High Impact News Filter
        if is_high_impact_news:
            return "HOLD", "High Impact Economic News Event Detected. Signal Paused."

        # 2. Multi-Timeframe Alignment Check
        required_tfs = ['1H', '30M', '15M', '5M']
        tf_results = {}
        hurst_results = {}

        for tf in required_tfs:
            if tf not in tf_data_dict or len(tf_data_dict[tf]['close']) < 50:
                return "HOLD", f"Insufficient data for timeframe {tf}."
            
            regime, H = cls.evaluate_tf_regime(
                tf_data_dict[tf]['close'],
                tf_data_dict[tf].get('high'),
                tf_data_dict[tf].get('low')
            )
            tf_results[tf] = regime
            hurst_results[tf] = H

        # Check alignment across all 4 timeframes
        all_bullish = all(status == "BULLISH" for status in tf_results.values())
        all_bearish = all(status == "BEARISH" for status in tf_results.values())

        # Order Flow Delta Filter
        ofi_delta = ask_bid_delta if ask_bid_delta is not None else 0

        # 3. Final Signal Decision
        if all_bullish and ofi_delta >= 0:
            h_str = ", ".join([f"{tf}:{hurst_results[tf]:.2f}" for tf in required_tfs])
            return "CALL (BUY)", f"Strong Multi-Timeframe Bullish Alignment ({h_str})"

        elif all_bearish and ofi_delta <= 0:
            h_str = ", ".join([f"{tf}:{hurst_results[tf]:.2f}" for tf in required_tfs])
            return "PUT (SELL)", f"Strong Multi-Timeframe Bearish Alignment ({h_str})"

        else:
            tf_summary = ", ".join([f"{tf}:{tf_results[tf]}" for tf in required_tfs])
            return "HOLD", f"Timeframes not aligned ({tf_summary}). Waiting for confirmation."
