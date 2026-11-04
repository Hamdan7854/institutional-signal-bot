import numpy as np

class MICPFeatureEngine:
    def __init__(self):
        pass

    def process_features(self, raw_candles=None):
        """
        Extracts closes, highs, and lows safely from raw candle data.
        """
        if not raw_candles:
            return [], [], []
        closes = [c['close'] for c in raw_candles] if raw_candles else []
        highs = [c['high'] for c in raw_candles] if raw_candles else []
        lows = [c['low'] for c in raw_candles] if raw_candles else []
        return closes, highs, lows

    def calculate_kama(self, prices, period=10, fast_end=2, slow_end=30):
        if len(prices) < period:
            return prices[-1] if len(prices) > 0 else 0.0
        prices = np.array(prices)
        change = np.abs(prices[period:] - prices[:-period])
        volatility = np.sum(np.abs(prices[1:] - prices[:-1]))
        if volatility == 0:
            er = 0.0
        else:
            er = change[-1] / volatility if isinstance(volatility, float) else 0.0
        fast_sc = 2.0 / (fast_end + 1)
        slow_sc = 2.0 / (slow_end + 1)
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        kama = prices[-2] + sc * (prices[-1] - prices[-2])
        return kama

    def calculate_hurst(self, prices, max_lag=20):
        if len(prices) < max_lag * 2:
            return 0.5
        lags = range(2, max_lag)
        tau = [np.sqrt(np.std(np.subtract(prices[lag:], prices[:-lag]))) for lag in lags]
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0

    def get_sr_ranges(self, highs, lows):
        if not highs or not lows:
            return 0.0, 0.0
        resistance = max(highs[-10:]) if len(highs) >= 10 else max(highs)
        support = min(lows[-10:]) if len(lows) >= 10 else min(lows)
        return support, resistance
