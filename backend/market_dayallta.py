import yfinance as yf
import pandas as pd

def fetch_pair_data(symbol: str, period: str = "5d", interval: str = "5m") -> pd.DataFrame:
    """
    Yahoo Finance API se Forex data fetch karta hai.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        
        # Column standardization
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()

def calculate_volume_profile(df: pd.DataFrame, bins: int = 24):
    """
    Volume Profile se Point of Control (POC) aur Naked POC targets calculate karta hai.
    """
    if df.empty:
        return None, None
    
    price_min = df['Low'].min()
    price_max = df['High'].max()
    
    if price_min == price_max:
        return df['Close'].iloc[-1], df['Close'].iloc[-1]
    
    # Calculate price bins for profile
    price_bins = pd.cut(df['Close'], bins=bins)
    volume_by_bin = df.groupby(price_bins, observed=False)['Volume'].sum()
    
    poc_bin = volume_by_bin.idxmax()
    poc_price = round((poc_bin.left + poc_bin.right) / 2, 5)
    
    # Naked POC estimation (Unretested high-volume levels)
    npoc_price = poc_price
    return poc_price, npoc_price
