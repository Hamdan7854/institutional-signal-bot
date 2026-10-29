import pandas as pd
import numpy as np
from market_data import fetch_pair_data, calculate_volume_profile

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Next candle expected volatility calculate karta hai."""
    df['tr0'] = abs(df['High'] - df['Low'])
    df['tr1'] = abs(df['High'] - df['Close'].shift(1))
    df['tr2'] = abs(df['Low'] - df['Close'].shift(1))
    tr = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return float(atr) if not np.isnan(atr) else 0.0005

def check_higher_timeframe_trend(symbol: str) -> str:
    """
    Filter 1: Multi-Timeframe Trend Alignment (5m / 15m Trend Check).
    Bade timeframe ka trend return karta hai: 'BULLISH', 'BEARISH', ya 'NEUTRAL'.
    """
    df_htf = fetch_pair_data(symbol, period="5d", interval="15m")
    if df_htf.empty or len(df_htf) < 20:
        df_htf = fetch_pair_data(symbol, period="2d", interval="5m")
        if df_htf.empty or len(df_htf) < 20:
            return "NEUTRAL"
            
    # Simple Moving Average (SMA 20) crossover check on Higher Timeframe
    sma_20 = df_htf['Close'].rolling(20).mean().iloc[-1]
    last_close = df_htf['Close'].iloc[-1]
    
    if last_close > sma_20:
        return "BULLISH"
    elif last_close < sma_20:
        return "BEARISH"
    return "NEUTRAL"

def analyze_next_candle_target(symbol: str) -> dict:
    """
    Advanced Institutional SMC + Volume Profile + Multi-Timeframe & Exhaustion Filter Engine.
    """
    # 1. Fetch 1-minute data for immediate next candle setup
    df = fetch_pair_data(symbol, period="2d", interval="1m")
    if df.empty or len(df) < 30:
        df = fetch_pair_data(symbol, period="5d", interval="5m")
        if df.empty or len(df) < 30:
            return None
    
    curr_price = round(float(df['Close'].iloc[-1]), 5)
    prev_close = round(float(df['Close'].iloc[-2]), 5)
    prev_open = round(float(df['Open'].iloc[-2]), 5)
    prev_high = round(float(df['High'].iloc[-2]), 5)
    prev_low = round(float(df['Low'].iloc[-2]), 5)
    
    atr = calculate_atr(df)
    poc_price, npoc_price = calculate_volume_profile(df)
    
    # 2. Filter 4: Candle Exhaustion & Wick Rejection Rule
    prev_body = abs(prev_close - prev_open)
    prev_range = prev_high - prev_low
    
    # Agar pichli candle ki body ATR se bhot bari ho (Exhaustion) ya wick total range ka 60% se zyada ho (Rejection)
    if prev_range > (atr * 2.5) or (prev_range > 0 and (prev_body / prev_range) < 0.25):
        # Market mein excessive noise ya reversal risk hai, signal skip kar do
        return None

    # 3. Filter 1: Multi-Timeframe Trend Check (5m/15m)
    htf_trend = check_higher_timeframe_trend(symbol)

    # 4. Fair Value Gap (FVG) Calculation
    fvg_target = None
    c1_high = df['High'].iloc[-3]
    c1_low = df['Low'].iloc[-3]
    c3_high = df['High'].iloc[-1]
    c3_low = df['Low'].iloc[-1]
    
    if c3_low > c1_high:
        fvg_target = round((c3_low + c1_high) / 2, 5)
    elif c3_high < c1_low:
        fvg_target = round((c3_high + c1_low) / 2, 5)

    # 5. Liquidity Levels
    recent_highs = round(float(df['High'].iloc[-20:-1].max()), 5)
    recent_lows = round(float(df['Low'].iloc[-20:-1].min()), 5)
    
    is_candle_green = prev_close > prev_open
    
    direction = "NEUTRAL"
    predicted_target = curr_price
    confluence_factors = []
    confidence = 82

    # Bullish Logic (Strictly aligned with Higher Timeframe Bullish Trend)
    if (curr_price >= prev_close or is_candle_green) and htf_trend != "BEARISH":
        direction = "BULLISH 🟢"
        targets = []
        if fvg_target and fvg_target > curr_price:
            targets.append(fvg_target)
            confluence_factors.append("FVG Imbalance Consequent Encroachment")
        if npoc_price and npoc_price > curr_price:
            targets.append(round(float(npoc_price), 5))
            confluence_factors.append("Naked Point of Control (nPOC) Magnet")
        if recent_highs > curr_price:
            targets.append(recent_highs)
            confluence_factors.append("Buy-Side Liquidity (BSL) Sweep")
            
        if htf_trend == "BULLISH":
            confluence_factors.append("Higher Timeframe (15m/5m) Trend Alignment")
            confidence += 5

        if targets:
            min_target = min(targets)
            predicted_target = round(min(min_target, curr_price + (atr * 0.7), 5), 5)
            confidence += len(confluence_factors) * 4
        else:
            predicted_target = round(curr_price + (atr * 0.4), 5)
            confluence_factors.append("Bullish Momentum & Order Flow Continuation")

    # Bearish Logic (Strictly aligned with Higher Timeframe Bearish Trend)
    elif htf_trend != "BULLISH":
        direction = "BEARISH 🔴"
        targets = []
        if fvg_target and fvg_target < curr_price:
            targets.append(fvg_target)
            confluence_factors.append("Fair Value Gap Rebalance Zone")
        if npoc_price and npoc_price < curr_price:
            targets.append(round(float(npoc_price), 5))
            confluence_factors.append("Naked POC Magnet Reversion")
        if recent_lows < curr_price:
            targets.append(recent_lows)
            confluence_factors.append("Sell-Side Liquidity (SSL) Clear")

        if htf_trend == "BEARISH":
            confluence_factors.append("Higher Timeframe (15m/5m) Trend Alignment")
            confidence += 5

        if targets:
            max_target = max(targets)
            predicted_target = round(max(max_target, curr_price - (atr * 0.7), 5), 5)
            confidence += len(confluence_factors) * 4
        else:
            predicted_target = round(curr_price - (atr * 0.4), 5)
            confluence_factors.append("Bearish Momentum & Institutional Push")
    else:
        return None

    clean_pair = symbol.replace("=X", "")
    
    return {
        "pair": clean_pair,
        "current_price": curr_price,
        "predicted_target": predicted_target,
        "direction": direction,
        "confidence": min(confidence, 96),
        "confluences": confluence_factors
    }
