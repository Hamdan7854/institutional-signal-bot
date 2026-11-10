"""Advanced Strategy with Market Regime Detection (ADX, RSI, Bollinger Bands, EMA Pullback & Mean Reversion)."""
import numpy as np
import pandas as pd
import config
from prediction.micp_engine import MICPEngine

def calculate_indicators(df):
    """Calculates EMA, RSI, Bollinger Bands, and ADX for regime filtering."""
    close = df['close']
    high = df['high']
    low = df['low']
    
    # EMAs
    df['ema_20'] = close.ewm(span=20, adjust=False).mean()
    df['ema_50'] = close.ewm(span=50, adjust=False).mean()
    
    # Bollinger Bands (20, 2)
    sma_20 = close.rolling(window=20).mean()
    std_20 = close.rolling(window=20).std()
    df['bb_upper'] = sma_20 + (std_20 * 2)
    df['bb_lower'] = sma_20 - (std_20 * 2)
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ADX (14 simplified approximation)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean()
    
    up_move = high - high.shift()
    down_move = low.shift() - low
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    pos_di = 100 * pd.Series(pos_dm).rolling(window=14).mean() / (atr + 1e-9)
    neg_di = 100 * pd.Series(neg_dm).rolling(window=14).mean() / (atr + 1e-9)
    dx = 100 * (pos_di - neg_di).abs() / (pos_di + neg_di + 1e-9)
    df['adx'] = dx.rolling(window=14).mean()
    
    return df

def spread_ok(sp_now, sp_med):
    if sp_now is None or sp_med is None:
        return True
    if not config.SPREAD_FILTER:
        return True
    if sp_now > config.MAX_SPREAD_PIPS:
        return False
    if sp_now > sp_med * config.SPREAD_MULT:
        return False
    return True

class SignalResult:
    def __init__(self, direction, confidence, target_time, entry):
        self.direction = direction
        self.confidence = confidence
        self.target_time = target_time
        self.entry = entry

class Strategy:
    def __init__(self, symbol, db):
        self.symbol = symbol
        self.db = db
        self.engine = MICPEngine()
        self.last_signal_time = 0.0  # Cooldown tracking
        self.paused_reason = None
        self.last_reason = "initializing"

    def retrain(self, df):
        if df is None or len(df) < config.MIN_LIVE_ROWS:
            self.last_reason = "insufficient_data"
            return {"trades": 0, "hit_rate": 0.0, "wilson_lb": 0.0, "breakeven": config.BREAKEVEN, "passed": False}
        df_ind = calculate_indicators(df.copy())
        rep = self.engine.train_and_evaluate(df_ind)
        return rep

    def on_candle(self, df, sp_now, sp_med):
        # 1. Cooldown Check (10 minutes = 600 seconds)
        import time
        if time.time() - self.last_signal_time < 600:
            self.last_reason = "cooldown_active"
            return None

        # 2. Spread Filter Check
        if not spread_ok(sp_now, sp_med):
            self.last_reason = "high_spread"
            return None

        if df is None or len(df) < 50:
            self.last_reason = "not_enough_data"
            return None

        df_ind = calculate_indicators(df.copy())
        latest = df_ind.iloc[-1]
        prev = df_ind.iloc[-2]

        adx = latest.get('adx', 25)
        rsi = latest.get('rsi', 50)
        close = latest['close']
        open_p = latest['open']
        ema_20 = latest.get('ema_20', close)
        ema_50 = latest.get('ema_50', close)
        bb_upper = latest.get('bb_upper', close * 1.01)
        bb_lower = latest.get('bb_lower', close * 0.99)

        direction = None
        confidence = 0.75

        # --- REGIME 1: RANGING MARKET (Mean Reversion) [ADX < 20] ---
        if adx < 20:
            # Oversold / Lower BB breakout + Bullish reversal wick/engulfing
            if close < bb_lower and rsi < 30 and close > open_p:
                direction = "CALL"
                confidence = 0.80
            # Overbought / Upper BB breakout + Bearish reversal wick/engulfing
            elif close > bb_upper and rsi > 70 and close < open_p:
                direction = "PUT"
                confidence = 0.80
            else:
                self.last_reason = "ranging_no_trigger"
                return None

        # --- REGIME 2: TRENDING MARKET (Pullback) [ADX > 25] ---
        elif adx > 25:
            # Bullish Trend (EMA 20 > EMA 50) -> Pullback down then resumption up
            if ema_20 > ema_50 and close > ema_20:
                direction = "CALL"
                confidence = 0.82
            # Bearish Trend (EMA 20 < EMA 50) -> Pullback up then resumption down
            elif ema_20 < ema_50 and close < ema_20:
                direction = "PUT"
                confidence = 0.82
            else:
                self.last_reason = "trending_no_pullback"
                return None
        else:
            self.last_reason = "neutral_adx_zone"
            return None

        if direction:
            self.last_signal_time = time.time()
            target_time = latest['time'] + pd.Timedelta(minutes=1)
            entry = close
            return SignalResult(direction, confidence, target_time, entry)

        return None
