from backend.features.micp_features import calculate_kama, calculate_hurst, get_sr_ranges

def evaluate_micp_90_signal(tf_data, closes, highs, lows):
    # 1. Multi-timeframe agreement strength check
    bullish_count = sum(1 for t in tf_data.values() if t == "BULLISH")
    bearish_count = sum(1 for t in tf_data.values() if t == "BEARISH")
    
    if bullish_count < 4 and bearish_count < 4:
        return "NO TRADE", "Weak MTF Confluence"

    base_dir = "CALL" if bullish_count >= 4 else "PUT"

    # 2. Market Regime & Hurst Filter
    hurst = calculate_hurst(closes)
    if hurst < 0.5:
        return "NO TRADE", "Sideways/Choppy Market (Hurst < 0.5)"

    # 3. Support/Resistance & Price Boundary Check
    support, resistance = get_sr_ranges(highs, lows)
    current_price = closes[-1]
    
    if base_dir == "CALL" and current_price >= resistance:
        return "NO TRADE", "At Resistance Zone"
    if base_dir == "PUT" and current_price <= support:
        return "NO TRADE", "At Support Zone"

    # 4. Candle Behavior (Body-to-Wick Ratio)
    # Assume latest candle stats
    body = abs(closes[-1] - closes[-2])
    total_range = highs[-1] - lows[-1]
    if total_range > 0 and (body / total_range) < 0.60:
        return "NO TRADE", "Weak Candle Momentum / High Wicks"

    return base_dir, "VALIDATED HIGH-CONFIDENCE SIGNAL"
