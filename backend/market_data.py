import asyncio
import logging
import pandas as pd
from twelvedata import TDClient
import config

logger = logging.getLogger(__name__)

class MarketDataProvider:
    def __init__(self):
        self.api_key = config.TWELVEDATA_API_KEY
        self.use_td = self.api_key and self.api_key != "YOUR_TWELVEDATA_API_KEY_HERE"
        if self.use_td:
            self.td_client = TDClient(apikey=self.api_key)
            logger.info("Twelve Data client initialized.")
        else:
            logger.warning("Twelve Data API key not found or invalid!")

    async def fetch_ohlcv(self, symbol: str) -> pd.DataFrame:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_fetch, symbol)

    def _sync_fetch(self, symbol: str) -> pd.DataFrame:
        if not self.use_td:
            raise ValueError("Twelve Data API Key is missing. Please set TWELVEDATA_API_KEY in Render Environment Variables.")

        try:
            formatted_symbol = symbol.upper()
            if "/" not in formatted_symbol and len(formatted_symbol) == 6:
                formatted_symbol = f"{formatted_symbol[:3]}/{formatted_symbol[3:]}"

            ts = self.td_client.time_series(
                symbol=formatted_symbol,
                interval=config.TIMEFRAME,
                outputsize=config.CANDLE_COUNT
            )
            df = ts.as_pandas()

            if df is None or df.empty:
                raise ValueError(f"Empty dataframe returned from Twelve Data for {formatted_symbol}")

            df = df.sort_index(ascending=True)
            
            # Reset index if datetime is stored as index to make it a standard column temporarily if needed
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()

            # Automatically map any casing variation of columns to lowercase
            df.columns = [str(col).strip().lower() for col in df.columns]
            
            required_cols = ['open', 'high', 'low', 'close']
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Missing required column '{col}' in fetched data. Available columns: {list(df.columns)}")
                df[col] = df[col].astype(float)

            return df

        except Exception as e:
            logger.error(f"Twelve Data fetch error for {symbol}: {e}")
            raise ValueError(f"Unable to fetch valid OHLCV candle data for: {symbol} ({str(e)})")
