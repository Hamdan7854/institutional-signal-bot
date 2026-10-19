
"""
Personal Forex 1-Minute Strategy
Data source: Yahoo Finance / yfinance

Signals: CALL, PUT, WAIT
Score: Rule-based points, NOT win probability.
Use closed candles and test in demo first.
"""

import numpy as np
import pandas as pd

MIN_CANDLES = 100
MIN_SCORE = 80
MAX_CANDLE_ATR = 2.5

FOREX_PAIRS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "NZDUSD": "NZDUSD=X",
}


def normalize_candles(data):
    """Normalize yfinance OHLC data."""
    if not isinstance(data, pd.DataFrame) or data.empty:
        return None

    df = data.copy()

    if isinstance(df.columns, pd.MultiIndex):
        # Handle standard single-ticker yfinance output
        df.columns = df.columns.get_level_values(0)

    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        return None

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=required)

    invalid = (
        (df["high"] < df["low"])
        | (df["high"] < df["open"])
        | (df["high"] < df["close"])
        | (df["low"] > df["open"])
        | (df["low"] > df["close"])
    )

    return df.loc[~invalid].copy()


def calculate_indicators(df):
    close = df["close"]
    high = df["high"]
    low = df["low"]

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 9, min_periods=9, adjust=False
    ).mean()
    avg_loss = loss.ewm(
        alpha=1 / 9, min_periods=9, adjust=False
    ).mean()

    rsi = 100 - (
        100 / (1 + avg_gain / avg_loss.replace(0, np.nan))
    )
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain == 0), 50)

    macd = (
        close.ewm(span=12, adjust=False).mean()
        - close.ewm(span=26, adjust=False).mean()
    )
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    up = high.diff()
    down = -low.diff()

    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    plus = plus_dm.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    minus = minus_dm.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    plus_di = 100 * plus / atr.replace(0, np.nan)
    minus_di = 100 * minus / atr.replace(0, np.nan)

    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denominator

    adx = dx.ewm(
        alpha=1 / 14, min_periods=14, adjust=False
    ).mean()

    return pd.DataFrame({
        "ema9": ema9,
        "ema21": ema21,
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "atr": atr,
        "adx": adx,
        "plus_di": plus_di,
        "minus_di": minus_di,
    })


