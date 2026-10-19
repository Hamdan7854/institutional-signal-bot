import numpy as np
import pandas as pd

MIN_CANDLES = 100
MIN_SCORE = 80
MAX_CANDLE_ATR = 2.5


class InstitutionalEngine:
    def __init__(self, data=None, **kwargs):
        self.data = data
        self.min_candles = MIN_CANDLES
        self.min_score = MIN_SCORE
        self.max_candle_atr = MAX_CANDLE_ATR

    @staticmethod
    def _normalize_candles(data):
        """Normalize yfinance OHLC data."""
        if not isinstance(data, pd.DataFrame) or data.empty:
            return None

        df = data.copy()

        if isinstance(df.columns, pd.MultiIndex):
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

    @staticmethod
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

    def analyze_market(self, df=None, trend_candles=None):
        if df is None:
            df = self.data

        result = {
            "signal": "WAIT",
            "score": 0,
            "prediction_score": 0,
            "score_type": "rule_points_not_win_probability",
            "expiry_minutes": 1,
            "reason": "No confirmed setup",
            "close": None,
            "entry_price": None,
            "rsi": None,
            "ema20": None,
            "ema50": None,
        }

        df_norm = self._normalize_candles(df)
        if df_norm is None or len(df_norm) < self.min_candles:
            result["reason"] = "Insufficient valid 1-minute candles"
            return result

        trend_up = False
        trend_down = False

        if trend_candles is not None:
            higher = self._normalize_candles(trend_candles)
            if higher is not None and len(higher) >= 30:
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

        ind = self.calculate_indicators(df_norm)
        row = ind.iloc[-1]

        if row.isna().any():
            result["reason"] = "Indicators are not ready"
            return result

        c = df_norm.iloc[-1]
        prev = df_norm.iloc[-2]

        candle_range = float(c["high"] - c["low"])
        atr = float(row["atr"])

        if candle_range <= 0 or atr <= 0:
            result["reason"] = "Invalid candle or volatility"
            return result

        body_ratio = abs(float(c["close"] - c["open"])) / candle_range

        if candle_range > self.max_candle_atr * atr:
            result["reason"] = "Abnormal candle; avoid chasing"
            return result

        bullish_candle = (
            c["close"] > c["open"] and body_ratio >= 0.45
        )
        bearish_candle = (
            c["close"] < c["open"] and body_ratio >= 0.45
        )

        ema9 = float(row["ema9"])
        ema21 = float(row["ema21"])
        recent = df_norm.iloc[-4:]

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

        close_price = float(c["close"])

        call_ok = (
            call_score >= self.min_score
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
            put_score >= self.min_score
            and put_score > call_score
            and c["close"] < ema9 < ema21
            and 32 < rsi < 50
            and macd < macd_sig
            and adx >= 20
            and minus_di > plus_di
            and bearish_candle
            and pullback_down
            and (trend_candles is None or trend_down)
        ]

        signal = "WAIT"
        score = max(call_score, put_score)
        reason = "Required conditions not aligned"

        if call_ok:
            signal = "CALL"
            score = call_score
            reason = "Bullish trend and pullback confirmed"
        elif put_ok:
            signal = "PUT"
            score = put_score
            reason = "Bearish trend and pullback confirmed"

        result.update({
            "action": signal,
            "signal": signal,
            "score": score,
            "prediction_score": score,
            "close": close_price,
            "entry_price": close_price,
            "rsi": round(rsi, 2),
            "adx": round(adx, 2),
            "ema20": round(ema9, 6),  # Mapped for main.py message format
            "ema50": round(ema21, 6),  # Mapped for main.py message format
            "ema9": round(ema9, 6),
            "ema21": round(ema21, 6),
            "macd": round(macd, 6),
            "call_score": call_score,
            "put_score": put_score,
            "reason": reason,
        })
        return result

    def generate_signal(self, candles, trend_candles=None):
        return self.analyze_market(df=candles, trend_candles=trend_candles)

    def evaluate_signal(self, symbol_or_df=None, trend_candles=None):
        if isinstance(symbol_or_df, pd.DataFrame):
            return self.analyze_market(df=symbol_or_df, trend_candles=trend_candles)
        if self.data is not None:
            return self.analyze_market(df=self.data, trend_candles=trend_candles)
        return {"action": "WAIT", "signal": "WAIT", "score": 0, "reason": "Pass DataFrame"}


# Compatibility aliases for main.py
Strategy = InstitutionalEngine
InstitutionalStrategy = InstitutionalEngine
