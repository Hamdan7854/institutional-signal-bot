import asyncio
import json
import os
import pandas as pd
import websockets

DERIV_APP_ID = 1089  # Public demo app ID
DERIV_WS_URL = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

# Yahoo/Standard symbols ko Deriv ke forex symbols me map karna
SYMBOL_MAP = {
    "EURUSD=X": "frxEURUSD",
    "GBPUSD=X": "frxGBPUSD",
    "USDJPY=X": "frxUSDJPY",
    "AUDUSD=X": "frxAUDUSD",
    "USDCAD=X": "frxUSDCAD",
    "USDCHF=X": "frxUSDCHF",
    "NZDUSD=X": "frxNZDUSD"
}

async def fetch_deriv_candles_async(deriv_symbol: str, count=100, granularity=60):
    """Deriv WebSocket se live historical candles fetch karta hai."""
    try:
        async with websockets.connect(DERIV_WS_URL) as websocket:
            # Token authorization agar environment me mojood ho
            token = os.environ.get("DERIV_API_TOKEN")
            if token:
                await websocket.send(json.dumps({"authorize": token}))
                await websocket.recv() # auth response skip

            request = {
                "ticks_history": deriv_symbol,
                "adjust_start_time": 1,
                "count": count,
                "end": "latest",
                "granularity": granularity, # 60s for 1m, 300s for 5m, 900s for 15m
                "style": "candles"
            }
            await websocket.send(json.dumps(request))
            response = await websocket.recv()
            data = json.loads(response)
            
            if "candles" in data:
                candles = data["candles"]
                df = pd.DataFrame(candles)
                df['Datetime'] = pd.to_datetime(df['epoch'], unit='s')
                df.set_index('Datetime', inplace=True)
                df = df.rename(columns={
                    'open': 'Open',
                    'high': 'High',
                    'low': 'Low',
                    'close': 'Close'
                })
                df['Volume'] = 1000  # Default volume substitute for binary feed
                return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception as e:
        print(f"Deriv API Error for {deriv_symbol}: {e}")
    
    return pd.DataFrame()

def fetch_pair_data(symbol: str, period: str = "5d", interval: str = "1m") -> pd.DataFrame:
    """
    Deriv API se live data fetch karke strategy ko deta hai (yfinance ki jagah).
    """
    deriv_sym = SYMBOL_MAP.get(symbol, "frxEURUSD")
    
    # Interval ko seconds me convert karna Deriv granularity ke liye
    granularity = 60
    if interval == "5m":
        granularity = 300
    elif interval == "15m":
        granularity = 900
    elif interval == "1m":
        granularity = 60

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                df = pool.submit(asyncio.run, fetch_deriv_candles_async(deriv_sym, count=150, granularity=granularity)).result()
                return df
        else:
            return asyncio.run(fetch_deriv_candles_async(deriv_sym, count=150, granularity=granularity))
    except Exception as e:
        print(f"Fetch wrapper error: {e}")
        return asyncio.run(fetch_deriv_candles_async(deriv_sym, count=150, granularity=granularity))

def calculate_volume_profile(df: pd.DataFrame, bins: int = 24):
    """
    Volume Profile se Point of Control (POC) aur Naked POC targets calculate karta hai.
    """
    if df.empty:
        return None, None
    
    price_min = df['Low'].min()
    price_max = df['High'].max()
    
    if price_min == price_max:
        return float(df['Close'].iloc[-1]), float(df['Close'].iloc[-1])
    
    try:
        price_bins = pd.cut(df['Close'], bins=bins)
        volume_by_bin = df.groupby(price_bins, observed=False)['Volume'].sum()
        
        poc_bin = volume_by_bin.idxmax()
        poc_price = round((poc_bin.left + poc_bin.right) / 2, 5)
        
        npoc_price = poc_price
        return poc_price, npoc_price
    except Exception:
        curr = float(df['Close'].iloc[-1])
        return curr, curr
