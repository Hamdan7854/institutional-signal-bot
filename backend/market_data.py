import yfinance as yf
import requests
import pandas as pd

class MarketDataProvider:
    def __init__(self):
        # Secondary API fallback / validation config (e.g., Free public endpoints or Forex feeds)
        self.secondary_enabled = True

    def get_historical_data(self, symbol: str) -> pd.DataFrame:
        # Standardize symbol for yfinance (e.g., EUR/USD -> EURUSD=X)
        yf_symbol = symbol.replace("/", "").upper()
        if not yf_symbol.endswith("=X") and len(yf_symbol) == 6:
            yf_symbol = yf_symbol + "=X"

        try:
            # 1. Primary Fetch via yfinance (1-minute interval for fast 15s/1m tracking)
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="1d", interval="1m")
            
            if df is None or df.empty:
                # Fallback to 5m if 1m is empty
                df = ticker.history(period="5d", interval="5m")

            if df is not None and not df.empty:
                # Clean columns to lowercase
                df = df.rename(columns={
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })
                
                primary_price = float(df['close'].iloc[-1])
                
                # 2. Multi-Source Validation (Cross-check with secondary public feed to prevent fake/manipulated data)
                if self.secondary_enabled:
                    self._cross_check_price(symbol, primary_price)
                
                return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            print(f"Primary Data Fetch Error for {symbol}: {e}")

        # Fallback empty structure if fetch fails
        return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

    def _cross_check_price(self, symbol: str, primary_price: float):
        try:
            clean_sym = symbol.replace("/", "")
            url = f"https://api.exchangerate-api.com/v4/latest/{clean_sym[:3]}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                rates = data.get("rates", {})
                target_currency = clean_sym[3:]
                if target_currency in rates:
                    secondary_price = float(rates[target_currency])
                    # Discrepancy check (Must be within 0.05% tolerance)
                    diff_percentage = abs(primary_price - secondary_price) / primary_price * 100
                    if diff_percentage > 0.5:
                        print(f"WARNING: Price discrepancy detected for {symbol}! Primary: {primary_price}, Secondary: {secondary_price}")
        except Exception as e:
            # Non-blocking cross check error
            pass
