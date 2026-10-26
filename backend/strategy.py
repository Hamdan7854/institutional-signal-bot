import numpy as np
import pandas as pd


class QuantitativeTradingStrategy:

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

  @staticmethod
  def check_safety_filters(
      current_payout: float,
      payout_threshold: float,
      is_news_time: bool,
      is_session_active: bool,
  ) -> bool:
    """Quantitative Risk Management aur Safety Gates ko enforce karta hai[cite: 8]."""
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
      df_1m: pd.DataFrame = None,
      df_5m: pd.DataFrame = None,
      price_history=None,
      tf_data_dict=None,
      ask_bid_delta=None,
      is_high_impact_news=False,
      current_payout=0.85,
      payout_threshold=0.80,
      is_news_time=False,
      is_session_active=True,
  ):
    """Main bot script ke sabhi formats ke sath compatible evaluate_signal method."""
    if is_high_impact_news or not cls.check_safety_filters(
        current_payout, payout_threshold, is_news_time, is_session_active
    ):
      return (
          "HOLD",
          "Safety Gate Blocked: News, Payout threshold, or Session mismatch.",
      )

    # Agar tf_data_dict pass ho raha hai toh usse DataFrames nikal lein
    if (
        tf_data_dict is not None
        and "1M" in tf_data_dict
        and "5M" in tf_data_dict
    ):
      df_1m = tf_data_dict["1M"]
      df_5m = tf_data_dict["5M"]

    # Agar price_history pass ho rahi hai toh usko DataFrame mein convert kar ke Pro-Grade indicators apply karein
    if (
        df_1m is None
        and price_history is not None
        and len(price_history) >= 20
    ):
      closes = np.array(price_history, dtype=float)
      # Dummy high/low/close dataframes create karna taaki indicators fail na hon
      df_1m = pd.DataFrame({
          "open": closes,
          "high": closes * 1.001,
          "low": closes * 0.999,
          "close": closes,
      })
      df_5m = df_1m.copy()

    if df_1m is not None and len(df_1m) > 20:
      if "BB_Upper" not in df_1m.columns or "EMA_200" not in df_5m.columns:
        df_1m, df_5m = cls.calculate_indicators(df_1m, df_5m)

      row_1m = df_1m.iloc[-1]
      row_5m = df_5m.iloc[-1]

      htf_bullish = row_1m["close"] > row_5m["EMA_200"]
      htf_bearish = row_1m["close"] < row_5m["EMA_200"]

      # Mean-Reversion Volatility Bounce (Bollinger + RSI + Stochastic)[cite: 2, 4, 9]
      if (
          row_1m["close"] <= row_1m["BB_Lower"]
          and row_1m["RSI"] < 30
          and row_1m["Stoch_K"] < 20
          and htf_bullish
      ):
        return (
            "CALL",
            (
                "Mean-Reversion Lower Band Bounce with RSI/Stochastic"
                " Confluence"
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
                "Mean-Reversion Upper Band Bounce with RSI/Stochastic"
                " Confluence"
            ),
        )

      # Trend-Following Momentum Convergence (SMA Crossover + MACD)[cite: 2, 9]
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

    return "HOLD", "No Clear Confluence or Insufficient Data"
