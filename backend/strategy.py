import numpy as np
import pandas as pd
from market_dayallta import MarketAnalyzer

class QuantitativeTradingStrategy:
    
    @staticmethod
    def calculate_hurst_exponent(price_series, max_lag=20):
        """
        1. Stochastic Regime Filter (Hurst Exponent)
        H > 0.55  -> Trending Market
        H < 0.45  -> Mean-Reverting / Ranging Market
        0.45 <= H <= 0.55 -> Random Walk / Noise
        """
        if len(price_series) < max_lag * 2:
            return 0.5 # Neutral / Noise
        
        lags = range(2, max_lag)
        tau = [np.std(np.subtract(price_series[lag:], price_series[:-lag])) for lag in lags]
        
        # Linear fit to calculate Hurst Exponent
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0]

    @staticmethod
    def calculate_kama(price_series, period=10, fast=2, slow=30):
        """
        3. Kaufman's Adaptive Moving Average (KAMA)
        Noise aur false breakouts ko filter karne ke liye.
        """
        change = abs(price_series[-1] - price_series[-period])
        volatility = sum(abs(price_series[i] - price_series[i-1]) for i in range(-period + 1, 0))
        
        if volatility == 0:
            er = 0
        else:
            er = change / volatility # Efficiency Ratio
            
        sc = (er * (2/(fast + 1) - 2/(slow + 1)) + 2/(slow + 1)) ** 2
        
        # Simple KAMA estimation
        kama = price_series[-period] + sc * (price_series[-1] - price_series[-period])
        return kama

    @classmethod
    def evaluate_signal(cls, price_history, volume_history=None, ask_bid_delta=None):
        """
        2. Order Flow Engine + Regime Filter + Adaptive Smoothing
        """
        min_required_len = 50
        if len(price_history) < min_required_len:
            return "HOLD", "Insufficient market data history."

        prices = np.array(price_history)

        # Step 1: Hurst Regime Analysis
        hurst = cls.calculate_hurst_exponent(prices)
        
        # Step 2: KAMA Adaptive Smoothing
        kama_current = cls.calculate_kama(prices)
        current_price = prices[-1]

        # Step 3: Order Flow Imbalance (OFI & Delta V)
        # Note: OFI requires tick/bid-ask order book data
        ofi_delta = ask_bid_delta if ask_bid_delta is not None else 0

        # Decision Engine Logic (Strict Filtering)
        signal = "HOLD"
        reason = "No high-probability institutional setup detected."

        # Trending Market Condition (Hurst > 0.55)
        if hurst > 0.55:
            if current_price > kama_current and ofi_delta > 0:
                signal = "CALL (BUY)"
                reason = f"Bullish Trend (Hurst: {hurst:.2f}) + Strong Order Flow Delta ({ofi_delta})"
            elif current_price < kama_current and ofi_delta < 0:
                signal = "PUT (SELL)"
                reason = f"Bearish Trend (Hurst: {hurst:.2f}) + Negative Order Flow Delta ({ofi_delta})"
            else:
                reason = f"Trending Regime (Hurst: {hurst:.2f}), but Order Flow conflict."

        # Ranging / Mean Reverting Condition (Hurst < 0.45)
        elif hurst < 0.45:
            # Overbought / Oversold Reversal Logic
            if current_price < kama_current and ofi_delta > 0:
                signal = "CALL (BUY)"
                reason = f"Mean Reversion (Hurst: {hurst:.2f}) + Institutional Absorption Delta ({ofi_delta})"
            elif current_price > kama_current and ofi_delta < 0:
                signal = "PUT (SELL)"
                reason = f"Mean Reversion (Hurst: {hurst:.2f}) + Institutional Exhaustion Delta ({ofi_delta})"
            else:
                reason = f"Ranging Market (Hurst: {hurst:.2f}), waiting for exhaustion."

        else:
            reason = f"Random Walk / Noise Detected (Hurst: {hurst:.2f}). Trade Filtered."

        return signal, reason
