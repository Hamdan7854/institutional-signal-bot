
import numpy as np
import pandas as pd

from config import (
    RSI_PERIOD,
    EMA_FAST,
    EMA_SLOW,
    KELTNER_PERIOD,
    ATR_PERIOD,
    ATR_MULTIPLIER,
    MIN_CANDLES,
)


class InstitutionalEngine:

    def __init__(
        self,
        data=None,
        rsi_period=RSI_PERIOD,
        ema_fast_period=EMA_FAST,
        ema_slow_period=EMA_SLOW,
        keltner_period=KELTNER_PERIOD,
        atr_period=ATR_PERIOD,
        atr_multiplier=ATR_MULTIPLIER,
        min_candles=MIN_CANDLES,
        expiry_seconds=60,
        timeframe="1m",
    ):
        self.data = data
        self.rsi_period = rsi_period
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.keltner_period = keltner_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.min_candles = min_candles
        self.expiry_seconds = expiry_seconds
        self.timeframe = timeframe

    @staticmethod
    def _prepare_data(df):
        if df is None or not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = [
            str(column).strip().lower()
            for column in df.columns
        ]

        required = ["open", "high", "low", "close"]

        if not all(column in df.columns for column in required):
            return pd.DataFrame()

        for column in required:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        df = df.dropna(subset=required)

        df = df[
            (df["open"] > 0)
            & (df["high"] > 0)
            & (df["low"] > 0)
            & (df["close"] > 0)
            & (df["high"] >= df["low"])
        ]

        return df

    def calculate_indicators(self, df):
        df = self._prepare_data(df)

        if df.empty:
            return df

        df["EMA_20"] = df["close"].ewm(
            span=self.ema_fast_period,
            adjust=False
        ).mean()

        df["EMA_50"] = df["close"].ewm(
            span=self.ema_slow_period,
            adjust=False
        ).mean()

        previous_close = df["close"].shift(1)

        true_range = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - previous_close).abs(),
                (df["low"] - previous_close).abs(),
            ],
            axis=1
        ).max(axis=1)

        df["ATR"] = true_range.ewm(
            alpha=1 / self.atr_period,
            adjust=False,
            min_periods=self.atr_period
        ).mean()

        df["KC_MIDDLE"] = df["close"].ewm(
            span=self.keltner_period,
            adjust=False
        ).mean()

        df["KC_UPPER"] = (
            df["KC_MIDDLE"]
            + self.atr_multiplier * df["ATR"]
        )

        df["KC_LOWER"] = (
            df["KC_MIDDLE"]
            - self.atr_multiplier * df["ATR"]
        )

        delta = df["close"].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        average_gain = gain.ewm(
            alpha=1 / self.rsi_period,
            adjust=False,
            min_periods=self.rsi_period
        ).mean()

        average_loss = loss.ewm(
            alpha=1 / self.rsi_period,
            adjust=False,
            min_periods=self.rsi_period
        ).mean()

        relative_strength = average_gain / average_loss.replace(
            0, np.nan
        )

        df["RSI"] = 100 - (
            100 / (1 + relative_strength)
        )

        df.loc[
            (average_loss == 0) & (average_gain > 0),
            "RSI"
        ] = 100

        df.loc[
            (average_loss == 0) & (average_gain == 0),
            "RSI"
        ] = 50

        return df

    @staticmethod
    def _number(value):
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _wait_result(self, reason, close=None, rsi=None,
                     ema20=None, ema50=None):
        return {
            "action": "WAIT",
            "signal": "WAIT",
            "entry_price": self._number(close),
            "close": self._number(close),
            "score": 0,
            "reason": reason,
            "rsi": self._number(rsi),
            "ema20": self._number(ema20),
            "ema50": self._number(ema50),
            "keltner_upper": None,
            "keltner_lower": None,
        }

    def analyze_market(self, df=None):
        if df is None:
            df = self.data

        prepared = self._prepare_data(df)

        if prepared.empty:
            return self._wait_result(
                "No valid market candle data."
            )

        if len(prepared) < self.min_candles:
            return self._wait_result(
                f"Not enough candles: {len(prepared)}; "
                f"minimum required: {self.min_candles}.",
                close=prepared["close"].iloc[-1]
            )

        data = self.calculate_indicators(prepared)

        if data.empty:
            return self._wait_result(
                "Indicators could not be calculated."
            )

        last = data.iloc[-1]
        previous = data.iloc[-2]

        close = self._number(last["close"])
        rsi = self._number(last["RSI"])
        previous_rsi = self._number(previous["RSI"])
        ema20 = self._number(last["EMA_20"])
        ema50 = self._number(last["EMA_50"])
        upper = self._number(last["KC_UPPER"])
        lower = self._number(last["KC_LOWER"])

        if any(
            value is None
            for value in (
                close, rsi, previous_rsi, ema20, ema50,
                upper, lower
            )
        ):
            return self._wait_result(
                "Indicator values are not ready.",
                close, rsi, ema20, ema50
            )

        # Original strategy conditions:
        # CALL: lower Keltner band touched in latest/previous
        # candle, RSI crosses upward through 50, EMA20 > EMA50.
        lower_touched = (
            last["low"] <= last["KC_LOWER"]
            or previous["low"] <= previous["KC_LOWER"]
        )

        rsi_cross_up = previous_rsi < 50 <= rsi
        bullish_trend = ema20 > ema50

        # PUT: upper Keltner band touched in latest/previous
        # candle, RSI crosses downward through 50, EMA20 < EMA50.
        upper_touched = (
            last["high"] >= last["KC_UPPER"]
            or previous["high"] >= previous["KC_UPPER"]
        )

        rsi_cross_down = previous_rsi > 50 >= rsi
        bearish_trend = ema20 < ema50

        if lower_touched and rsi_cross_up and bullish_trend:
            signal = "CALL"
            reason = (
                "Lower Keltner touch + RSI crossed above 50 "
                "+ EMA20 above EMA50."
            )
            score = 85

        elif upper_touched and rsi_cross_down and bearish_trend:
            signal = "PUT"
            reason = (
                "Upper Keltner touch + RSI crossed below 50 "
                "+ EMA20 below EMA50."
            )
            score = 85

        else:
            signal = "WAIT"
            score = 0
            reason = (
                "The complete strategy conditions are not aligned."
            )

        return {
            "action": signal,
            "signal": signal,
            "entry_price": close,
            "close": close,
            "score": score,
            "reason": reason,
            "rsi": rsi,
            "ema20": ema20,
            "ema50": ema50,
            "keltner_upper": upper,
            "keltner_lower": lower,
        }

    def generate_signal(self, df=None, symbol=None):
        return self.analyze_market(df=df)

    def evaluate_signal(self, symbol_or_df=None):
        if isinstance(symbol_or_df, pd.DataFrame):
            return self.analyze_market(df=symbol_or_df)

        if self.data is not None:
            return self.analyze_market(df=self.data)

        return self._wait_result(
            "Pass a DataFrame containing OHLC candle data."
        )


Strategy = InstitutionalEngine
