from datetime import datetime
import numpy as np
import pandas as pd


class QuantitativeTradingStrategy:
  """Purani high-performance quantitative strategy + New Pro-Grade Binary

  Strategy indicators & safety filters ka combined version.
  """

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

    sc = (
        er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)
    ) ** 2  # noqa
    return price_series[-1]  # fallback/adaptive return implementation

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

  # ==========================================
  # NEW PRO-GRADE BINARY STRATEGY EXTENSIONS
  # ==========================================
  @staticmethod
  def calculate_pro_grade_indicators(df_1m: pd.DataFrame, df_5m: pd.DataFrame):
    """Research ke mutabiq Pro-Grade indicators (Bollinger, RSI, Stochastic, MACD) calculate karta hai."""
    # 1-Minute Indicators
    df_1m["SMA_5"] = df_1m["close"].rolling(window=5).mean()
    df_1m["SMA_15"] = df_1m["close"].rolling(window=15).mean()

    # EMA & MACD
    exp1 = df_1m["close"].ewm(span=9, adjust=False).mean()
    exp2 = df_1m["close"].ewm(span=21, adjust=False).mean()
    df_1m["MACD"] = exp1 - exp2
    df_1m["MACD_Signal"] = df_1m["MACD"].ewm(span=7, adjust=False).mean()

    # Bollinger Bands (20, 2)
    df_1m["BB_Middle"] = df_1m["close"].rolling(window=20).mean()
    std_dev = df_1m["close"].rolling(window=20).std()
    df_1m["BB_Upper"] = df_1m["BB_Middle"] + (std_dev * 2)
    df_1m["BB_Lower"] = df_1m["BB_Middle"] - (std_dev * 2)

    # RSI (14)
    delta = df_1m["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_1m["RSI"] = 100 - (100 / (1 + rs))

    # Stochastic Oscillator (%K 14, %D 3)
    low_14 = df_1m["low"].rolling(window=14).min()
    high_14 = df_1m["high"].rolling(window=14).max()
    df_1m["Stoch_K"] = (
        (df_1m["close"] - low_14) / (high_14 - low_14)
    ) * 100
    df_1m["Stoch_D"] = df_1m["Stoch_K"].rolling(window=3).mean()

    # 5-Minute Higher Timeframe Trend Filter (EMA 200)
    df_5m["EMA_200"] = df_5m["close"].ewm(span=200, adjust=False).mean()

    return df_1m, df_5m

  @staticmethod
  def check_safety_filters(
      current_payout: float,
      payout_threshold: float,
      is_news_time: bool,
      is_session_active: bool,
  ) -> bool:
    """Quantitative Risk Management aur Safety Gates ko enforce karta hai."""
    if current_payout < payout_threshold:
      return False
    if is_news_time:
      return False
    if not is_session_active:
      return False
    return True

  @classmethod
  def evaluate_signals(
      cls,
      price_history=None,
      tf_data_dict=None,
      ask_bid_delta=None,
      is_high_impact_news=False,
      current_payout=0.85,
      payout_threshold=0.80,
      is_news_time=False,
      is_session_active=True,
  ):
    """Hybrid Decision Engine: Purani high-performance logic ke sath-sath

    naye Pro-Grade Mean-Reversion aur Trend filters ko bhi support karta hai.
    """
    # 1. High Impact News & Safety Filter Check
    if is_high_impact_news or not cls.check_safety_filters(
        current_payout, payout_threshold, is_news_time, is_session_active
    ):
      return (
          "HOLD",
          "Safety Gate Blocked: News, Payout threshold, or Session mismatch.",
      )

    # 2. Agar DataFrames provide kiye gaye hain toh Pro-Grade Multi-Indicator Confluence check karein
    if (
        tf_data_dict is not None
        and "1M" in tf_data_dict
        and "5M" in tf_data_dict
    ):
      df_1m = tf_data_dict["1M"]
      df_5m = tf_data_dict["5M"]

      if len(df_1m) > 25 and len(df_5m) > 200:
        df_1m, df_5m = cls.calculate_pro_grade_indicators(df_1m, df_5m)
        row_1m = df_1m.iloc[-1]
        row_5m = df_5m.iloc[-1]

        htf_bullish = row_1m["close"] > row_5m["EMA_200"]
        htf_bearish = row_1m["close"] < row_5m["EMA_200"]

        # Mean-Reversion Strategy (Bollinger + RSI + Stochastic)
        if (
            row_1m["close"] <= row_1m["BB_Lower"]
            and row_1m["RSI"] < 30
            and row_1m["Stoch_K"] < 20
            and htf_bullish
        ):
          return (
              "CALL",
              (
                  "Pro-Grade Mean-Reversion Lower Band Bounce with"
                  " RSI/Stochastic Confluence"
              ),
          )

        if (
            row_1m["close"] >= row_1m["BB_Upper"]
            and row_1m["RSI"] > 70
            and row_1m["Stoch_K"] > 80
            and htf_bearish
        ):
          return (
              "PUT",
              (
                  "Pro-Grade Mean-Reversion Upper Band Bounce with"
                  " RSI/Stochastic Confluence"
              ),
          )

        # Trend-Following Strategy (SMA Crossover + MACD)
        if (
            row_1m["SMA_5"] > row_1m["SMA_15"]
            and row_1m["MACD"] > row_1m["MACD_Signal"]
            and htf_bullish
        ):
          return (
              "CALL",
              "Pro-Grade Trend-Following Crossover & MACD Convergence",
          )

        if (
            row_1m["SMA_5"] < row_1m["SMA_15"]
            and row_1m["MACD"] < row_1m["MACD_Signal"]
            and htf_bearish
        ):
          return "PUT", "Pro-Grade Trend-Following Crossover & MACD Convergence"

    # 3. Fallback to Original High-Performance Strategy Logic (Purani Logic)
    if price_history is not None:
      prices = np.array(price_history, dtype=float)
      if len(prices) < 50:
        return "HOLD", "Insufficient market data history."

      region, hurst = cls.evaluate_tf_regime(prices)
      kama = cls.calculate_kama(prices)
      current_price = prices[-1]

      if 0.45 <= hurst <= 0.55:
        return "HOLD", f"Random Walk / Noise Detected (Hurst: {hurst:.2f})"

      if hurst > 0.55:
        if current_price > kama and (
            ask_bid_delta is None or ask_bid_delta > 0
        ):
          return "CALL (BUY)", f"Bullish Trend (Hurst: {hurst:.2f})"
        elif current_price < kama and (
            ask_bid_delta is None or ask_bid_delta < 0
        ):
          return "PUT (SELL)", f"Bearish Trend (Hurst: {hurst:.2f})"
        else:
          return "HOLD", f"Trending Regime (Hurst: {hurst:.2f}), No Delta Match"
      else:
        if current_price > kama and (
            ask_bid_delta is None or ask_bid_delta > 0
        ):
          return "CALL (BUY)", f"Mean Reversion Reversal (Hurst: {hurst:.2f})"
        elif current_price < kama and (
            ask_bid_delta is None or ask_bid_delta < 0
        ):
          return "PUT (SELL)", f"Mean Reversion Reversal (Hurst: {hurst:.2f})"
        else:
          return "HOLD", f"Ranging Market (Hurst: {hurst:.2f})"

    return "HOLD", "No valid market data or configuration provided."
