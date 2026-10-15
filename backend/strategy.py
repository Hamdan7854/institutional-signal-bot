import pandas as pd
import numpy as np
import ta
from config import (
    BODY_MIN_RATIO, 
    MIN_QUALITY_SCORE, 
    ADX_MIN_THRESHOLD, 
    LOOKBACK_CANDLES,
    EMA_FAST,
    EMA_SLOW
)

class InstitutionalEngine:
    """
    Complete 5-Layer Institutional Signal & Quality Filter Engine (5-Minute Timeframe)
    """
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def calculate_indicators(self):
        # Layer 1: Trend Filter (EMA 21/50)
        self.df['ema_fast'] = ta.trend.ema_indicator(self.df['close'], window=EMA_FAST)
        self.df['ema_slow'] = ta.trend.ema_indicator(self.df['close'], window=EMA_SLOW)

        # Layer 3: Momentum (RSI, MACD, ADX)
        self.df['rsi'] = ta.momentum.rsi(self.df['close'], window=14)
        
        macd = ta.trend.MACD(self.df['close'], window_slow=26, window_fast=12, window_sign=9)
        self.df['macd'] = macd.macd()
        self.df['macd_signal'] = macd.macd_signal()

        self.df['adx'] = ta.trend.adx(self.df['high'], self.df['low'], self.df['close'], window=14)

    def evaluate_signal(self, pair: str) -> dict:
        if len(self.df) < LOOKBACK_CANDLES:
            return {"action": "NO TRADE", "reason": "Insufficient Candle Data for Level Analysis"}

        self.calculate_indicators()
        last = self.df.iloc[-1]

        # -------------------------------------------------------------
        # LAYER 1: Trend Filter (EMA 21/50 Structure)
        # -------------------------------------------------------------
        uptrend = last['ema_fast'] > last['ema_slow'] and last['close'] > last['ema_fast']
        downtrend = last['ema_fast'] < last['ema_slow'] and last['close'] < last['ema_fast']

        if not (uptrend or downtrend):
            return {"action": "NO TRADE", "reason": "Layer 1 Failed: Market structure/EMA 21/50 neutral"}

        # -------------------------------------------------------------
        # LAYER 2: Key Levels (Support/Resistance Breakout Validation)
        # -------------------------------------------------------------
        recent_resistance = self.df['high'].iloc[-LOOKBACK_CANDLES:-1].max()
        recent_support = self.df['low'].iloc[-LOOKBACK_CANDLES:-1].min()

        bullish_breakout = last['close'] > recent_resistance
        bearish_breakout = last['close'] < recent_support

        # -------------------------------------------------------------
        # LAYER 3: Momentum Filter (RSI, MACD, ADX > 25)
        # -------------------------------------------------------------
        adx_strong = last['adx'] >= ADX_MIN_THRESHOLD
        if not adx_strong:
            return {"action": "NO TRADE", "reason": f"Layer 3 Failed: ADX Weak ({last['adx']:.1f} < {ADX_MIN_THRESHOLD})"}

        macd_bullish = last['macd'] > last['macd_signal']
        macd_bearish = last['macd'] < last['macd_signal']

        rsi_bullish = 52 < last['rsi'] < 70
        rsi_bearish = 30 < last['rsi'] < 48

        # -------------------------------------------------------------
        # LAYER 4: Entry Confirmation (Candle Close & 60% Body Rule)
        # -------------------------------------------------------------
        candle_range = last['high'] - last['low']
        body_size = abs(last['close'] - last['open'])
        if candle_range == 0 or (body_size / candle_range) < BODY_MIN_RATIO:
            return {"action": "NO TRADE", "reason": "Layer 4 Failed: Candle body < 60% (Weak breakout candle)"}

        # -------------------------------------------------------------
        # LAYER 5: Institutional Quality Filter & Scoring
        # -------------------------------------------------------------
        score = 0
        action = "NO TRADE"
        reason = ""

        if uptrend and bullish_breakout and macd_bullish and rsi_bullish:
            score = 95
            action = "CALL"
            reason = "L1-L5 Pass: EMA Uptrend + Resistance Breakout + Strong ADX/MACD/RSI Momentum"
        elif downtrend and bearish_breakout and macd_bearish and rsi_bearish:
            score = 95
            action = "PUT"
            reason = "L1-L5 Pass: EMA Downtrend + Support Breakdown + Strong ADX/MACD/RSI Momentum"
        else:
            reason = "Layer 5 Safety Filter: Directional Conflict or Poor Quality Score"

        if score < MIN_QUALITY_SCORE:
            action = "NO TRADE"

        return {
            "pair": pair,
            "action": action,
            "score": score,
            "reason": reason,
            "expiry": "5 Minutes",  # Updated to 5 Minutes
            "entry_price": round(last['close'], 5)
        }

    def run_historical_backtest(self, total_trades_to_test=500) -> dict:
        """
        Historical Out-of-Sample Backtesting Engine (500-1000 Trades Evaluation)
        """
        if len(self.df) < total_trades_to_test:
            test_len = len(self.df) - LOOKBACK_CANDLES
        else:
            test_len = total_trades_to_test

        wins, losses, ties = 0, 0, 0
        
        for i in range(LOOKBACK_CANDLES, LOOKBACK_CANDLES + test_len):
            sub_df = self.df.iloc[:i]
            engine = InstitutionalEngine(sub_df)
            sig = engine.evaluate_signal("BACKTEST")
            
            if sig['action'] in ['CALL', 'PUT']:
                entry_p = self.df.iloc[i-1]['close']
                expiry_p = self.df.iloc[i]['close']
                
                if sig['action'] == 'CALL':
                    if expiry_p > entry_p: wins += 1
                    elif expiry_p < entry_p: losses += 1
                    else: ties += 1
                elif sig['action'] == 'PUT':
                    if expiry_p < entry_p: wins += 1
                    elif expiry_p > entry_p: losses += 1
                    else: ties += 1

        total_signals = wins + losses + ties
        win_rate = (wins / total_signals * 100) if total_signals > 0 else 0.0
        
        return {
            "total_tested": total_signals,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": round(win_rate, 2)
        }
