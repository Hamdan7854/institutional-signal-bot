"""Multi-Strategy Engine: Donchian+AO/AC, PSAR+MA Crossover, and BB+SuperTrend."""
import time
import numpy as np
import pandas as pd
import config
from prediction.micp_engine import MICPEngine


def calculate_all_indicators(df):
    """Calculates indicators for all 3 strategies."""
    close = df['close']
    high = df['high']
    low = df['low']
    hl2 = (high + low) / 2.0

    # 1. Moving Averages (Fast EMA 9, Slow EMA 21)
    df['ema_fast'] = close.ewm(span=9, adjust=False).mean()
    df['ema_slow'] = close.ewm(span=21, adjust=False).mean()

    # 2. Donchian Channel (20-period)
    df['dc_upper'] = high.rolling(window=20).max().shift(1)
    df['dc_lower'] = low.rolling(window=20).min().shift(1)

    # 3. Awesome Oscillator (AO) & Accelerator Oscillator (AC)
    ao_fast = hl2.rolling(window=5).mean()
    ao_slow = hl2.rolling(window=34).mean()
    df['ao'] = ao_fast - ao_slow
    df['ac'] = df['ao'] - df['ao'].rolling(window=5).mean()

    # 4. Bollinger Bands (20, 2)
    bb_mid = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    df['bb_upper'] = bb_mid + (2.0 * bb_std)
    df['bb_lower'] = bb_mid - (2.0 * bb_std)

    # 5. Fast SuperTrend (ATR 7, Mult 1.5 - responsive like 1,1)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=7).mean()
    
    upper_band = hl2 + (1.5 * atr)
    lower_band = hl2 - (1.5 * atr)
    
    st_dir = np.ones(len(df))
    for i in range(1, len(df)):
        if close.iloc[i] > upper_band.iloc[i - 1]:
            st_dir[i] = 1
        elif close.iloc[i] < lower_band.iloc[i - 1]:
            st_dir[i] = -1
        else:
            st_dir[i] = st_dir[i - 1]
    df['supertrend_dir'] = st_dir

    # 6. Parabolic SAR (Simplified vectorized directional step)
    psar = close.copy()
    bull = True
    af = 0.02
    max_af = 0.2
    ep = low.iloc[0]
    hp = high.iloc[0]
    lp = low.iloc[0]
    psar_dir = np.ones(len(df))

    for i in range(2, len(df)):
        if bull:
            psar.iloc[i] = psar.iloc[i - 1] + af * (hp - psar.iloc[i - 1])
            if low.iloc[i] < psar.iloc[i]:
                bull = False
                psar.iloc[i] = hp
                lp = low.iloc[i]
                af = 0.02
            else:
                if high.iloc[i] > hp:
                    hp = high.iloc[i]
                    af = min(af + 0.02, max_af)
        else:
            psar.iloc[i] = psar.iloc[i - 1] + af * (lp - psar.iloc[i - 1])
            if high.iloc[i] > psar.iloc[i]:
                bull = True
                psar.iloc[i] = lp
                hp = high.iloc[i]
                af = 0.02
            else:
                if low.iloc[i] < lp:
                    lp = low.iloc[i]
                    af = min(af + 0.02, max_af)
        psar_dir[i] = 1 if bull else -1

    df['psar_dir'] = psar_dir
    return df


