
import logging

import pandas as pd
import yfinance as yf

from config import MARKET_INTERVAL, MARKET_PERIOD

logger = logging.getLogger(__name__)


class MarketDataProvider:

    @staticmethod
    def normalize_symbol(symbol):
        clean = str(symbol).strip().upper()
        clean = clean.replace("/", "").replace("-", "")

        if clean.endswith("=X"):
            return clean

        if len(clean) == 6 and clean.isalpha():
            return clean + "=X"

        raise ValueError(
            f"Unsupported forex pair: {symbol}. "
            "Example: EUR/USD"
        )

    def get_historical_data(self, symbol):
        columns = ["open", "high", "low", "close", "volume"]

        try:
            ticker_symbol = self.normalize_symbol(symbol)

            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(
                period=MARKET_PERIOD,
                interval=MARKET_INTERVAL,
                auto_adjust=False
            )

            if df is None or df.empty:
                logger.warning(
                    "No candle data received for %s",
                    ticker_symbol
                )
                return pd.DataFrame(columns=columns)

            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })

            df.columns = [
                str(column).strip().lower()
                for column in df.columns
            ]

            required = ["open", "high", "low", "close"]

            if not all(column in df.columns for column in required):
                logger.warning("Required OHLC columns missing.")
                return pd.DataFrame(columns=columns)

            if "volume" not in df.columns:
                df["volume"] = 0

            for column in columns:
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

            if df.empty:
                return pd.DataFrame(columns=columns)

            return df[columns].copy()

        except Exception:
            logger.exception(
                "Market data request failed for %s",
                symbol
            )
            return pd.DataFrame(columns=columns)
