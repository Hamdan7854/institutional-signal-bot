""" strategy.py — RSI 50 + Keltner Channel + EMA 20/50 signal strategy. Signals only. This module does not place trades and does not guarantee a win rate. Expected input DataFrame columns: open, high, low, close (case-insensitive). Use fully closed 1-minute candles from the same market feed you check manually. """

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

try:
    from market_data import MarketDataProvider
except ImportError:
    MarketDataProvider = None


class InstitutionalEngine:
    """ Compatibility class retained for existing main.py integrations. CALL: - Price touches/penetrates the lower Keltner band on the latest candle or previous candle. - RSI crosses from below 50 to above 50. - EMA20 > EMA50. PUT: - Price touches/penetrates the upper Keltner band on the latest candle or previous candle. - RSI crosses from above 50 to below 50. - EMA20 < EMA50. Otherwise WAIT. The old fallback momentum signals were removed so that signals follow the stated setup rather than emitting weaker alternatives. """

    def __init__( self, data: Optional[pd.DataFrame] = None, rsi_period: int = 14, atr_period: int = 20, keltner_period: int = 20, atr_multiplier: float = 2.0, min_candles: int = 60, ):
        if rsi_period not in (7, 14):
            raise ValueError("rsi_period must be 7 or 14.")
        if min(atr_period, keltner_period, min_candles) < 1:
            raise ValueError("Periods and min_candles must be positive.")
        if atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be positive.")

        self.data = data.copy() if isinstance(data, pd.DataFrame) else data
        self.rsi_period = rsi_period
        self.atr_period = atr_period
        self.keltner_period = keltner_period
        self.atr_multiplier = atr_multiplier
        self.min_candles = min_candles
        self.market_provider = MarketDataProvider() if MarketDataProvider else None