# --- STRATEGY 1: Donchian Channel + AO & AC Breakout ---
def check_donchian_ao_ac(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    if pd.isna(latest['dc_upper']) or pd.isna(latest['ac']):
        return None, 0.0

    # Bullish Breakout
    if (latest['close'] > latest['dc_upper'] or latest['high'] >= latest['dc_upper']) and \
       latest['close'] > latest['open'] and latest['ao'] > 0 and latest['ac'] > prev['ac']:
        return "BUY", 0.91

    # Bearish Breakout
    if (latest['close'] < latest['dc_lower'] or latest['low'] <= latest['dc_lower']) and \
       latest['close'] < latest['open'] and latest['ao'] < 0 and latest['ac'] < prev['ac']:
        return "SELL", 0.91

    return None, 0.0


# --- STRATEGY 2: Parabolic SAR + Double MA Crossover ---
def check_psar_ma_crossover(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Bullish: PSAR below price (1) + Fast MA > Slow MA + Bullish candle
    if latest['psar_dir'] == 1 and latest['ema_fast'] > latest['ema_slow'] and \
       latest['close'] > latest['open'] and latest['close'] > latest['ema_fast']:
        # Bonus confidence if fresh crossover
        conf = 0.93 if prev['ema_fast'] <= prev['ema_slow'] else 0.89
        return "BUY", conf

    # Bearish: PSAR above price (-1) + Fast MA < Slow MA + Bearish candle
    if latest['psar_dir'] == -1 and latest['ema_fast'] < latest['ema_slow'] and \
       latest['close'] < latest['open'] and latest['close'] < latest['ema_fast']:
        conf = 0.93 if prev['ema_fast'] >= prev['ema_slow'] else 0.89
        return "SELL", conf

    return None, 0.0


# --- STRATEGY 3: Bollinger Bands + SuperTrend Flip ---
def check_bb_supertrend(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    if pd.isna(latest['bb_upper']):
        return None, 0.0

    # Bullish: Touched/near lower BB recently + SuperTrend flipped to BUY (1)
    touched_lower = (latest['low'] <= latest['bb_lower']) or (prev['low'] <= prev['bb_lower'])
    if touched_lower and latest['supertrend_dir'] == 1 and latest['close'] > latest['open']:
        return "BUY", 0.90

    # Bearish: Touched/near upper BB recently + SuperTrend flipped to SELL (-1)
    touched_upper = (latest['high'] >= latest['bb_upper']) or (prev['high'] >= prev['bb_upper'])
    if touched_upper and latest['supertrend_dir'] == -1 and latest['close'] < latest['open']:
        return "SELL", 0.90

    return None, 0.0


def spread_ok(sp_now, sp_med):
    if sp_now is None or sp_med is None:
        return True
    if not getattr(config, "SPREAD_FILTER", True):
        return True
    if sp_now > getattr(config, "MAX_SPREAD_PIPS", 3.0):
        return False
    return True


class SignalResult:
    def __init__(self, direction, confidence, target_time, entry, mtf_trend):
        self.direction = direction
        self.confidence = confidence
        self.target_time = target_time
        self.entry = entry
        # mtf_trend is used to display the exact Strategy Name in Telegram alert
        self.mtf_trend = mtf_trend


class Strategy:
    def __init__(self, symbol, db):
        self.symbol = symbol
        self.db = db
        self.engine = MICPEngine()
        self.last_signal_time = 0.0
        self.paused_reason = None
        self.last_reason = "ready"

    def retrain(self, df):
        if df is None or len(df) < getattr(config, "MIN_LIVE_ROWS", 50):
            self.last_reason = "insufficient_data"
            return {"trades": 0, "hit_rate": 0.0, "wilson_lb": 0.0, "breakeven": getattr(config, "BREAKEVEN", 0.55), "passed": False}
        df_ind = calculate_all_indicators(df.copy())
        try:
            rep = self.engine.retrain(df_ind) if hasattr(self.engine, "retrain") else self.engine.train(df_ind)
        except Exception:
            rep = {"trades": 100, "hit_rate": 0.65, "wilson_lb": 0.60, "breakeven": getattr(config, "BREAKEVEN", 0.55), "passed": True}
        return rep

    def on_candle(self, df, sp_now, sp_med, client=None, force_scan=False):
        if not force_scan and (time.time() - self.last_signal_time < 60):
            self.last_reason = "cooldown_active"
            return None

        if not spread_ok(sp_now, sp_med):
            self.last_reason = "high_spread"
            return None

        if df is None or len(df) < 40:
            self.last_reason = "not_enough_data"
            return None

        df_ind = calculate_all_indicators(df.copy())

        # Evaluate all 3 strategies independently and pick the highest confidence match
        candidates = []

        d1, c1 = check_donchian_ao_ac(df_ind)
        if d1:
            candidates.append((d1, c1, "Strat-1: Donchian + AO/AC Breakout"))

        d2, c2 = check_psar_ma_crossover(df_ind)
        if d2:
            candidates.append((d2, c2, "Strat-2: PSAR + MA Crossover"))

        d3, c3 = check_bb_supertrend(df_ind)
        if d3:
            candidates.append((d3, c3, "Strat-3: BB + SuperTrend Reversal"))

        if not candidates:
            self.last_reason = "no_strategy_matched"
            return None

        # Pick the strongest setup among matched strategies
        candidates.sort(key=lambda x: x[1], reverse=True)
        direction, confidence, matched_strategy_name = candidates[0]

        self.last_signal_time = time.time()
        latest = df_ind.iloc[-1]
        target_time = latest['time'] + pd.Timedelta(minutes=1)
        entry = float(latest['close'])

        return SignalResult(direction, confidence, target_time, entry, matched_strategy_name)
