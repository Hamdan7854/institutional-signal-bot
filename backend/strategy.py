from market_dayallta import MarketAnalyzer

class TradingStrategy:
    @staticmethod
    def calculate_sma(price_history, period):
        if len(price_history) < period:
            return None
        return sum(price_history[-period:]) / period

    @classmethod
    def evaluate_signal(cls, price_history, fast_period, slow_period):
        if len(price_history) < slow_period + 1:
            return "HOLD", "Insufficient price history for analysis."

        sma_fast = cls.calculate_sma(price_history, fast_period)
        sma_slow = cls.calculate_sma(price_history, slow_period)
        
        prev_fast = cls.calculate_sma(price_history[:-1], fast_period)
        prev_slow = cls.calculate_sma(price_history[:-1], slow_period)

        if not (sma_fast and sma_slow and prev_fast and prev_slow):
            return "HOLD", "Calculating indicators..."

        ext_trend, ext_conf = MarketAnalyzer.get_multi_platform_confirmation()

        signal = "HOLD"
        reason = "No crossover detected."

        if prev_fast <= prev_slow and sma_fast > sma_slow:
            signal = "CALL (BUY)"
            reason = f"Bullish Crossover (Fast: {sma_fast:.2f} > Slow: {sma_slow:.2f}). External Trend: {ext_trend}"
        elif prev_fast >= prev_slow and sma_fast < sma_slow:
            signal = "PUT (SELL)"
            reason = f"Bearish Crossover (Fast: {sma_fast:.2f} < Slow: {sma_slow:.2f}). External Trend: {ext_trend}"

        return signal, reason
