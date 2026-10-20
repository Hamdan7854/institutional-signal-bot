import asyncio
import pandas as pd
import yfinance as yf
from twelvedata import TDClient
import config

class MarketDataProvider:
    def __init__(self):
        self.use_td = config.TWELVEDATA_API_KEY != "YOUR_TWELVEDATA_API_KEY"
        if self.use_td:
            self.td_client = TDClient(apikey=config.TWELVEDATA_API_KEY)

    async def fetch_ohlcv(self, symbol: str) -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_fetch, symbol)

    def _sync_fetch(self, symbol: str) -> pd.DataFrame:
        if self.use_td:
            try:
                ts = self.td_client.time_series(
                    symbol=symbol,
                    interval=config.TIMEFRAME,
                    outputsize=config.CANDLE_COUNT
                ).as_pandas()
                if not ts.empty:
                    df = ts.sort_index(ascending=True)
                    df.rename(columns={
                        'open': 'Open', 'high': 'High', 
                        'low': 'Low', 'close': 'Close', 'volume': 'Volume'
                    }, inplace=True)
                    return df
            except Exception:
                pass
        
        # Secondary Data Source: Yahoo Finance
        yf_symbol = symbol.replace("/", "") + "=X"
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="5d", interval=config.TIMEFRAME)
        if df.empty:
            raise ValueError(f"Unable to fetch valid OHLCV candle data for: {symbol}")
        return df
