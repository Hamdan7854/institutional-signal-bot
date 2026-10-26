import numpy as np
import pandas as pd


class ProGradeBinaryStrategy:
  """Research aur Pro-Grade Binary Option Bots ke mutabiq pure Strategy

  Engine (Mean-Reversion, Trend-Following, aur Safety Gates).
  """

  def __init__(self, asset="EURUSD", payout_threshold=0.80):
    self.asset = asset
    self.payout_threshold = payout_threshold

  @staticmethod
  def calculate_indicators(df_1m: pd.DataFrame, df_5m: pd.DataFrame):
    """Research ke mutabiq 1-minute aur 5-minute non-repainting indicators calculate karta hai[cite: 1, 3, 9]."""
    # 1-Minute Indicators (Mean-Reversion & Momentum)
    df_1m["SMA_5"] = df_1m["close"].rolling(window=5).mean()
    df_1m["SMA_15"] = df_1m["close"].rolling(window=15).mean()

    # EMA & MACD for Trend Setups[cite: 9]
    exp1 = df_1m["close"].ewm(span=9, adjust=False).mean()
    exp2 = df_1m["close"].ewm(span=21, adjust=False).mean()
    df_1m["MACD"] = exp1 - exp2
    df_1m["MACD_Signal"] = df_1m["MACD"].ewm(span=7, adjust=False).mean()

    # Bollinger Bands (20, 2)[cite: 2, 9]
    df_1m["BB_Middle"] = df_1m["close"].rolling(window=20).mean()
    std_dev = df_1m["close"].rolling(window=20).std()
    df_1m["BB_Upper"] = df_1m["BB_Middle"] + (std_dev * 2)
    df_1m["BB_Lower"] = df_1m["BB_Middle"] - (std_dev * 2)

    # RSI (14)[cite: 2, 9]
    delta = df_1m["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_1m["RSI"] = 100 - (100 / (1 + rs))

    # Stochastic Oscillator (%K 14, %D 3)[cite: 2, 9]
    low_14 = df_1m["low"].rolling(window=14).min()
    high_14 = df_1m["high"].rolling(window=14).max()
    df_1m["Stoch_K"] = (
        (df_1m["close"] - low_14) / (high_14 - low_14)
    ) * 100
    df_1m["Stoch_D"] = df_1m["Stoch_K"].rolling(window=3).mean()

    # 5-Minute Higher Timeframe Trend Filter[cite: 3, 9]
    df_5m["EMA_200"] = df_5m["close"].ewm(span=200, adjust=False).mean()

    return df_1m, df_5m

  def check_safety_filters(
      self, current_payout: float, is_news_time: bool, is_session_active: bool
  ) -> bool:
    """Quantitative Risk Management aur Safety Gates ko enforce karta hai[cite: 8]."""
    # 1. Payout Threshold Gating (Must be >= 80%)[cite: 8, 9]
    if current_payout < self.payout_threshold:
      return False

    # 2. Fundamental News Filter (No trade during high-impact news)[cite: 8, 9]
    if is_news_time:
      return False

    # 3. Session & Volatility Time Filters (London/New York overlap preferred)[cite: 8]
    if not is_session_active:
      return False

    return True

  def generate_signal(
      self,
      df_1m: pd.DataFrame,
      df_5m: pd.DataFrame,
      current_payout: float,
      is_news_time: bool,
      is_session_active: bool,
  ):
    """Multi-indicator confluence aur multi-timeframe filter ke base par CALL/PUT signal generate karta hai[cite: 3, 9]."""

    # Safety checks validate karein
    if not self.check_safety_filters(
        current_payout, is_news_time, is_session_active
    ):
      return "HOLD", "Safety Gate Blocked: Payout, News, or Session mismatch."

    # Latest row data
    row_1m = df_1m.iloc[-1]
    row_5m = df_5m.iloc[-1]

    # Higher Timeframe Trend Bias (5-min EMA 200 check)[cite: 3, 9]
    htf_bullish = row_1m["close"] > row_5m["EMA_200"]
    htf_bearish = row_1m["close"] < row_5m["EMA_200"]

    # Strategy 1: Mean-Reversion Volatility Bounce (Bollinger + RSI + Stochastic)[cite: 2, 4, 9]
    if (
        row_1m["close"] <= row_1m["BB_Lower"]
        and row_1m["RSI"] < 30
        and row_1m["Stoch_K"] < 20
        and htf_bullish
    ):
      return (
          "CALL",
          "Mean-Reversion Lower Band Bounce with RSI/Stochastic Confluence",
      )

    if (
        row_1m["close"] >= row_1m["BB_Upper"]
        and row_1m["RSI"] > 70
        and row_1m["Stoch_K"] > 80
        and htf_bearish
    ):
      return (
          "PUT",
          "Mean-Reversion Upper Band Bounce with RSI/Stochastic Confluence",
      )

    # Strategy 2: Trend-Following Momentum Convergence (SMA/EMA Crossover + MACD)[cite: 2, 9]
    if (
        row_1m["SMA_5"] > row_1m["SMA_15"]
        and row_1m["MACD"] > row_1m["MACD_Signal"]
        and htf_bullish
    ):
      return "CALL", "Trend-Following Crossover & MACD Convergence"

    if (
        row_1m["SMA_5"] < row_1m["SMA_15"]
        and row_1m["MACD"] < row_1m["MACD_Signal"]
        and htf_bearish
    ):
      return "PUT", "Trend-Following Crossover & MACD Convergence"

    return "HOLD", "No Clear Confluence"
