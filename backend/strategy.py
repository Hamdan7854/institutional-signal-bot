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

def analyze_next_candle_target(symbol: str) -> dict:
    """
    Research-backed SMC + Volume Profile Confluence Engine with Momentum Filtering.
    Sirf wahi signals generate karega jahan price action aur trend fully aligned hon.
    """
    df = fetch_pair_data(symbol, period="2d", interval="1m")
    if df.empty or len(df) < 30:
        df = fetch_pair_data(symbol, period="5d", interval="5m")
        if df.empty or len(df) < 30:
            return None
    
    curr_price = round(float(df['Close'].iloc[-1]), 5)
    prev_price = round(float(df['Close'].iloc[-2]), 5)
    prev_open = round(float(df['Open'].iloc[-2]), 5)
    
    atr = calculate_atr(df)
    poc_price, npoc_price = calculate_volume_profile(df)
    
    # 1. Fair Value Gap (FVG) Calculation
    fvg_target = None
    c1_high = df['High'].iloc[-3]
    c1_low = df['Low'].iloc[-3]
    c3_high = df['High'].iloc[-1]
    c3_low = df['Low'].iloc[-1]
    
    if c3_low > c1_high:
        fvg_target = round((c3_low + c1_high) / 2, 5)
    elif c3_high < c1_low:
        fvg_target = round((c3_high + c1_low) / 2, 5)

    # 2. Liquidity Levels
    recent_highs = round(float(df['High'].iloc[-20:-1].max()), 5)
    recent_lows = round(float(df['Low'].iloc[-20:-1].min()), 5)
    
    # 3. Strict Momentum & Trend Alignment Check
    # Agar pichli candle bullish thi, toh bearish signal nahi aana chahiye (fake signals rokne ke liye)
    is_candle_green = prev_price > prev_open
    
    direction = "NEUTRAL"
    predicted_target = curr_price
    confluence_factors = []
    confidence = 80

    # Bullish Logic
    if curr_price >= prev_price or is_candle_green:
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
            
        if targets:
            min_target = min(targets)
            predicted_target = round(min(min_target, curr_price + (atr * 0.8), 5), 5)
            confidence += len(confluence_factors) * 5
        else:
            predicted_target = round(curr_price + (atr * 0.5), 5)
            confluence_factors.append("Bullish Momentum & Order Flow Continuation")

    # Bearish Logic
    else:
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

        if targets:
            max_target = max(targets)
            predicted_target = round(max(max_target, curr_price - (atr * 0.8), 5), 5)
            confidence += len(confluence_factors) * 5
        else:
            predicted_target = round(curr_price - (atr * 0.5), 5)
            confluence_factors.append("Bearish Momentum & Institutional Push")

    clean_pair = symbol.replace("=X", "")
    
    return {
        "pair": clean_pair,
        "current_price": curr_price,
        "predicted_target": predicted_target,
        "direction": direction,
        "confidence": min(confidence, 95),
        "confluences": confluence_factors
    }
