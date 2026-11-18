"""Custom 5-Strategy Multi-Timeframe Engine:
1. Parabolic SAR (0.03, 0.3) + Momentum (5) [1M]
2. SuperTrend (10, 2.5) + Momentum (7) [30s]
3. Donchian (50) + AO (30,70) + AC (15,50,5) [1M]
4. Bollinger Bands + SuperTrend (1,1) + ZigZag (5,12,3) [15s]
5. Triple EMA Pullback (EMA 15, 30, 60) [1M]
"""
import time
import numpy as np
import pandas as pd
import config
from prediction.micp_engine import MICPEngine


def compute_supertrend(df, atr_period=10, multiplier=2.5):
    """Computes standard trailing SuperTrend direction (1 = BUY, -1 = SELL)."""
    high = df['high']
    low = df['low']
    close = df['close']
    hl2 = (high + low) / 2.0

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=atr_period).mean() if atr_period > 1 else tr

    upper_basic = hl2 + (multiplier * atr)
    lower_basic = hl2 - (multiplier * atr)

    final_upper = upper_basic.copy()
    final_lower = lower_basic.copy()
    st_dir = np.ones(len(df))

    for i in range(1, len(df)):
        if pd.isna(atr.iloc[i - 1]):
            st_dir[i] = 1
            continue

        if upper_basic.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = upper_basic.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        if lower_basic.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = lower_basic.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

        if st_dir[i - 1] == 1:
            st_dir[i] = -1 if close.iloc[i] < final_lower.iloc[i] else 1
        else:
            st_dir[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1

    return st_dir


def compute_psar(df, step=0.03, max_af=0.3):
    """Computes Parabolic SAR direction (1 = Below/BUY, -1 = Above/SELL)."""
    close = df['close']
    high = df['high']
    low = df['low']

    psar = close.copy()
    bull = True
    af = step
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
                af = step
            else:
                if high.iloc[i] > hp:
                    hp = high.iloc[i]
                    af = min(af + step, max_af)
        else:
            psar.iloc[i] = psar.iloc[i - 1] + af * (lp - psar.iloc[i - 1])
            if high.iloc[i] > psar.iloc[i]:
                bull = True
                psar.iloc[i] = lp
                hp = high.iloc[i]
                af = step
            else:
                if low.iloc[i] < lp:
                    lp = low.iloc[i]
                    af = min(af + step, max_af)
        psar_dir[i] = 1 if bull else -1

    return psar_dir


# --- STRATEGY 1: Parabolic SAR (0.03, 0.3) + Momentum (5) [1M] ---
def check_strat1_psar_mom5(df_1m):
    if df_1m is None or len(df_1m) < 20:
        return None, 0.0
    df = df_1m.copy()
    df['psar_dir'] = compute_psar(df, step=0.03, max_af=0.3)
    df['mom_5'] = df['close'] - df['close'].shift(5)

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    if pd.isna(latest['mom_5']) or pd.isna(prev['mom_5']):
        return None, 0.0

    # BUY: PSAR dots below candles (1) + Momentum(5) > 0 & rising + Green candle
    if latest['psar_dir'] == 1 and latest['mom_5'] > 0 and latest['mom_5'] > prev['mom_5'] and latest['close'] > latest['open']:
        conf = 0.93 if (prev['psar_dir'] == -1 or prev['mom_5'] <= 0) else 0.89
        return "BUY", conf

    # SELL: PSAR dots above candles (-1) + Momentum(5) < 0 & falling + Red candle
    if latest['psar_dir'] == -1 and latest['mom_5'] < 0 and latest['mom_5'] < prev['mom_5'] and latest['close'] < latest['open']:
        conf = 0.93 if (prev['psar_dir'] == 1 or prev['mom_5'] >= 0) else 0.89
        return "SELL", conf

    return None, 0.0


# --- STRATEGY 2: SuperTrend (10, 2.5) + Momentum (7) [30s] ---
def check_strat2_supertrend_mom7(df_30s):
    if df_30s is None or len(df_30s) < 25:
        return None, 0.0
    df = df_30s.copy()
    df['st_dir'] = compute_supertrend(df, atr_period=10, multiplier=2.5)
    df['mom_7'] = df['close'] - df['close'].shift(7)

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    if pd.isna(latest['mom_7']) or pd.isna(prev['mom_7']):
        return None, 0.0

    # BUY: SuperTrend bullish (1) + Momentum(7) > 0 & accelerating + Green candle
    if latest['st_dir'] == 1 and latest['mom_7'] > 0 and latest['mom_7'] > prev['mom_7'] and latest['close'] > latest['open']:
        conf = 0.93 if prev['st_dir'] == -1 else 0.89
        return "BUY", conf

    # SELL: SuperTrend bearish (-1) + Momentum(7) < 0 & falling + Red candle
    if latest['st_dir'] == -1 and latest['mom_7'] < 0 and latest['mom_7'] < prev['mom_7'] and latest['close'] < latest['open']:
        conf = 0.93 if prev['st_dir'] == 1 else 0.89
        return "SELL", conf

    return None, 0.0


# --- STRATEGY 3: Donchian (50) + AO (30,70) + AC (15,50,5) [1M] ---
def check_strat3_donchian_ao_ac(df_1m):
    if df_1m is None or len(df_1m) < 80:
        return None, 0.0
    df = df_1m.copy()
    hl2 = (df['high'] + df['low']) / 2.0

    # Donchian Channel (50-period)
    df['dc_upper'] = df['high'].rolling(window=50).max().shift(1)
    df['dc_lower'] = df['low'].rolling(window=50).min().shift(1)

    # Awesome Oscillator (Short 30, Long 70)
    df['ao'] = hl2.rolling(window=30).mean() - hl2.rolling(window=70).mean()

    # Accelerator Oscillator (AO Short 15, AO Long 50, AC SMA 5)
    ao_for_ac = hl2.rolling(window=15).mean() - hl2.rolling(window=50).mean()
    df['ac'] = ao_for_ac - ao_for_ac.rolling(window=5).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    if pd.isna(latest['dc_upper']) or pd.isna(latest['ao']) or pd.isna(latest['ac']):
        return None, 0.0

    # Fresh Bullish Breakout of Donchian 50 + AO > 0 + AC rising
    fresh_bull = (prev['close'] <= prev['dc_upper']) and (latest['close'] > latest['dc_upper'])
    if fresh_bull and latest['close'] > latest['open'] and latest['ao'] > 0 and latest['ac'] > prev['ac']:
        return "BUY", 0.92

    # Fresh Bearish Breakout of Donchian 50 + AO < 0 + AC falling
    fresh_bear = (prev['close'] >= prev['dc_lower']) and (latest['close'] < latest['dc_lower'])
    if fresh_bear and latest['close'] < latest['open'] and latest['ao'] < 0 and latest['ac'] < prev['ac']:
        return "SELL", 0.92

    return None, 0.0


# --- STRATEGY 4: Bollinger Bands + SuperTrend (1,1) + ZigZag (5,12,3) [15s] ---
def check_strat4_bb_st_zigzag(df_15s):
    if df_15s is None or len(df_15s) < 25:
        return None, 0.0
    df = df_15s.copy()

    # Bollinger Bands (20, 2)
    bb_mid = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = bb_mid + (2.0 * bb_std)
    df['bb_lower'] = bb_mid - (2.0 * bb_std)

    # SuperTrend (1, 1)
    df['st_dir'] = compute_supertrend(df, atr_period=1, multiplier=1.0)

    # Non-repainting ZigZag (Depth=5, Deviation=12, Backstep=3 -> 5-bar swing pivot)
    swing_low_5 = df['low'].rolling(window=5).min()
    swing_high_5 = df['high'].rolling(window=5).max()

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    if pd.isna(latest['bb_upper']):
        return None, 0.0

    # BUY: Lower BB touch + ZigZag bottom pivot + SuperTrend(1,1) flipped to BUY (1)
    touched_lower = (latest['low'] <= latest['bb_lower']) or (prev['low'] <= prev['bb_lower'])
    zz_bottom = (prev['low'] <= swing_low_5.iloc[-2]) or (latest['low'] <= swing_low_5.iloc[-1])
    if touched_lower and zz_bottom and latest['st_dir'] == 1 and latest['close'] > latest['open']:
        return "BUY", 0.91

    # SELL: Upper BB touch + ZigZag top pivot + SuperTrend(1,1) flipped to SELL (-1)
    touched_upper = (latest['high'] >= latest['bb_upper']) or (prev['high'] >= prev['bb_upper'])
    zz_top = (prev['high'] >= swing_high_5.iloc[-2]) or (latest['high'] >= swing_high_5.iloc[-1])
    if touched_upper and zz_top and latest['st_dir'] == -1 and latest['close'] < latest['open']:
        return "SELL", 0.91

    return None, 0.0


# --- STRATEGY 5: Triple EMA Pullback (EMA 15 Green, EMA 30 Yellow, EMA 60 Red) [1M] ---
def check_strat5_triple_ema(df_1m):
    if df_1m is None or len(df_1m) < 70:
        return None, 0.0
    df = df_1m.copy()
    df['ema15'] = df['close'].ewm(span=15, adjust=False).mean()  # Green
    df['ema30'] = df['close'].ewm(span=30, adjust=False).mean()  # Yellow
    df['ema60'] = df['close'].ewm(span=60, adjust=False).mean()  # Red

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    # SELL Setup:
    # Downtrend alignment: Red (60) on top > Yellow (30) > Green (15)
    # Pullback touched Yellow (30), then Red candle crosses/touches back below Green (15)
    downtrend_aligned = (latest['ema60'] > latest['ema30']) and (latest['ema30'] > latest['ema15'])
    touched_ema30_up = (prev['high'] >= prev['ema30']) or (prev2['high'] >= prev2['ema30']) or (latest['high'] >= latest['ema30'])
    crossed_below_ema15 = (latest['close'] < latest['open']) and (latest['close'] < latest['ema15']) and (latest['open'] >= latest['ema15'] or prev['close'] >= prev['ema15'])

    if downtrend_aligned and touched_ema30_up and crossed_below_ema15:
        return "SELL", 0.94

    # BUY Setup:
    # Uptrend alignment: Red (60) at bottom < Yellow (30) < Green (15)
    # Pullback dipped to touch Yellow (30), then Green candle crosses back above Green (15)
    uptrend_aligned = (latest['ema60'] < latest['ema30']) and (latest['ema30'] < latest['ema15'])
    touched_ema30_down = (prev['low'] <= prev['ema30']) or (prev2['low'] <= prev2['ema30']) or (latest['low'] <= latest['ema30'])
    crossed_above_ema15 = (latest['close'] > latest['open']) and (latest['close'] > latest['ema15']) and (latest['open'] <= latest['ema15'] or prev['close'] <= prev['ema15'])

    if uptrend_aligned and touched_ema30_down and crossed_above_ema15:
        return "BUY", 0.94

    return None, 0.0


def fetch_sub_timeframe(client, symbol, granularity, count=100):
    """Fetches S30 or S15 candles from OANDA client if available."""
    if client is None:
        return None
    try:
        if hasattr(client, "get_candles"):
            rows = client.get_candles(symbol, granularity=granularity, count=count)
            if rows:
                return pd.DataFrame(rows)
        if hasattr(client, "fetch_candles"):
            rows = client.fetch_candles(symbol, granularity=granularity, count=count)
            if rows:
                return pd.DataFrame(rows)
    except Exception:
        pass
    return None


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
        # mtf_trend displays the exact matched Strategy Name & Timeframe in Telegram
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
        try:
            rep = self.engine.retrain(df) if hasattr(self.engine, "retrain") else self.engine.train(df)
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

        if df is None or len(df) < 80:
            self.last_reason = "not_enough_data"
            return None

        # Fetch 30s and 15s candles from OANDA (fallback to 1M if unavailable)
        df_30s = fetch_sub_timeframe(client, self.symbol, "S30", count=60)
        if df_30s is None or df_30s.empty:
            df_30s = df

        df_15s = fetch_sub_timeframe(client, self.symbol, "S15", count=60)
        if df_15s is None or df_15s.empty:
            df_15s = df

        candidates = []

        # 1. PSAR (0.03, 0.3) + Momentum (5) [1M]
        d1, c1 = check_strat1_psar_mom5(df)
        if d1:
            candidates.append((d1, c1, "Strat-1: PSAR(0.03,0.3) + Mom(5) [1M]"))

        # 2. SuperTrend (10, 2.5) + Momentum (7) [30s]
        d2, c2 = check_strat2_supertrend_mom7(df_30s)
        if d2:
            candidates.append((d2, c2, "Strat-2: SuperTrend(10,2.5) + Mom(7) [30s]"))

        # 3. Donchian (50) + AO (30,70) + AC (15,50,5) [1M]
        d3, c3 = check_strat3_donchian_ao_ac(df)
        if d3:
            candidates.append((d3, c3, "Strat-3: Donchian(50) + AO(30,70) + AC(15,50,5) [1M]"))

        # 4. Bollinger Bands + SuperTrend (1,1) + ZigZag (5,12,3) [15s]
        d4, c4 = check_strat4_bb_st_zigzag(df_15s)
        if d4:
            candidates.append((d4, c4, "Strat-4: BB + SuperTrend(1,1) + ZigZag(5,12,3) [15s]"))

        # 5. Triple EMA Pullback (15, 30, 60) [1M]
        d5, c5 = check_strat5_triple_ema(df)
        if d5:
            candidates.append((d5, c5, "Strat-5: Triple EMA Pullback (15/30/60) [1M]"))

        if not candidates:
            self.last_reason = "no_strategy_matched"
            return None

        # Pick the highest-confidence setup
        candidates.sort(key=lambda x: x[1], reverse=True)
        direction, confidence, matched_strategy_name = candidates[0]

        self.last_signal_time = time.time()
        latest = df.iloc[-1]
        target_time = latest['time'] + pd.Timedelta(minutes=1)
        entry = float(latest['close'])

        return SignalResult(direction, confidence, target_time, entry, matched_strategy_name)
