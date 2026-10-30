"""
strategy.py — Finnhub REST API Forex Signal Scanner (EURUSD & USDJPY)
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import requests

LOG = logging.getLogger("forex_strategy")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

# Finnhub ke mutabiq symbols
DEFAULT_PAIRS = ["EURUSD", "USDJPY"]

TIMEFRAMES = {
    "execution": "1",    # 1 minute
    "confirmation": "5", # 5 minutes
    "trend": "15",       # 15 minutes
}

MIN_SCORE = int(os.getenv("MIN_SCORE", "7"))
MIN_RR = float(os.getenv("MIN_RR", "1.5"))


@dataclass
class Candle:
    timestamp: Any
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Signal:
    pair: str
    direction: str
    score: int
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    timeframe: str
    confirmations: List[str]
    candle_time: Any
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FinnhubClient:
    """Finnhub REST API client for fetching Forex candles reliably."""

    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY", "").strip()

    def _fetch_candles(self, symbol: str, resolution: str) -> List[Candle]:
        if not self.api_key:
            raise RuntimeError("FINNHUB_API_KEY environment variable is missing")

        # Finnhub symbol format (e.g., OANDA:EUR_USD)
        finnhub_symbol = f"OANDA:{symbol[:3]}_{symbol[3:]}"
        
        # Last 3 days range for candles
        to_time = int(time.time())
        from_time = to_time - (3 * 24 * 60 * 60)

        url = "https://finnhub.io/api/v1/forex/candle"
        params = {
            "symbol": finnhub_symbol,
            "resolution": resolution,
            "from": from_time,
            "to": to_time,
            "token": self.api_key
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Finnhub HTTP error {response.status_code}")

        data = response.json()
        if data.get("s") != "ok":
            raise RuntimeError(f"Finnhub API returned status: {data.get('s')}")

        timestamps = data.get("t", [])
        opens = data.get("o", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        closes = data.get("c", [])

        out: List[Candle] = []
        for i in range(len(timestamps)):
            out.append(Candle(
                timestamp=timestamps[i],
                open=float(opens[i]),
                high=float(highs[i]),
                low=float(lows[i]),
                close=float(closes[i]),
                volume=0.0
            ))
        return out

    async def fetch_timeframes(self, symbol: str) -> Tuple[List[Candle], List[Candle], List[Candle]]:
        # Run synchronous requests in thread to keep async event loop non-blocking
        loop = asyncio.get_running_loop()
        
        execution = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["execution"])
        await asyncio.sleep(0.2)
        confirmation = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["confirmation"])
        await asyncio.sleep(0.2)
        trend_data = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["trend"])

        if len(execution) < 50 or len(confirmation) < 50 or len(trend_data) < 50:
            raise ValueError(f"{symbol}: Insufficient candles from Finnhub")

        return execution, confirmation, trend_data


def _atr(c: Sequence[Candle], period: int = 14) -> float:
    trs = []
    for i in range(1, len(c)):
        prev = c[i - 1].close
        trs.append(max(c[i].high - c[i].low, abs(c[i].high - prev), abs(c[i].low - prev)))
    if not trs:
        return 0.0
    return sum(trs[-period:]) / min(period, len(trs))


def _kama(c: Sequence[Candle], period: int = 10, fast_end: float = 2.0 / 3.0, slow_end: float = 2.0 / 31.0) -> Optional[float]:
    if len(c) < period + 1:
        return None
    closes = [x.close for x in c]
    kama_values = [sum(closes[:period]) / period]
    for i in range(period, len(closes)):
        change = abs(closes[i] - closes[i - period])
        volatility = sum(abs(closes[j] - closes[j - 1]) for j in range(i - period + 1, i + 1))
        er = 0.0 if volatility == 0 else change / volatility
        sc = (er * (fast_end - slow_end) + slow_end) ** 2
        prev_kama = kama_values[-1]
        kama_values.append(prev_kama + sc * (closes[i] - prev_kama))
    return kama_values[-1] if kama_values else None


def _support_resistance_zones(c: Sequence[Candle], lookback: int = 50) -> Tuple[Optional[float], Optional[float]]:
    if len(c) < lookback:
        return None, None
    recent = c[-lookback:]
    return min(x.low for x in recent), max(x.high for x in recent)


def _swings(c: Sequence[Candle], left: int = 2, right: int = 2):
    highs, lows = [], []
    for i in range(left, len(c) - right):
        if all(c[i].high > c[j].high for j in range(i-left, i)) and all(c[i].high >= c[j].high for j in range(i+1, i+right+1)):
            highs.append((i, c[i].high))
        if all(c[i].low < c[j].low for j in range(i-left, i)) and all(c[i].low <= c[j].low for j in range(i+1, i+right+1)):
            lows.append((i, c[i].low))
    return highs, lows


def _trend(c: Sequence[Candle]) -> str:
    highs, lows = _swings(c[-100:])
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    if highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1]:
        return "BULLISH"
    if highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1]:
        return "BEARISH"
    return "NEUTRAL"


def _liquidity_sweep(c: Sequence[Candle], lookback: int = 20):
    if len(c) < lookback + 2:
        return None
    last = c[-1]
    prior = c[-lookback-1:-1]
    prior_high = max(x.high for x in prior)
    prior_low = min(x.low for x in prior)
    if last.high > prior_high and last.close < prior_high:
        return "BEARISH_SWEEP", prior_high
    if last.low < prior_low and last.close > prior_low:
        return "BULLISH_SWEEP", prior_low
    return None


def _mss(c: Sequence[Candle], direction: str, lookback: int = 20) -> bool:
    recent = c[-lookback-1:-1]
    if not recent:
        return False
    if direction == "CALL":
        return c[-1].close > max(x.high for x in recent)
    return c[-1].close < min(x.low for x in recent)


def _analyse(
    pair: str,
    execution: Sequence[Candle],
    confirmation: Sequence[Candle],
    trend_data: Sequence[Candle],
) -> Optional[Signal]:
    if min(len(execution), len(confirmation), len(trend_data)) < 50:
        return None

    last = execution[-1]
    atr = _atr(execution)
    if atr <= 0:
        return None

    htf_trend = _trend(trend_data)
    mid_trend = _trend(confirmation)
    sweep = _liquidity_sweep(execution)
    if not sweep:
        return None

    sweep_type, swept_level = sweep
    direction = "CALL" if sweep_type == "BULLISH_SWEEP" else "PUT"

    if not _mss(execution, direction):
        return None
    if direction == "CALL" and htf_trend != "BULLISH":
        return None
    if direction == "PUT" and htf_trend != "BEARISH":
        return None

    confirmations = [
        f"{sweep_type} at {swept_level:.5f}",
        "Execution-timeframe MSS",
        f"Higher-timeframe trend: {htf_trend}",
    ]
    score = 3

    kama_val = _kama(execution)
    if kama_val is not None:
        confirmations.append(f"KAMA level: {kama_val:.5f}")
        if direction == "CALL" and last.close > kama_val:
            score += 1
        elif direction == "PUT" and last.close < kama_val:
            score += 1

    sup, res = _support_resistance_zones(execution)
    if sup is not None and res is not None:
        if direction == "CALL" and abs(last.low - sup) <= atr * 0.75:
            confirmations.append(f"Support confluence at {sup:.5f}")
            score += 1
        elif direction == "PUT" and abs(last.high - res) <= atr * 0.75:
            confirmations.append(f"Resistance confluence at {res:.5f}")
            score += 1

    if score < MIN_SCORE:
        return None

    entry = last.close
    if direction == "CALL":
        stop = min(last.low, swept_level) - atr * 0.15
        risk = entry - stop
        target = entry + risk * MIN_RR
    else:
        stop = max(last.high, swept_level) + atr * 0.15
        risk = stop - entry
        target = entry - risk * MIN_RR

    if risk <= 0 or not all(map(math.isfinite, (entry, stop, target))):
        return None

    rr = abs(target - entry) / risk
    if rr < MIN_RR:
        return None

    return Signal(
        pair=pair,
        direction=direction,
        score=score,
        entry=entry,
        stop_loss=stop,
        target=target,
        risk_reward=round(rr, 2),
        timeframe="1m",
        confirmations=confirmations,
        candle_time=last.timestamp,
        notes="Finnhub REST API stable signal.",
    )


async def analyze_next_candle_target(pair: str) -> Optional[Dict[str, Any]]:
    client = FinnhubClient()
    try:
        execution, confirmation, trend_data = await client.fetch_timeframes(pair)
        signal = _analyse(pair, execution, confirmation, trend_data)
        if signal:
            return signal.to_dict()
    except Exception as exc:
        LOG.exception("Finnhub analysis failed for %s: %s", pair, exc)
    return None


async def scan_all(pairs: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    selected = [p.upper().strip() for p in (pairs or DEFAULT_PAIRS) if p.strip()]
    started = time.perf_counter()
    
    signals = []
    errors = {}
    for pair in selected:
        res = await analyze_next_candle_target(pair)
        if res:
            signals.append(res)
        await asyncio.sleep(0.2)

    signals.sort(key=lambda x: x["score"], reverse=True)
    return {
        "signals": signals,
        "errors": errors,
        "scanned": len(selected),
        "signal_count": len(signals),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "status": "OK" if not errors else "PARTIAL",
    }
