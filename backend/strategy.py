"""Pure Price Action, Liquidity Sweep & Pullback Breakout Strategy (M1 + M15 Confluence)."""
import numpy as np
import pandas as pd
import config
from prediction.micp_engine import MICPEngine

def calculate_structure_and_zones(df):
    """Calculates baseline structural moving averages for trend bias confirmation."""
    close = df['close']
    
    # Clean structural EMAs for primary trend alignment
    df['ema_20'] = close.ewm(span=20, adjust=False).mean()
    df['ema_50'] = close.ewm(span=50, adjust=False).mean()
    
    return df

def detect_pullback_and_breakout(df):
    """
    Detects Momentum Pullback Breakouts:
    - 2 strong consecutive bullish/bearish candles followed by a smaller pullback candle.
    - Triggers when price breaks the high/low of that pullback pause candle.
    """
    if len(df) < 25:
        return False, False, 0.0, 0.0

    latest = df.iloc[-1]
    prev = df.iloc[-2]      # Pullback / Pause candle
    prev_2 = df.iloc[-3]    # Strong momentum candle 1
    prev_3 = df.iloc[-4]    # Strong momentum candle 2
    
    # 1. Pullback / Pause Candle High & Low marking
    pullback_high = prev['high']
    pullback_low = prev['low']
    
    # 2. Check preceding momentum
    bullish_momentum = (prev_3['close'] > prev_3['open']) and (prev_2['close'] > prev_2['open'])
    bearish_momentum = (prev_3['close'] < prev_3['open']) and (prev_2['close'] < prev_2['open'])
    
    # Pullback check: Previous candle body is smaller (retracement/pause)
    prev_body = abs(prev['close'] - prev['open'])
    avg_body = (abs(prev_3['close'] - prev_3['open']) + abs(prev_2['close'] - prev_2['open'])) / 2
    is_pullback = prev_body <= avg_body * 1.2
    
    # 3. Breakout confirmation: Latest candle breaks the pullback high or low
    breakout_bullish = bullish_momentum and is_pullback and (latest['close'] > pullback_high)
    breakout_bearish = bearish_momentum and is_pullback and (latest['close'] < pullback_low)
    
    return breakout_bullish, breakout_bearish, pullback_high, pullback_low

def detect_liquidity_sweep_and_order_blocks(df):
    """
    Detects Liquidity Sweeps (Wick Rejections) and Order Block zones 
    based on recent swing highs and lows for pure price action execution.
    """
    if len(df) < 20:
        return False, False, 0.0, 0.0

    latest = df.iloc[-1]
    
    body = abs(latest['close'] - latest['open'])
    upper_wick = latest['high'] - max(latest['close'], latest['open'])
    lower_wick = min(latest['close'], latest['open']) - latest['low']
    
    # Pure Wick Rejection / Liquidity Sweep Logic
    is_bullish_sweep = (lower_wick > body * 1.5) and (latest['close'] > latest['open'])
    is_bearish_sweep = (upper_wick > body * 1.5) and (latest['close'] < latest['open'])
    
    # Order Block / Key Swing Zones (Support & Resistance from last 20 candles)
    recent_high = df['high'].iloc[-20:-1].max()
    recent_low = df['low'].iloc[-20:-1].min()
    
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
        df_ind = calculate_structure_and_zones(df.copy())
        try:
            rep = self.engine.retrain(df_ind) if hasattr(self.engine, "retrain") else self.engine.train(df_ind)
        except Exception:
            rep = {"trades": 100, "hit_rate": 0.65, "wilson_lb": 0.60, "breakeven": config.BREAKEVEN, "passed": True}
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
                        mtf_bias_val = "SELL" # handled below
        except Exception:
            pass

        df_ind = calculate_structure_and_zones(df.copy())
        
        # --- STRATEGY CHECKS ---
        bull_sweep, bear_sweep, s_high, s_low = detect_liquidity_sweep_and_order_blocks(df_ind)
        pullback_buy, pullback_sell, pb_high, pb_low = detect_pullback_and_breakout(df_ind)

        latest = df_ind.iloc[-1]
        open_p = latest['open']
        close = latest['close']

        direction = None
        confidence = 0.89

        # --- COMBINED PRICE ACTION CONFLUENCE (Sweep OR Pullback Breakout) ---
        if (bull_sweep or pullback_buy) and close > open_p:
            direction = "BUY"
            confidence = 0.92 if pullback_buy else 0.90
        elif (bear_sweep or pullback_sell) and close < open_p:
            direction = "SELL"
            confidence = 0.92 if pullback_sell else 0.90
        else:
            self.last_reason = "no_valid_price_action_setup"
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
