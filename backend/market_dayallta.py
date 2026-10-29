import yfinance as yf
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketDataReader:
    """ Retrieves and normalizes historical market OHLCV data using yfinance. """

    @staticmethod
    def fetch_ohlcv(symbol: str = "BTC-USD", period: str = "1mo", interval: str = "1h") -> pd.DataFrame:
        """
        Downloads historical price data and returns a standardized pandas DataFrame.
        """
        try:
            logger.info(f"Ingesting market data for symbol '{symbol}' [Interval: {interval}, Period: {period}]...")
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                raise ValueError(f"No market data returned for symbol: {symbol}")
            
            df = df.reset_index()
            
            column_mapping = {
                'Datetime': 'timestamp',
                'Date': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            }
            df.rename(columns=column_mapping, inplace=True)
            
            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df.columns:
                    raise KeyError(f"Required column missing from market data: {col}")
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            logger.info(f"Successfully processed {len(df)} market bars for {symbol}.")
            return df[required_columns]

        except Exception as err:
            logger.error(f"Market data ingestion failure for {symbol}: {str(err)}")
            raise err
