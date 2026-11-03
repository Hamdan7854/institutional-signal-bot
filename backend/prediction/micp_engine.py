import pandas as pd

class MICPPredictionEngine:
    @staticmethod
    def predict_next_candle(df: pd.DataFrame):
        if df is None or len(df) < 5:
            return "NEUTRAL", 0.0, 0.0

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        close = latest['close']
        sma = latest['sma_20']
        rsi = latest['rsi']
        atr = latest['atr']

        # Quantitative Multi-Factor Logic for MICP-60
        bullish_score = 0
        bearish_score = 0

        if close > sma:
            bullish_score += 0.4
        else:
            bearish_score += 0.4

        if rsi < 45:
            bullish_score += 0.4  # Oversold bounce potential
        elif rsi > 55:
            bearish_score += 0.4  # Overbought pullback potential

        if latest['close'] > prev['close']:
            bullish_score += 0.2
        else:
            bearish_score += 0.2

        if bullish_score > bearish_score:
            direction = "BULLISH 🚀"
            confidence = round(min(bullish_score, 0.95), 2)
            expected_close = round(close + (atr * 0.3), 5)
        else:
            direction = "BEARISH 📉"
            confidence = round(min(bearish_score, 0.95), 2)
            expected_close = round(close - (atr * 0.3), 5)

        return direction, confidence, expected_close
