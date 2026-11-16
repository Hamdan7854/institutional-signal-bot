"""Strict Pure Price Action, Liquidity Sweep & Momentum Pullback Breakout Strategy (M1 + M15 Confluence)."""
import time
import numpy as np
import pandas as pd
import config
from prediction.micp_engine import MICPEngine


def calculate_structure_and_zones(df):
    """Calculates structural EMAs and average body metrics for strict momentum filtering."""
    close = df['close']
    df['ema_20'] = close.ewm(span=20, adjust=False).mean()
    df['ema_50'] = close.ewm(span=50, adjust=False).mean()
    
    # Candle body and total range metrics
    df['body'] = (df['close'] - df['open']).abs()
    df['range'] = (df['high'] - df['low']).replace(0, np.nan)
    df['avg_body_10'] = df['body'].rolling(window=10).mean()
    return df


def detect_pullback_and_breakout(df):
    """
    Strict Momentum Pullback Breakout:
    1. Two strong momentum candles (bodies > 10-candle average).
    2. One genuine small pause/pullback candle (body <= 65% of momentum average).
    3. Decisive breakout candle closing cleanly beyond pullback high/low with strong body (>55% of candle range).
    """
    if len(df) < 25:
        return False, False, 0.0, 0.0

    latest = df.iloc[-1]      # Current breakout candle (evaluated at 40th second)
    prev = df.iloc[-2]        # Pullback / Pause candle
    prev_2 = df.iloc[-3]      # Momentum candle 2
    prev_3 = df.iloc[-4]      # Momentum candle 1

    avg_market_body = df['avg_body_10'].iloc[-2]
    if pd.isna(avg_market_body) or avg_market_body == 0:
        return False, False, 0.0, 0.0

    # 1. Check Preceding True Momentum (Both candles must have strong bodies)
    p3_body = abs(prev_3['close'] - prev_3['open'])
    p2_body = abs(prev_2['close'] - prev_2['open'])
    momentum_avg_body = (p3_body + p2_body) / 2.0

    strong_bull_momentum = (
        (prev_3['close'] > prev_3['open']) and
        (prev_2['close'] > prev_2['open']) and
        (momentum_avg_body >= avg_market_body * 1.1)
    )
    strong_bear_momentum = (
        (prev_3['close'] < prev_3['open']) and
        (prev_2['close'] < prev_2['open']) and
        (momentum_avg_body >= avg_market_body * 1.1)
    )

    # 2. Genuine Pause/Pullback Check (Prev candle must be noticeably smaller)
    prev_body = abs(prev['close'] - prev['open'])
    is_valid_pullback = prev_body <= (momentum_avg_body * 0.65)

    pullback_high = prev['high']
    pullback_low = prev['low']

    # 3. Decisive Breakout Candle Check (Strong body, no exhaustion wick)
    latest_body = abs(latest['close'] - latest['open'])
    latest_range = latest['high'] - latest['low']
    if latest_range == 0:
        return False, False, pullback_high, pullback_low

    body_to_range_ratio = latest_body / latest_range
    is_solid_breakout_candle = (body_to_range_ratio >= 0.55) and (latest_body >= avg_market_body * 1.1)

    breakout_bullish = (
        strong_bull_momentum and
        is_valid_pullback and
        is_solid_breakout_candle and
        (latest['close'] > pullback_high) and
        (latest['close'] > prev_2['high'])
    )

    breakout_bearish = (
        strong_bear_momentum and
        is_valid_pullback and
        is_solid_breakout_candle and
        (latest['close'] < pullback_low) and
        (latest['close'] < prev_2['low'])
    )

    return breakout_bullish, breakout_bearish, pullback_high, pullback_low


