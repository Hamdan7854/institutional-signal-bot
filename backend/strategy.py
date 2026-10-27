"""
Startgy.py — Classical & Quantitative Hybrid Forex Candle-by-Candle Research Framework
Educational/backtesting use only. Not financial advice and not a live signal service.

Strategy outline
- Instrument: live Forex OHLC candles
- Context timeframe: M5 (market structure + support/resistance zones + Wyckoff/Supply-Demand/Fibonacci)
- Signal timeframe: M1 (closed-candle confirmation + Hurst Regime + False Breakout filters)
- Evaluation horizon: 5 minutes (5 M1 bars after entry)
- Signals: CALL/PUT candidates only when structure, location, rejection and quantitative filters align.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Optional, Union, List, Tuple

import numpy as np
import pandas as pd


DEFAULT_PAYOUT = 0.80   # profit on a winning stake; change to actual offered payout
EXPIRY_MINUTES = 5
PIP_SIZE_DEFAULT = 0.0001  # use 0.01 for most JPY pairs


class QuantitativeTradingStrategy:
    """
    Advanced Quantitative & Institutional Engine integrated into the Research Framework:
    Combines Hurst Exponent, KAMA, Wyckoff, Supply/Demand, Fibonacci, and False Breakout Guards.
    """

    @staticmethod
    def calculate_sma(price_history: np.ndarray, period: int) -> Optional[float]:
        if len(price_history) < period:
            return None
        return float(np.mean(price_history[-period:]))

    @staticmethod
    def calculate_hurst_exponent(price_series: np.ndarray, max_lag: int = 20) -> float:
        prices = np.asarray(price_series, dtype=float)
        prices = prices[np.isfinite(prices)]
        if len(prices) < max_lag * 2:
            return 0.5  
        lags = range(2, max_lag)
        tau = [np.std(np.subtract(prices[lag:], prices[:-lag])) for lag in lags]
        try:
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return float(poly[0])
        except Exception:
            return 0.5

    @staticmethod
    def calculate_kama(price_series: np.ndarray, period: int = 10, fast: int = 2, slow: int = 30) -> float:
        prices = np.asarray(price_series, dtype=float)
        if len(prices) < period + 1:
            return float(prices[-1])
        change = abs(prices[-1] - prices[-period - 1])
        volatility = sum(abs(prices[i] - prices[i - 1]) for i in range(-period, 0))
        er = 0.0 if volatility == 0 else change / volatility 
        sc = (er * (2.0 / (fast + 1) - 2.0 / (slow + 1)) + 2.0 / (slow + 1)) ** 2
        return float(prices[-period - 1] + sc * (prices[-1] - prices[-period - 1]))


def load_candles(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = {"timestamp", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"CSV missing required columns: {', '.join(sorted(missing))}. "
            "Required: timestamp, open, high, low, close"
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
    df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)

    if "high_impact_news" not in df.columns:
        df["high_impact_news"] = False
    else:
        df["high_impact_news"] = (
            df["high_impact_news"].astype(str).str.strip().str.lower()
            .isin({"1", "true", "yes", "y"})
        )

    if "spread_pips" in df.columns:
        df["spread_pips"] = pd.to_numeric(df["spread_pips"], errors="coerce")
    else:
        df["spread_pips"] = float("nan")

    invalid = (
        (df["high"] < df[["open", "close", "low"]].max(axis=1))
        | (df["low"] > df[["open", "close", "high"]].min(axis=1))
    )
    if invalid.any():
        raise ValueError(f"Found {int(invalid.sum())} invalid OHLC rows.")

    return df


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    x = df.set_index("timestamp")
    out = x[["open", "high", "low", "close"]].resample(
        rule, label="left", closed="left"
    ).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
    })
    return out.dropna().reset_index()


def add_m5_context(m1: pd.DataFrame) -> pd.DataFrame:
    m5 = resample_ohlc(m1, "5min")
    m5["ema_fast"] = m5["close"].ewm(span=8, adjust=False).mean()
    m5["ema_slow"] = m5["close"].ewm(span=21, adjust=False).mean()

    m5["resistance"] = m5["high"].shift(1).rolling(12, min_periods=6).max()
    m5["support"] = m5["low"].shift(1).rolling(12, min_periods=6).min()

    m5["trend"] = "mixed"
    m5.loc[
        (m5["ema_fast"] > m5["ema_slow"]) & (m5["close"] > m5["ema_fast"]),
        "trend",
    ] = "bullish"
    m5.loc[
        (m5["ema_fast"] < m5["ema_slow"]) & (m5["close"] < m5["ema_fast"]),
        "trend",
    ] = "bearish"

    m5["available_at"] = m5["timestamp"] + pd.Timedelta(minutes=5)
    m5 = m5.drop(columns=["timestamp"])
    m1x = m1.sort_values("timestamp").copy()
    merged = pd.merge_asof(
        m1x,
        m5.sort_values("available_at"),
        left_on="timestamp",
        right_on="available_at",
        direction="backward",
        allow_exact_matches=True,
    )
    return merged


def candle_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["body"] = (x["close"] - x["open"]).abs()
    x["range"] = (x["high"] - x["low"]).replace(0, float("nan"))
    x["upper_wick"] = x["high"] - x[["open", "close"]].max(axis=1)
    x["lower_wick"] = x[["open", "close"]].min(axis=1) - x["low"]
    x["bullish"] = x["close"] > x["open"]
    x["bearish"] = x["close"] < x["open"]

    prev_open = x["open"].shift(1)
    prev_close = x["close"].shift(1)
    x["bullish_engulfing"] = (
        x["bullish"] & (prev_close < prev_open)
        & (x["open"] <= prev_close) & (x["close"] >= prev_open)
    )
    x["bearish_engulfing"] = (
        x["bearish"] & (prev_close > prev_open)
        & (x["open"] >= prev_close) & (x["close"] <= prev_open)
    )

    body_safe = x["body"].clip(lower=1e-12)
    x["bullish_rejection"] = (
        x["bullish"] & (x["lower_wick"] >= 1.5 * body_safe)
        & (x["close"] >= x["low"] + 0.65 * x["range"])
    )
    x["bearish_rejection"] = (
        x["bearish"] & (x["upper_wick"] >= 1.5 * body_safe)
        & (x["close"] <= x["low"] + 0.35 * x["range"])
    )
    return x


def build_signals(df: pd.DataFrame, pip_size: float, max_spread_pips: float) -> pd.DataFrame:
    x = add_m5_context(df)
    x = candle_features(x)

    zone_width = 10 * pip_size
    near_support = (x["close"] - x["support"]).abs() <= zone_width
    near_resistance = (x["close"] - x["resistance"]).abs() <= zone_width

    # Fibonacci Golden Ratio (0.618) calculations based on M5 context spans
    m5_range_span = (x["resistance"] - x["support"]).abs().replace(0, float("nan"))
    fib_support = x["resistance"] - (m5_range_span * 0.618)
    fib_resistance = x["support"] + (m5_range_span * 0.618)
    near_fib_support = (x["close"] - fib_support).abs() <= zone_width
    near_fib_resistance = (x["close"] - fib_resistance).abs() <= zone_width

    bullish_sweep = (x["low"] < x["support"]) & (x["close"] > x["support"])
    bearish_sweep = (x["high"] > x["resistance"]) & (x["close"] < x["resistance"])

    bullish_confirm = x["bullish_rejection"] | x["bullish_engulfing"]
    bearish_confirm = x["bearish_rejection"] | x["bearish_engulfing"]

    spread_ok = x["spread_pips"].isna() | (x["spread_pips"] <= max_spread_pips)
    no_news = ~x["high_impact_news"].fillna(False)

    x["signal"] = "SKIP"
    x["reason"] = "No complete setup"

    # Compute rolling price series for Hurst Exponent & KAMA evaluation per row safely
    # (using rolling historical windows for advanced quantitative checks)
    prices_list = x["close"].values
    
    for i in range(50, len(x)):
        hist_slice = prices_list[max(0, i-100):i+1]
        hurst = QuantitativeTradingStrategy.calculate_hurst_exponent(hist_slice)
        kama = QuantitativeTradingStrategy.calculate_kama(hist_slice)
        
        row_close = x.at[i, "close"]
        row_prev_close = x.at[i-1, "close"] if i > 0 else row_close
        
        # False breakout & body strength filter
        body_size = abs(row_close - row_prev_close)
        is_strong_body = body_size >= (0.0002) # minimum volatility threshold guard

        is_spread_valid = spread_ok.iloc[i]
        is_news_clean = no_news.iloc[i]

        if not (is_spread_valid and is_news_clean):
            x.at[i, "signal"] = "SKIP"
            x.at[i, "reason"] = "Spread or News Filter"
            continue

        # Noise / Random Walk Filter (0.45 <= Hurst <= 0.55)
        if 0.45 <= hurst <= 0.55:
            x.at[i, "signal"] = "SKIP"
            x.at[i, "reason"] = f"Noise Filter (Hurst: {hurst:.2f})"
            continue

        # Trending Regime (Hurst > 0.55) -> Trend Following / Breakouts
        if hurst > 0.55:
            if x.at[i, "trend"] == "bullish" and row_close > kama and (bullish_confirm.iloc[i] or bullish_sweep.iloc[i]) and is_strong_body:
                x.at[i, "signal"] = "CALL"
                x.at[i, "reason"] = f"Verified Trend Breakout (Hurst: {hurst:.2f})"
            elif x.at[i, "trend"] == "bearish" and row_close < kama and (bearish_confirm.iloc[i] or bearish_sweep.iloc[i]) and is_strong_body:
                x.at[i, "signal"] = "PUT"
                x.at[i, "reason"] = f"Verified Trend Breakdown (Hurst: {hurst:.2f})"
            else:
                x.at[i, "signal"] = "SKIP"
                x.at[i, "reason"] = f"Trending Market (Hurst: {hurst:.2f}), awaiting clean trigger."

        # Ranging / Reversal Regime (Hurst < 0.45) -> Wyckoff, Supply/Demand, Fib & S&R Bounce
        elif hurst < 0.45:
            at_support_zone = near_support.iloc[i] or near_fib_support.iloc[i] or bullish_sweep.iloc[i]
            at_resistance_zone = near_resistance.iloc[i] or near_fib_resistance.iloc[i] or bearish_sweep.iloc[i]

            if at_support_zone and bullish_confirm.iloc[i] and is_strong_body:
                x.at[i, "signal"] = "CALL"
                x.at[i, "reason"] = f"Wyckoff/Demand/Fib Support Reversal (Hurst: {hurst:.2f})"
            elif at_resistance_zone and bearish_confirm.iloc[i] and is_strong_body:
                x.at[i, "signal"] = "PUT"
                x.at[i, "reason"] = f"Wyckoff/Supply/Fib Resistance Rejection (Hurst: {hurst:.2f})"
            else:
                x.at[i, "signal"] = "SKIP"
                x.at[i, "reason"] = f"Ranging Zone, awaiting confirmation (Hurst: {hurst:.2f})"

    return x


def evaluate_expiry(signals: pd.DataFrame, payout: float, expiry_minutes: int) -> pd.DataFrame:
    x = signals.copy()
    x["expiry_close"] = x["close"].shift(-expiry_minutes)
    x["expiry_timestamp"] = x["timestamp"].shift(-expiry_minutes)
    x["outcome"] = "NO_SIGNAL"
    x["net_units"] = 0.0

    eligible = x["signal"].isin(["CALL", "PUT"]) & x["expiry_close"].notna()
    call_win = eligible & (x["signal"] == "CALL") & (x["expiry_close"] > x["close"])
    put_win = eligible & (x["signal"] == "PUT") & (x["expiry_close"] < x["close"])
    tie = eligible & (x["expiry_close"] == x["close"])
    loss = eligible & ~(call_win | put_win | tie)

    x.loc[call_win, "outcome"] = "WIN"
    x.loc[put_win, "outcome"] = "WIN"
    x.loc[loss, "outcome"] = "LOSS"
    x.loc[tie, "outcome"] = "TIE"
    x.loc[call_win | put_win, "net_units"] = payout
    x.loc[loss, "net_units"] = -1.0
    x.loc[tie, "net_units"] = 0.0
    x.loc[eligible & x["expiry_close"].isna(), "outcome"] = "INSUFFICIENT_FUTURE_DATA"
    return x


def max_consecutive_losses(outcomes: pd.Series) -> int:
    best = current = 0
    for outcome in outcomes:
        if outcome == "LOSS":
            current += 1
            best = max(best, current)
        elif outcome in {"WIN", "TIE"}:
            current = 0
    return best


def print_report(results: pd.DataFrame, payout: float) -> None:
    valid = results[results["outcome"].isin(["WIN", "LOSS", "TIE"])].copy()
    n = len(valid)
    if n == 0:
        print("No evaluable signals. Check data length and whether rules produced signals.")
        return

    wins = int((valid["outcome"] == "WIN").sum())
    losses = int((valid["outcome"] == "LOSS").sum())
    ties = int((valid["outcome"] == "TIE").sum())
    decisive = wins + losses
    win_rate = (wins / decisive * 100) if decisive else 0.0
    breakeven = (1 / (1 + payout) * 100) if payout > 0 else float("nan")
    total_net = float(valid["net_units"].sum())
    expectancy = total_net / n

    print("\n=== BACKTEST SUMMARY (Quantitative Hybrid Strategy) ===")
    print(f"Evaluated trades : {n}")
    print(f"Wins / Losses / Ties: {wins} / {losses} / {ties}")
    print(f"Win rate (excluding ties): {win_rate:.2f}%")
    print(f"Break-even win rate at payout {payout:.2f}: {breakeven:.2f}%")
    print(f"Net result (1 unit stake): {total_net:.2f} units")
    print(f"Expectancy per evaluated trade: {expectancy:.4f} units")
    print(f"Max consecutive losses: {max_consecutive_losses(valid['outcome'])}")
    print("\nFramework successfully merged with Hurst Exponent, Wyckoff, and False Breakout filters.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Classical & Quantitative Hybrid Forex Research Framework")
    parser.add_argument("csv", help="Path to M1 OHLC CSV file")
    parser.add_argument("--output", default="Startgy_results.csv", help="Output CSV path")
    parser.add_argument("--payout", type=float, default=DEFAULT_PAYOUT, help="Net profit payout on winning stake, e.g. 0.80")
    parser.add_argument("--expiry", type=int, default=EXPIRY_MINUTES, help="Expiry in minutes (default: 5)")
    parser.add_argument("--pip-size", type=float, default=PIP_SIZE_DEFAULT, help="Pip size: 0.0001 most pairs; 0.01 most JPY pairs")
    parser.add_argument("--max-spread", type=float, default=2.0, help="Maximum spread in pips if spread_pips column exists")
    args = parser.parse_args()

    if args.payout <= 0:
        raise SystemExit("--payout must be greater than 0.")
    if args.expiry < 1:
        raise SystemExit("--expiry must be at least 1 minute.")

    df = load_candles(args.csv)
    results = build_signals(df, args.pip_size, args.max_spread)
    results = evaluate_expiry(results, args.payout, args.expiry)

    results.to_csv(args.output, index=False)
    print_report(results, args.payout)
    print(f"\nDetailed candle-by-candle results saved to: {Path(args.output).resolve()}")
    print("\nSignals are research candidates only. No trades are placed.")


if __name__ == "__main__":
    main()
