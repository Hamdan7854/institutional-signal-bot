import numpy as np
import pandas as pd


class QuantitativeTradingStrategy:

  def __init__(self, asset="EURUSD", payout_threshold=0.80):
    self.asset = asset
    self.payout_threshold = payout_threshold

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
      hl = high_prices[i] - low_prices[i]
      hc = abs(high_prices[i] - close_prices[i - 1])
      lc = abs(low_prices[i] - close_prices[i - 1])
      tr = max(hl, hc, lc)
      tr_list.append(tr)
    return np.mean(tr_list[-period:])

  @staticmethod
  def calculate_hurst_exponent(price_series, volatility_ratio=1.0):
    """Dynamic Hurst Exponent Calculation (Regime Filter)"""
    if volatility_ratio > 1.2:
      max_lag = 12  # Fast market: smaller lag
    elif volatility_ratio < 0.8:
      max_lag = 28  # Slow market: larger lag
    else:
      max_lag = 20  # Standard lag

    if len(price_series) < max_lag * 2:
      return 0.5  # Neutral / Noise

    lags = range(2, max_lag)
    tau = [
        np.std(np.subtract(price_series[lag:], price_series[:-lag]))
        for lag in lags
    ]
    tau = np.where(np.array(tau) == 0, 1e-8, tau)
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return poly[0]

  @staticmethod
  def calculate_kama(price_series, period=10, fast=2, slow=30):
    """Kaufman's Adaptive Moving Average (KAMA)"""
    if len(price_series) < period:
      return price_series[-1]

    change = abs(price_series[-1] - price_series[-period])
    volatility = sum(
        abs(price_series[i] - price_series[i - 1]) for i in range(1, period + 1)
    )

    if volatility == 0:
      er = 0
    else:
      er = change / volatility

    sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
    return price_series[-1]

  @classmethod
  def evaluate_tf_regime(
      cls, price_history, high_prices=None, low_prices=None
  ):
    """Single Timeframe Analysis: Returns Regime and Hurst Value"""
    prices = np.array(price_history, dtype=float)
    if len(prices) < 50:
      return "NEUTRAL", 0.5

    std_dev = np.std(prices[-20:])
    avg_std = np.mean([np.std(prices[i - 20 : i]) for i in range(30, len(prices))])
    volatility_ratio = std_dev / avg_std if avg_std > 0 else 1.0

    hurst = cls.calculate_hurst_exponent(prices, volatility_ratio=volatility_ratio)
    kama = cls.calculate_kama(prices)
    current_price = prices[-1]

    if hurst > 0.55:
      if current_price > kama:
        return "BULLISH", hurst
      elif current_price < kama:
        return "BEARISH", hurst

    return "NEUTRAL", hurst

  @staticmethod
  def check_safety_filters(
      current_payout: float,
      payout_threshold: float,
      is_news_time: bool,
      is_session_active: bool,
  ) -> bool:
    """Pro-Grade Risk Management & Safety Gates (Payout, News, Session)"""
    if current_payout < payout_threshold:
      return False
    if is_news_time:
      return False
    if not is_session_active:
      return False
    return True

  @classmethod
  def evaluate_signal(
      cls,
      price_history=None,
      tf_data_dict=None,
      df_1m=None,
      df_5m=None,
      ask_bid_delta=None,
      is_high_impact_news=False,
      current_payout=0.85,
      payout_threshold=0.80,
      is_news_time=False,
      is_session_active=True,
  ):
    """Hybrid Decision Engine: Hurst/KAMA high-accuracy core + Safety Filters"""

    # 1. Safety Gates Check (Payout, News, Session)
    if is_high_impact_news or not cls.check_safety_filters(
        current_payout, payout_threshold, is_news_time, is_session_active
    ):
      return (
          "HOLD",
          (
              "Safety Gate Blocked: Payout below threshold, News, or"
              " Session mismatch."
          ),
      )

    # 2. Agar DataFrame ya tf_data_dict diya gaya hai toh prices extract karein
    if (
        price_history is None
        and tf_data_dict is not None
        and "1M" in tf_data_dict
    ):
      price_history = tf_data_dict["1M"]["close"].values
    elif price_history is None and df_1m is not None:
      price_history = df_1m["close"].values

    # 3. High-Accuracy Hurst Exponent & KAMA Core Logic
    if price_history is not None:
      prices = np.array(price_history, dtype=float)
      if len(prices) < 50:
        return "HOLD", "Insufficient market data history."

      region, hurst = cls.evaluate_tf_regime(prices)
      kama = cls.calculate_kama(prices)
      current_price = prices[-1]

      # Noise / Random Walk Filter (Loss se bachane ke liye)
      if 0.45 <= hurst <= 0.55:
        return "HOLD", f"Random Walk / Noise Detected (Hurst: {hurst:.2f})"

      # Trending Market Strategy
      if hurst > 0.55:
        if current_price > kama and (
            ask_bid_delta is None or ask_bid_delta > 0
        ):
          return "CALL", f"High-Accuracy Bullish Trend (Hurst: {hurst:.2f})"
        elif current_price < kama and (
            ask_bid_delta is None or ask_bid_delta < 0
        ):
          return "PUT", f"High-Accuracy Bearish Trend (Hurst: {hurst:.2f})"
        else:
          return (
              "HOLD",
              f"Trending Regime (Hurst: {hurst:.2f}), Delta Filter Blocked",
          )

      # Mean-Reversion Market Strategy
      else:
        if current_price > kama and (
            ask_bid_delta is None or ask_bid_delta > 0
        ):
          return "PUT", f"High-Accuracy Mean Reversion Reversal (Hurst: {hurst:.2f})"
        elif current_price < kama and (
            ask_bid_delta is None or ask_bid_delta < 0
        ):
          return "CALL", f"High-Accuracy Mean Reversion Reversal (Hurst: {hurst:.2f})"
        else:
          return "HOLD", f"Ranging Market (Hurst: {hurst:.2f})"

    return "HOLD", "No valid market data or configuration provided."