@staticmethod
    def _prepare_data(df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Market data must be a pandas DataFrame.")

        out = df.copy()
        out.columns = [str(col).strip().lower() for col in out.columns]
        required = {"open", "high", "low", "close"}
        missing = required.difference(out.columns)
        if missing:
            raise ValueError(f"Missing required OHLC columns: {', '.join(sorted(missing))}")

        for col in ("open", "high", "low", "close"):
            out[col] = pd.to_numeric(out[col], errors="coerce")
        out = out.dropna(subset=["open", "high", "low", "close"])

        if (out["high"] < out["low"]).any():
            raise ValueError("Invalid candle data: high is lower than low.")
        return out

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate EMA20, EMA50, RSI and Keltner bands (EMA20 ± 2 ATR)."""
        out = self._prepare_data(df)

        close = out["close"]
        high = out["high"]
        low = out["low"]

        out["EMA_20"] = close.ewm(
            span=self.keltner_period, adjust=False,
            min_periods=self.keltner_period
        ).mean()
        out["EMA_50"] = close.ewm(
            span=50, adjust=False, min_periods=50
        ).mean()

        previous_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - previous_close).abs(),
                (low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        # Wilder-style ATR smoothing, with a 20-candle default.
        out["ATR"] = true_range.ewm(
            alpha=1 / self.atr_period, adjust=False,
            min_periods=self.atr_period
        ).mean()
        out["KC_Middle"] = out["EMA_20"]
        out["KC_Upper"] = out["KC_Middle"] + self.atr_multiplier * out["ATR"]
        out["KC_Lower"] = out["KC_Middle"] - self.atr_multiplier * out["ATR"]

        delta = close.diff()
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)
        avg_gain = gains.ewm(
            alpha=1 / self.rsi_period, adjust=False,
            min_periods=self.rsi_period
        ).mean()
        avg_loss = losses.ewm(
            alpha=1 / self.rsi_period, adjust=False,
            min_periods=self.rsi_period
        ).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        out["RSI"] = 100 - (100 / (1 + rs))
        out.loc[(avg_loss == 0) & (avg_gain > 0), "RSI"] = 100
        out.loc[(avg_loss == 0) & (avg_gain == 0), "RSI"] = 50

        # Legacy lowercase aliases retained in case another module uses them.
        out["atr"] = out["ATR"]
        out["kc_upper"] = out["KC_Upper"]
        out["kc_lower"] = out["KC_Lower"]
        out["rsi"] = out["RSI"]
        return out

@staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            result = float(value)
            return result if np.isfinite(result) else None
        except (TypeError, ValueError):
            return None

    def analyze_market(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Analyze real candle data. Missing/short data returns WAIT, never fake candles."""
        source = df if isinstance(df, pd.DataFrame) and not df.empty else self.data

        if not isinstance(source, pd.DataFrame) or source.empty:
            return {
                "action": "HOLD",
                "signal": "WAIT",
                "entry_price": None,
                "score": 0,
                "reason": "No market data available; WAIT.",
            }

        try:
            prepared = self._prepare_data(source)
        except (TypeError, ValueError) as exc:
            return {
                "action": "HOLD", "signal": "WAIT", "entry_price": None,
                "score": 0, "reason": f"Invalid market data: {exc}",
            }

        if len(prepared) < self.min_candles:
            return {
                "action": "HOLD", "signal": "WAIT",
                "entry_price": self._number(prepared["close"].iloc[-1]),
                "score": 0,
                "reason": f"Need at least {self.min_candles} candles; received {len(prepared)}.",
            }

        data = self.calculate_indicators(prepared)
        needed = ["RSI", "EMA_20", "EMA_50", "KC_Upper", "KC_Lower", "ATR"]
        valid = data.dropna(subset=needed)
        if len(valid) < 2:
            return {
                "action": "HOLD", "signal": "WAIT",
                "entry_price": self._number(data["close"].iloc[-1]),
                "score": 0, "reason": "Indicators are not ready; WAIT.",
            }

        prev = valid.iloc[-2]
        latest = valid.iloc[-1]
        prev_rsi = float(prev["RSI"])
        rsi = float(latest["RSI"])
        ema20 = float(latest["EMA_20"])
        ema50 = float(latest["EMA_50"])

        # Band touch is based on candle high/low, not close alone.
        lower_touched = (
            float(latest["low"]) <= float(latest["KC_Lower"])
            or float(prev["low"]) <= float(prev["KC_Lower"])
        )
        upper_touched = (
            float(latest["high"]) >= float(latest["KC_Upper"])
            or float(prev["high"]) >= float(prev["KC_Upper"])
        )

        rsi_cross_up = prev_rsi < 50 <= rsi
        rsi_cross_down = prev_rsi > 50 >= rsi
        bullish_trend = ema20 > ema50
        bearish_trend = ema20 < ema50

        action = "HOLD"
        signal = "WAIT"
        score = 0
        reason = "No clean setup: Keltner touch, RSI-50 crossover and EMA trend must agree."

        if lower_touched and rsi_cross_up and bullish_trend:
            action, signal, score = "BUY", "CALL", 85
            reason = "CALL setup: lower Keltner band touched, RSI crossed above 50, EMA20 > EMA50."
        elif upper_touched and rsi_cross_down and bearish_trend:
            action, signal, score = "SELL", "PUT", 85
            reason = "PUT setup: upper Keltner band touched, RSI crossed below 50, EMA20 < EMA50."

        # Score is a rule-match label, NOT a probability or a verified win rate.
        return {
            "action": action,
            "signal": signal,
            "entry_price": float(latest["close"]),
            "score": score,
            "reason": reason,
            "rsi": rsi,
            "ema20": ema20,
            "ema50": ema50,
            "keltner_upper": float(latest["KC_Upper"]),
            "keltner_lower": float(latest["KC_Lower"]),
        }

    def evaluate_signal(self, symbol_or_df):
        """Keep the old public method name for compatibility with existing main.py."""
        if isinstance(symbol_or_df, str):
            if not self.market_provider:
                return self.analyze_market(None)
            try:
                df = self.market_provider.get_historical_data(symbol_or_df)
            except Exception as exc:
                return {
                    "action": "HOLD", "signal": "WAIT", "entry_price": None,
                    "score": 0, "reason": f"Market data fetch failed: {exc}",
                }
            return self.analyze_market(df)

        if isinstance(symbol_or_df, pd.DataFrame):
            return self.analyze_market(symbol_or_df)

        return self.analyze_market(self.data)


# Alias for compatibility with the newer main.py version provided earlier.
Strategy = InstitutionalEngine
