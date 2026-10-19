
import logging

import pandas as pd
import yfinance as yf

from config import (
    MARKET_INTERVAL,
    MARKET_PERIOD,
    MIN_CANDLES,
)

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """Fetch historical OHLC candles from Yahoo Finance."""

    def __init__(self):
        self.secondary_enabled = False

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Convert EUR/USD into EURUSD=X for Yahoo Finance."""
        clean = str(symbol).strip().upper().replace("/", "")

        if clean.endswith("=X"):
            return clean

        if len(clean) == 6 and clean.isalpha():
            return clean + "=X"

        raise ValueError(
            f"Unsupported forex symbol: {symbol}"
        )

    def get_historical_data(self, symbol: str) -> pd.DataFrame:
        columns = ["open", "high", "low", "close", "volume"]

        try:
            yf_symbol = self.normalize_symbol(symbol)

            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(
                period=MARKET_PERIOD,
                interval=MARKET_INTERVAL,
                auto_adjust=False,
            )

            if df is None or df.empty:
                logger.warning(
                    "No market candles received for %s",
                    yf_symbol,
                )
                return pd.DataFrame(columns=columns)

            df = df.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            df.columns = [
                str(column).strip().lower()
                for column in df.columns
            ]

            required = ["open", "high", "low", "close"]

            if not all(column in df.columns for column in required):
                logger.error(
                    "Missing OHLC columns for %s",
                    yf_symbol,
                )
                return pd.DataFrame(columns=columns)

            if "volume" not in df.columns:
                df["volume"] = 0

            for column in columns:
                df[column] = pd.to_numeric(
                    df[column], errors="coerce"
                )

            df = df.dropna(subset=required)

            df = df[
                (df["high"] >= df["low"])
                & (df["open"] > 0)
                & (df["high"] > 0)
                & (df["low"] > 0)
                & (df["close"] > 0)
            ]

            # Avoid using a potentially unfinished latest candle.
            # Yahoo timestamps may be timezone-aware.
            if len(df) > 0:
                now = pd.Timestamp.now(tz=df.index.tz)
                latest_time = df.index[-1]

                if (now - latest_time).total_seconds() < 60:
                    df = df.iloc[:-1]

            if len(df) < MIN_CANDLES:
                logger.warning(
                    "%s has only %s usable candles",
                    yf_symbol,
                    len(df),
                )

            return df[columns].copy()

        except Exception:
            logger.exception(
                "Market data fetch failed for %s", symbol
            )
            return pd.DataFrame(columns=columns)
