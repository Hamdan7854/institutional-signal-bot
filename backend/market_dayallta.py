import yfinance as yf
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketDataReader:
    """ Retrieves and normalizes historical market OHLCV data using yfinance. """

    @staticmethod
    def fetch_ohlcv(symbol: str = "EURUSD=X", period: str = "1mo", interval: str = "1h") -> pd.DataFrame:
        """
        Downloads historical price data and returns a standardized pandas DataFrame.
        Handles formatting for all Forex pairs with 5-digit precision.
        """
        try:
            clean_symbol = symbol.upper().replace("/", "").replace("-", "").strip()
            
            if len(clean_symbol) == 6 and not clean_symbol.endswith("=X") and not "-" in symbol:
                formatted_symbol = f"{clean_symbol}=X"
            else:
                formatted_symbol = symbol.upper()

            logger.info(f"Ingesting market data for symbol '{formatted_symbol}' [Interval: {interval}, Period: {period}]...")
            ticker = yf.Ticker(formatted_symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                raise ValueError(f"No market data returned for symbol: {formatted_symbol}")
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

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
            
            # Ensure 5 decimal places precision for forex prices if it's a forex pair
            price_cols = ['open', 'high', 'low', 'close']
            for col in price_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    if "=X" in formatted_symbol or len(clean_symbol) == 6:
                        df[col] = df[col].round(5)
                    else:
                        df[col] = df[col].round(2)

            if 'volume' not in df.columns:
                df['volume'] = 1000.0
            else:
                df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(1000.0)

            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df.columns:
                    raise KeyError(f"Required column missing from market data: {col}")
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            logger.info(f"Successfully processed {len(df)} market bars for {formatted_symbol}.")
            return df[required_columns]

        except Exception as err:
            logger.error(f"Market data ingestion failure for {symbol}: {str(err)}")
            raise err
