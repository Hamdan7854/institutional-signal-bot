import numpy as np
import pandas as pd
from typing import Dict, Any

class SMCStrategyEngine:
    """
    Evaluates Smart Money Concepts (SMC), Fair Value Gaps (FVG),
    Liquidity Pools (BSL/SSL), and Volume Profile Point of Control (POC).
    """

    def __init__(self, swing_lookback: int = 5, volume_bins: int = 50):
        self.swing_lookback = swing_lookback
        self.volume_bins = volume_bins

    def detect_swing_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Identifies swing highs (Buy-Side Liquidity) and swing lows (Sell-Side Liquidity). """
        df = df.copy()
        df['swing_high'] = False
        df['swing_low'] = False

        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            high_range = df['high'].iloc[i - self.swing_lookback : i + self.swing_lookback + 1]
            low_range = df['low'].iloc[i - self.swing_lookback : i + self.swing_lookback + 1]

            if df['high'].iloc[i] == high_range.max():
                df.at[i, 'swing_high'] = True

            if df['low'].iloc[i] == low_range.min():
                df.at[i, 'swing_low'] = True

        return df

    def detect_fair_value_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Detects 3-candle Fair Value Gaps (FVG) and calculates Consequent Encroachment (CE). """
        df = df.copy()
        df['bullish_fvg_ce'] = np.nan
        df['bearish_fvg_ce'] = np.nan

        for i in range(2, len(df)):
            # Bullish FVG Condition: Low of candle i > High of candle i-2
            if df['low'].iloc[i] > df['high'].iloc[i - 2]:
                top = df['low'].iloc[i]
                bottom = df['high'].iloc[i - 2]
                df.at[i, 'bullish_fvg_ce'] = (top + bottom) / 2.0

            # Bearish FVG Condition: High of candle i < Low of candle i-2
            if df['high'].iloc[i] < df['low'].iloc[i - 2]:
                top = df['low'].iloc[i - 2]
                bottom = df['high'].iloc[i]
                df.at[i, 'bearish_fvg_ce'] = (top + bottom) / 2.0

        return df

    def calculate_volume_poc(self, df: pd.DataFrame) -> float:
        """ Constructs a volume profile histogram and returns the Point of Control (POC). """
        price_min = df['low'].min()
        price_max = df['high'].max()

        if price_min == price_max:
            return float(price_min)

        bins = np.linspace(price_min, price_max, self.volume_bins)
        volume_hist = np.zeros(len(bins) - 1)

        for _, row in df.iterrows():
            low_idx = np.digitize(row['low'], bins) - 1
            high_idx = np.digitize(row['high'], bins) - 1
            low_idx = max(0, min(low_idx, len(bins) - 2))
            high_idx = max(0, min(high_idx, len(bins) - 2))
            
            span = max(1, high_idx - low_idx + 1)
            vol_per_bin = row['volume'] / span
            volume_hist[low_idx : high_idx + 1] += vol_per_bin

        poc_idx = np.argmax(volume_hist)
        poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2.0
        return float(poc_price)

    def generate_predictive_signal(self, df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """ Formulates precise market direction and next-candle target price prediction. """
        df_swings = self.detect_swing_points(df)
        df_fvg = self.detect_fair_value_gaps(df_swings)
        poc_price = self.calculate_volume_poc(df)

        last_close = float(df['close'].iloc[-1])

        # Extract BSL and SSL Liquidity Targets
        swing_highs = df_swings[df_swings['swing_high']]['high']
        swing_lows = df_swings[df_swings['swing_low']]['low']

        bsl_target = float(swing_highs.iloc[-1]) if not swing_highs.empty else last_close * 1.015
        ssl_target = float(swing_lows.iloc[-1]) if not swing_lows.empty else last_close * 0.985

        # Check Active Fair Value Gap Targets
        recent_bull_ce = df_fvg['bullish_fvg_ce'].dropna()
        recent_bear_ce = df_fvg['bearish_fvg_ce'].dropna()

        active_bull_ce = float(recent_bull_ce.iloc[-1]) if not recent_bull_ce.empty else None
        active_bear_ce = float(recent_bear_ce.iloc[-1]) if not recent_bear_ce.empty else None

        # Structural Confluence Evaluation
        if last_close >= poc_price:
            bias = "BULLISH"
            if active_bull_ce and active_bull_ce > last_close:
                predicted_target = active_bull_ce
                rationale = f"Bullish structure targeting unmitigated Fair Value Gap CE at {active_bull_ce:.2f}."
            else:
                predicted_target = bsl_target
                rationale = f"Price above Volume POC ({poc_price:.2f}). Draw on liquidity targeting Buy-Side Liquidity (BSL) at {bsl_target:.2f}."
        else:
            bias = "BEARISH"
            if active_bear_ce and active_bear_ce < last_close:
                predicted_target = active_bear_ce
                rationale = f"Bearish structure targeting unmitigated Fair Value Gap CE at {active_bear_ce:.2f}."
            else:
                predicted_target = ssl_target
                rationale = f"Price below Volume POC ({poc_price:.2f}). Draw on liquidity targeting Sell-Side Liquidity (SSL) at {ssl_target:.2f}."

        return {
            "symbol": symbol,
            "current_price": last_close,
            "bias": bias,
            "predicted_target_price": float(predicted_target),
            "poc_price": poc_price,
            "bsl_target": bsl_target,
            "ssl_target": ssl_target,
            "confluence_reason": rationale
        }
