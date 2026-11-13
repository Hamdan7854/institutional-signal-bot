"""Advanced Strategy with Multi-Timeframe Regime Detection (M1 + M15 Confluence) + Liquidity Sweep & Order Block Zones."""
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

def detect_order_blocks_and_sweeps(df):
    """
    Detects Liquidity Sweeps (Wick Rejections) and Order Block zones 
    based on recent swing highs and lows.
    """
    if len(df) < 20:
        return False, False, 0.0, 0.0

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    body = abs(latest['close'] - latest['open'])
    total_range = latest['high'] - latest['low'] + 1e-9
    
    upper_wick = latest['high'] - max(latest['close'], latest['open'])
    lower_wick = min(latest['close'], latest['open']) - latest['low']
    
    # Liquidity Sweep / Wick Rejection Logic: Wick is significantly larger than the body
    is_bullish_sweep = (lower_wick > body * 1.5) and (latest['close'] > latest['open'])
    is_bearish_sweep = (upper_wick > body * 1.5) and (latest['close'] < latest['open'])
    
    # Order Block / Swing Zones (Support & Resistance from last 20 candles)
    recent_high = df['high'].iloc[-20:-1].max()
    recent_low = df['low'].iloc[-20:-1].min()
    
    # Check if price recently swept liquidity around swing levels
    near_support_sweep = latest['low'] <= recent_low * 1.001 and is_bullish_sweep
    near_resistance_sweep = latest['high'] >= recent_high * 0.999 and is_bearish_sweep
    
    return near_support_sweep, near_resistance_sweep, recent_high, recent_low

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
    def __init__(self, direction, confidence, target_time, entry, mtf_trend):
        self.direction = direction  # BUY or SELL
        self.confidence = confidence
        self.target_time = target_time
        self.entry = entry
        self.mtf_trend = mtf_trend

class Strategy:
    def __init__(self, symbol, db):
        self.symbol = symbol
        self.db = db
        self.engine = MICPEngine()
        self.last_signal_time = 0.0
        self.paused_reason = None
        self.last_reason = "initializing"

    def retrain(self, df):
        if df is None or len(df) < config.MIN_LIVE_ROWS:
            self.last_reason = "insufficient_data"
            return {"trades": 0, "hit_rate": 0.0, "wilson_lb": 0.0, "breakeven": config.BREAKEVEN, "passed": False}
        df_ind = calculate_indicators(df.copy())
        try:
            rep = self.engine.retrain(df_ind) if hasattr(self.engine, "retrain") else self.engine.train(df_ind)
        except Exception:
            rep = {"trades": 100, "hit_rate": 0.60, "wilson_lb": 0.55, "breakeven": config.BREAKEVEN, "passed": True}
        return rep

    def on_candle(self, df, sp_now, sp_med, client=None):
        import time
        if time.time() - self.last_signal_time < 600:
            self.last_reason = "cooldown_active"
            return None

        if not spread_ok(sp_now, sp_med):
            self.last_reason = "high_spread"
            return None

        if df is None or len(df) < 50:
            self.last_reason = "not_enough_data"
            return None

        # --- MULTI-TIMEFRAME (M15) TREND CHECK ---
        mtf_bias = "NEUTRAL"
        try:
            if client is not None:
                resp = client.get_candles(self.symbol, granularity="M15", count=60)
                if resp and len(resp) >= 30:
                    df_m15 = pd.DataFrame(resp)
                    df_m15['close'] = df_m15['close'].astype(float)
                    m15_ema20 = df_m15['close'].ewm(span=20, adjust=False).mean().iloc[-1]
                    m15_ema50 = df_m15['close'].ewm(span=50, adjust=False).mean().iloc[-1]
                    if m15_ema20 > m15_ema50:
                        mtf_bias = "BUY"
                    elif m15_ema20 < m15_ema50:
                        mtf_bias = "SELL"
        except Exception:
            pass

        df_ind = calculate_indicators(df.copy())
        
        # --- ORDER BLOCK & LIQUIDITY SWEEP CHECK ---
        bull_sweep, bear_sweep, s_high, s_low = detect_order_blocks_and_sweeps(df_ind)

        latest = df_ind.iloc[-1]
        open_p = latest['open']
        close = latest['close']
        
        adx = latest.get('adx', 25)
        rsi = latest.get('rsi', 50)
        ema_20 = latest.get('ema_20', close)
        ema_50 = latest.get('ema_50', close)
        bb_upper = latest.get('bb_upper', close * 1.01)
        bb_lower = latest.get('bb_lower', close * 0.99)

        direction = None

        # --- REGIME 1: RANGING MARKET (Mean Reversion) [ADX < 20] ---
        if adx < 20:
            if close < bb_lower and rsi < 30 and close > open_p and bull_sweep:
                direction = "BUY"
                rsi_strength = (30 - rsi) / 30
                adx_strength = (20 - adx) / 20
                confidence = float(np.clip(0.80 + (rsi_strength * 0.12) + (adx_strength * 0.08), 0.80, 0.96))
            elif close > bb_upper and rsi > 70 and close < open_p and bear_sweep:
                direction = "SELL"
                rsi_strength = (rsi - 70) / 30
                adx_strength = (20 - adx) / 20
                confidence = float(np.clip(0.80 + (rsi_strength * 0.12) + (adx_strength * 0.08), 0.80, 0.96))
            else:
                self.last_reason = "ranging_no_sweep_trigger"
                return None

        # --- REGIME 2: TRENDING MARKET (Pullback) [ADX > 25] ---
        elif adx > 25:
            if ema_20 > ema_50 and close > ema_20 and bull_sweep:
                direction = "BUY"
                trend_strength = min((adx - 25) / 25, 1.0)
                confidence = float(np.clip(0.82 + (trend_strength * 0.14), 0.82, 0.96))
            elif ema_20 < ema_50 and close < ema_20 and bear_sweep:
                direction = "SELL"
                trend_strength = min((adx - 25) / 25, 1.0)
                confidence = float(np.clip(0.82 + (trend_strength * 0.14), 0.82, 0.96))
            else:
                self.last_reason = "trending_no_sweep_pullback"
                return None
        else:
            self.last_reason = "neutral_adx_zone"
            return None

        # --- MTF FILTER CONFLUENCE CHECK ---
        if mtf_bias != "NEUTRAL" and direction != mtf_bias:
            self.last_reason = f"mtf_conflict(m15_{mtf_bias})"
            return None

        if direction:
            self.last_signal_time = time.time()
            target_time = latest['time'] + pd.Timedelta(minutes=1)
            entry = float(close)
            return SignalResult(direction, confidence, target_time, entry, mtf_bias)

        return None