def generate_signal(candles, trend_candles=None):
    """
    candles:
        Closed 1-minute OHLC DataFrame.

    trend_candles:
        Optional closed 5-minute OHLC DataFrame.
        Supply genuine 5-minute candles for multi-timeframe filtering.

    Returns:
        Signal dictionary.
    """

    result = {
        "signal": "WAIT",
        "score": 0,
        "prediction_score": 0,
        "score_type": "rule_points_not_win_probability",
        "expiry_minutes": 1,
        "reason": "No confirmed setup",
    }

    df = normalize_candles(candles)
    if df is None or len(df) < MIN_CANDLES:
        result["reason"] = "Insufficient valid 1-minute candles"
        return result

    # Require a recent timestamp. Never assume stale data is live.
    try:
        now = pd.Timestamp.now(tz="UTC")
        last_time = pd.Timestamp(df.index[-1])

        if last_time.tzinfo is None:
            last_time = last_time.tz_localize("UTC")
        else:
            last_time = last_time.tz_convert("UTC")

        age = (now - last_time).total_seconds()

        if age < 0 or age > 180:
            result["reason"] = "Stale or future-dated market data"
            return result

        if age < 60:
            result["reason"] = (
                "Latest candle may be incomplete; wait for close"
            )
            return result

        result["candle_timestamp"] = last_time.isoformat()
        result["data_age_seconds"] = round(age, 1)

    except Exception:
        result["reason"] = "Could not validate candle timestamp"
        return result

    # If 5-minute trend is not supplied, do not pretend it was checked.
    trend_up = False
    trend_down = False

    if trend_candles is not None:
        higher = normalize_candles(trend_candles)

        if higher is None or len(higher) < 30:
            result["reason"] = "Insufficient 5-minute trend data"
            return result

        hi_close = higher["close"]
        hi_ema9 = hi_close.ewm(span=9, adjust=False).mean()
        hi_ema21 = hi_close.ewm(span=21, adjust=False).mean()

        trend_up = (
            hi_close.iloc[-1] > hi_ema9.iloc[-1]
            > hi_ema21.iloc[-1]
        )
        trend_down = (
            hi_close.iloc[-1] < hi_ema9.iloc[-1]
            < hi_ema21.iloc[-1]
        )

    ind = calculate_indicators(df)
    row = ind.iloc[-1]

    if row.isna().any():
        result["reason"] = "Indicators are not ready"
        return result

    c = df.iloc[-1]
    prev = df.iloc[-2]

    candle_range = float(c["high"] - c["low"])
    atr = float(row["atr"])

    if candle_range <= 0 or atr <= 0:
        result["reason"] = "Invalid candle or volatility"
        return result

    body_ratio = abs(float(c["close"] - c["open"])) / candle_range

    if candle_range > MAX_CANDLE_ATR * atr:
        result["reason"] = "Abnormal candle; avoid chasing"
        return result

    bullish_candle = (
        c["close"] > c["open"] and body_ratio >= 0.45
    )
    bearish_candle = (
        c["close"] < c["open"] and body_ratio >= 0.45
    )

    # EMA pullback and recovery
    ema9 = float(row["ema9"])
    ema21 = float(row["ema21"])
    recent = df.iloc[-4:]

    pullback_up = (
        (recent["low"] <= ema9 * 1.0003).any()
        and c["close"] > ema9
        and c["close"] > prev["high"]
    )

    pullback_down = (
        (recent["high"] >= ema9 * 0.9997).any()
        and c["close"] < ema9
        and c["close"] < prev["low"]
    )

    rsi = float(row["rsi"])
    macd = float(row["macd"])
    macd_sig = float(row["macd_signal"])
    adx = float(row["adx"])
    plus_di = float(row["plus_di"])
    minus_di = float(row["minus_di"])

    # Weighted rules; these are not statistical probabilities.
    call_score = 0
    put_score = 0

    if c["close"] > ema9 > ema21:
        call_score += 20
    if c["close"] < ema9 < ema21:
        put_score += 20

    if 50 < rsi < 68:
        call_score += 15
    if 32 < rsi < 50:
        put_score += 15

    if macd > macd_sig:
        call_score += 15
    if macd < macd_sig:
        put_score += 15

    if adx >= 20 and plus_di > minus_di:
        call_score += 15
    if adx >= 20 and minus_di > plus_di:
        put_score += 15

    if bullish_candle:
        call_score += 15
    if bearish_candle:
        put_score += 15

    if pullback_up:
        call_score += 20
    if pullback_down:
        put_score += 20

    if trend_candles is not None:
        if trend_up:
            call_score += 15
        if trend_down:
            put_score += 15

    result.update({
        "rsi": round(rsi, 2),
        "adx": round(adx, 2),
        "ema9": round(ema9, 6),
        "ema21": round(ema21, 6),
        "macd": round(macd, 6),
        "call_score": call_score,
        "put_score": put_score,
        "trend_filter_enabled": trend_candles is not None,
    })

    call_ok = (
        call_score >= MIN_SCORE
        and call_score > put_score
        and c["close"] > ema9 > ema21
        and 50 < rsi < 68
        and macd > macd_sig
        and adx >= 20
        and plus_di > minus_di
        and bullish_candle
        and pullback_up
        and (trend_candles is None or trend_up)
    )

    put_ok = (
        put_score >= MIN_SCORE
        and put_score > call_score
        and c["close"] < ema9 < ema21
        and 32 < rsi < 50
        and macd < macd_sig
        and adx >= 20
        and minus_di > plus_di
        and bearish_candle
        and pullback_down
        and (trend_candles is None or trend_down)
    )

    if call_ok:
        result.update({
            "signal": "CALL",
            "score": call_score,
            "prediction_score": call_score,
            "reason": "Bullish trend and pullback confirmed",
        })
    elif put_ok:
        result.update({
            "signal": "PUT",
            "score": put_score,
            "prediction_score": put_score,
            "reason": "Bearish trend and pullback confirmed",
        })
    else:
        result.update({
            "signal": "WAIT",
            "score": max(call_score, put_score),
            "prediction_score": max(call_score, put_score),
            "reason": "Required conditions not aligned",
        })

    return result


# Compatibility alias for an existing bot
def get_signal(candles, trend_candles=None):
    return generate_signal(candles, trend_candles)
