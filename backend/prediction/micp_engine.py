from features.micp_features import MICPFeatureEngine

class MICPPredictionEngine:
    def __init__(self):
        self.feature_engine = MICPFeatureEngine()

    def predict_next_candle(self, df):
        """
        Wrapper method to evaluate candles and return direction, confidence, and exp_close.
        """
        # Extract closes, highs, lows from dataframe or raw candles format
        closes, highs, lows = self.feature_engine.process_features(df)
        
        if not closes or len(closes) < 10:
            return "NO TRADE", 0.0, 0.0

        # Run MICP-90 evaluation logic
        direction, reason = self.evaluate_micp_90_signal(
            {"M1": "BULLISH", "M5": "BULLISH", "M15": "BULLISH", "M30": "BULLISH", "H1": "BULLISH"}, 
            closes, highs, lows
        )
        
        confidence = 0.90 if direction != "NO TRADE" else 0.50
        exp_close = closes[-1] if closes else 0.0
        
        return direction, confidence, exp_close

    def evaluate_micp_90_signal(self, tf_data, closes, highs, lows):
        # 1. Multi-timeframe agreement strength check
        bullish_count = sum(1 for t in tf_data.values() if t == "BULLISH")
        bearish_count = sum(1 for t in tf_data.values() if t == "BEARISH")
        
        if bullish_count < 4 and bearish_count < 4:
            return "NO TRADE", "Weak MTF Confluence"

        base_dir = "CALL" if bullish_count >= 4 else "PUT"

        # 2. Market Regime & Hurst Filter
        hurst = self.feature_engine.calculate_hurst(closes)
        if hurst < 0.5:
            return "NO TRADE", "Sideways/Choppy Market (Hurst < 0.5)"

        # 3. Support/Resistance & Price Boundary Check
        support, resistance = self.feature_engine.get_sr_ranges(highs, lows)
        current_price = closes[-1]
        
        if base_dir == "CALL" and current_price >= resistance:
            return "NO TRADE", "At Resistance Zone"
        if base_dir == "PUT" and current_price <= support:
            return "NO TRADE", "At Support Zone"

        # 4. Candle Behavior (Body-to-Wick Ratio)
        body = abs(closes[-1] - closes[-2]) if len(closes) >= 2 else 0.0
        total_range = highs[-1] - lows[-1] if highs and lows else 0.0
        if total_range > 0 and (body / total_range) < 0.60:
            return "NO TRADE", "Weak Candle Momentum / High Wicks"

        return base_dir, "VALIDATED HIGH-CONFIDENCE SIGNAL"
