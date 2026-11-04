from features.micp_features import MICPFeatureEngine

class MICPPredictionEngine:
    def __init__(self):
        self.feature_engine = MICPFeatureEngine()

    @staticmethod
    def predict_next_candle(df):
        """
        Wrapper method to evaluate candles and return direction, confidence, and exp_close.
        """
        feature_engine = MICPFeatureEngine()
        closes, highs, lows = feature_engine.process_features(df)
        
        if not closes or len(closes) < 10:
            return "NO TRADE", 0.0, 0.0

        tf_data = {"M1": "BULLISH", "M5": "BULLISH", "M15": "BULLISH", "M30": "BULLISH", "H1": "BULLISH"}
        bullish_count = sum(1 for t in tf_data.values() if t == "BULLISH")
        bearish_count = sum(1 for t in tf_data.values() if t == "BEARISH")
        
        if bullish_count < 4 and bearish_count < 4:
            return "NO TRADE", 0.50, closes[-1] if closes else 0.0

        base_dir = "CALL" if bullish_count >= 4 else "PUT"

        hurst = feature_engine.calculate_hurst(closes)
        if hurst < 0.5:
            return "NO TRADE", 0.50, closes[-1] if closes else 0.0

        support, resistance = feature_engine.get_sr_ranges(highs, lows)
        current_price = closes[-1] if closes else 0.0
        
        if base_dir == "CALL" and current_price >= resistance:
            return "NO TRADE", 0.50, current_price
        if base_dir == "PUT" and current_price <= support:
            return "NO TRADE", 0.50, current_price

        body = abs(closes[-1] - closes[-2]) if len(closes) >= 2 else 0.0
        total_range = highs[-1] - lows[-1] if highs and lows else 0.0
        if total_range > 0 and (body / total_range) < 0.60:
            return "NO TRADE", 0.50, current_price

        return base_dir, 0.90, current_price
