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
            # Clean symbol format for Twelve Data (e.g., EUR/USD)
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

            # Twelve Data returns dataframe with index as datetime or columns reversed sometimes
            df = df.sort_index(ascending=True)
            
            # Standardize column names
            rename_map = {}
            for col in df.columns:
                lower_col = col.lower()
                if 'open' in lower_col: rename_map[col] = 'open'
                elif 'high' in lower_col: rename_map[col] = 'high'
                elif 'low' in lower_col: rename_map[col] = 'low'
                elif 'close' in lower_col: rename_map[col] = 'close'
                elif 'volume' in lower_col: rename_map[col] = 'volume'
            
            df.rename(columns=rename_map, inplace=True)
            
            required_cols = ['open', 'high', 'low', 'close']
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Missing required column {col} in fetched data.")
                df[col] = df[col].astype(float)

            return df

        except Exception as e:
            logger.error(f"Twelve Data fetch error for {symbol}: {e}")
            raise ValueError(f"Unable to fetch valid OHLCV candle data for: {symbol} ({str(e)})")
