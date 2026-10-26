import numpy as np
import pandas as pd


class QuantitativeTradingStrategy:

  def __init__(self, asset="EURUSD", payout_threshold=0.80):
    self.asset = asset
    self.payout_threshold = payout_threshold

  def calculate_indicators(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame):
    """Research ke mutabiq 1-minute aur 5-minute non-repainting indicators calculate karta hai."""
    # 1-Minute Indicators (Mean-Reversion & Momentum)
    df_1m["SMA_5"] = df_1m["close"].rolling(window=5).mean()
    df_1m["SMA_15"] = df_1m["close"].rolling(window=15).mean()

    # EMA & MACD for Trend Setups
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

    # 5-Minute Higher Timeframe Trend Filter
    df_5m["EMA_200"] = df_5m["close"].ewm(span=200, adjust=False).mean()

    return df_1m, df_5m

  def check_safety_filters(
      self, current_payout: float, is_news_time: bool, is_session_active: bool
  ) -> bool:
    """Quantitative Risk Management aur Safety Gates ko enforce karta hai."""
    if current_payout < self.payout_threshold:
      return False
    if is_news_time:
      return False
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
    """Multi-indicator confluence aur multi-timeframe filter ke base par CALL/PUT signal generate karta hai."""
    if not self.check_safety_filters(
        current_payout, is_news_time, is_session_active
    ):
      return "HOLD", "Safety Gate Blocked: Payout, News, or Session mismatch."

    row_1m = df_1m.iloc[-1]
    row_5m = df_5m.iloc[-1]

    htf_bullish = row_1m["close"] > row_5m["EMA_200"]
    htf_bearish = row_1m["close"] < row_5m["EMA_200"]

    # Mean-Reversion Volatility Bounce
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

    # Trend-Following Momentum Convergence
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