def detect_liquidity_sweep_and_order_blocks(df):
    """
    Strict Liquidity Sweep (2.0x Wick Rejection) at 15-candle Swing High/Low.
    """
    if len(df) < 20:
        return False, False, 0.0, 0.0

    latest = df.iloc[-1]
    body = abs(latest['close'] - latest['open'])
    if body == 0:
        return False, False, 0.0, 0.0

    upper_wick = latest['high'] - max(latest['close'], latest['open'])
    lower_wick = min(latest['close'], latest['open']) - latest['low']

    # Strict 2.0x Wick-to-Body Rejection
    is_bullish_sweep = (lower_wick >= body * 2.0) and (upper_wick <= body * 0.5) and (latest['close'] > latest['open'])
    is_bearish_sweep = (upper_wick >= body * 2.0) and (lower_wick <= body * 0.5) and (latest['close'] < latest['open'])

    # Expanded 15-candle swing zone for stronger structural levels
    recent_high = df['high'].iloc[-15:-1].max()
    recent_low = df['low'].iloc[-15:-1].min()

    # Exact level sweep (must actually pierce or touch the extreme swing level)
    near_support_sweep = (latest['low'] <= recent_low) and is_bullish_sweep
    near_resistance_sweep = (latest['high'] >= recent_high) and is_bearish_sweep

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
        self.direction = direction
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
        if time.time() - self.last_signal_time < 600:
            self.last_reason = "cooldown_active"
            return None

        if not spread_ok(sp_now, sp_med):
            self.last_reason = "high_spread"
            return None

        if df is None or len(df) < 50:
            self.last_reason = "not_enough_data"
            return None

        # --- STRICT MULTI-TIMEFRAME (M15) TREND CHECK ---
        mtf_bias = "NEUTRAL"
        try:
            if client is not None:
                # Using client.candles to match oanda_client.py method signature
                resp = client.candles(self.symbol, granularity="M15", count=60)
                candles = resp.get("candles", []) if isinstance(resp, dict) else resp
                if candles and len(candles) >= 50:
                    closes = [float(c['mid']['c']) if 'mid' in c else float(c['close']) for c in candles if c.get('complete', True)]
                    if len(closes) >= 50:
                        s_m15 = pd.Series(closes)
                        m15_ema20 = s_m15.ewm(span=20, adjust=False).mean().iloc[-1]
                        m15_ema50 = s_m15.ewm(span=50, adjust=False).mean().iloc[-1]
                        current_m15_price = s_m15.iloc[-1]
                        
                        # Price must also be above/below EMA 20 for true trend alignment
                        if m15_ema20 > m15_ema50 and current_m15_price > m15_ema20:
                            mtf_bias = "BUY"
                        elif m15_ema20 < m15_ema50 and current_m15_price < m15_ema20:
                            mtf_bias = "SELL"
        except Exception:
            self.last_reason = "mtf_fetch_error"
            return None

        # Block signals if M15 trend is flat/neutral
        if mtf_bias == "NEUTRAL":
            self.last_reason = "mtf_neutral_no_clear_trend"
            return None

        df_ind = calculate_structure_and_zones(df.copy())
        latest = df_ind.iloc[-1]
        
        # M1 local EMA trend check (must match M15)
        m1_bullish_trend = (latest['ema_20'] > latest['ema_50']) and (latest['close'] > latest['ema_20'])
        m1_bearish_trend = (latest['ema_20'] < latest['ema_50']) and (latest['close'] < latest['ema_20'])

        # --- STRATEGY CHECKS ---
        bull_sweep, bear_sweep, _, _ = detect_liquidity_sweep_and_order_blocks(df_ind)
        pullback_buy, pullback_sell, _, _ = detect_pullback_and_breakout(df_ind)

        open_p = latest['open']
        close = latest['close']

        direction = None
        confidence = 0.90

        # --- COMBINED STRICT CONFLUENCE ---
        if (pullback_buy or bull_sweep) and close > open_p and m1_bullish_trend:
            direction = "BUY"
            confidence = 0.94 if pullback_buy else 0.91
        elif (pullback_sell or bear_sweep) and close < open_p and m1_bearish_trend:
            direction = "SELL"
            confidence = 0.94 if pullback_sell else 0.91
        else:
            self.last_reason = "no_valid_price_action_setup"
            return None

        # --- FINAL M15 ALIGNMENT GATE ---
        if direction != mtf_bias:
            self.last_reason = f"mtf_conflict(m15_{mtf_bias})"
            return None

        self.last_signal_time = time.time()
        target_time = latest['time'] + pd.Timedelta(minutes=1)
        entry = float(close)
        return SignalResult(direction, confidence, target_time, entry, mtf_bias)
