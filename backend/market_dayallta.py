import logging
import yfinance as yf

class MarketAnalyzer:
    @staticmethod
    def get_multi_platform_confirmation(symbol="^GSPC"):
        """
        Confirms market direction across external platforms (e.g., Yahoo Finance).
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d", interval="1h")
            if hist.empty:
                return "NEUTRAL", 0.0
            
            close_prices = hist['Close'].tolist()
            if len(close_prices) >= 2:
                diff = close_prices[-1] - close_prices[-2]
                trend = "BULLISH" if diff > 0 else "BEARISH"
                confidence = abs(diff) / close_prices[-2] * 100
                return trend, round(confidence, 2)
        except Exception as e:
            logging.error(f"Multi-platform confirmation error: {str(e)}")
        
        return "NEUTRAL", 0.0
