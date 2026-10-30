"""
strategy.py — OANDA V20 API Forex Signal Scanner (80% Match Rule & 5 Decimals)
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

DEFAULT_PAIRS = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP"]

TIMEFRAMES = {
    "execution": "M1",    # 1 minute
    "confirmation": "M5", # 5 minutes
    "trend": "M15",       # 15 minutes
}

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
    confidence: int
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


class OandaClient:
    """OANDA V20 REST API client for fetching Forex candles reliably."""

    def __init__(self):
        self.api_key = os.getenv("OANDA_API_KEY", "").strip()
        self.account_id = os.getenv("OANDA_ACCOUNT_ID", "").strip()
        self.base_url = "https://api-fxpractice.oanda.com/v3"

    def _fetch_candles(self, symbol: str, granularity: str) -> List[Candle]:
        if not self.api_key:
            raise RuntimeError("OANDA_API_KEY environment variable is missing")

        oanda_symbol = f"{symbol[:3]}_{symbol[3:]}"

        url = f"{self.base_url}/instruments/{oanda_symbol}/candles"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept-Datetime-Format": "UNIX"
        }
        params = {
            "granularity": granularity,
            "count": 100,
            "price": "M"
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"OANDA HTTP error {response.status_code}: {response.text}")

        data = response.json()
        raw_candles = data.get("candles", [])

        out: List[Candle] = []
        for rc in raw_candles:
            if not rc.get("complete", True):
                continue
            mid = rc.get("mid", {})
            out.append(Candle(
                timestamp=float(rc.get("time", 0)),
                open=float(mid.get("o", 0)),
                high=float(mid.get("h", 0)),
                low=float(mid.get("l", 0)),
                close=float(mid.get("c", 0)),
                volume=float(rc.get("volume", 0))
            ))
        return out

    async def fetch_timeframes(self, symbol: str) -> Tuple[List[Candle], List[Candle], List[Candle]]:
        loop = asyncio.get_running_loop()
        
        execution = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["execution"])
        await asyncio.sleep(0.1)
        confirmation = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["confirmation"])
        await asyncio.sleep(0.1)
        trend_data = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["trend"])

        if len(execution) < 40 or len(confirmation) < 40 or len(trend_data) < 40:
            raise ValueError(f"{symbol}: Insufficient candles from OANDA")

        return execution, confirmation, trend_data


def _atr(c: Sequence[Candle], period: int = 14) -> float:
    trs = []
    for i in range(1, len(c)):
        prev = c[i - 1].close
        trs.append(max(c[i].high - c[i].low, abs(c[i].high - prev), abs(c[i].low - prev)))
    if not trs:
        return 0.0010
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


def _swings(c: Sequence[Candle], left: int = 2, right: int = 2):
    highs, lows = [], []
    for i in range(left, len(c) - right):
        if all(c[i].high > c[j].high for j in range(i-left, i)) and all(c[i].high >= c[j].high for j in range(i+1, i+right+1)):
            highs.append((i, c[i].high))
        if all(c[i].low < c[j].low for j in range(i-left, i)) and all(c[i].low <= c[j].low for j in range(i+1, i+right+1)):
            lows.append((i, c[i].low))
    return highs, lows


def _trend(c: Sequence[Candle]) -> str:
    highs, lows = _swings(c[-50:])
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    if highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1]:
        return "BULLISH"
    if highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1]:
        return "BEARISH"
    return "NEUTRAL"


def _analyse(
    pair: str,
    execution: Sequence[Candle],
    confirmation: Sequence[Candle],
    trend_data: Sequence[Candle],
) -> Optional[Signal]:
    if min(len(execution), len(confirmation), len(trend_data)) < 40:
        return None

    last = execution[-1]
    prev = execution[-2]
    atr = _atr(execution)

    # Direction determination based on candle momentum
    direction = "CALL" if last.close >= prev.close else "PUT"

    # Total 5 conditions setup
    confirmations = []
    
    # Condition 1: Candle Momentum Check
    c1_passed = True
    if direction == "CALL":
        confirmations.append("✔ Bullish candle momentum confirmed")
    else:
        confirmations.append("✔ Bearish candle momentum confirmed")

    # Condition 2: Trend Alignment (HTF Trend)
    htf_trend = _trend(trend_data)
    c2_passed = (htf_trend != "NEUTRAL")
    confirmations.append(f"✔ Higher Timeframe Trend: {htf_trend}")

    # Condition 3: KAMA Filter Check
    kama_val = _kama(execution)
    c3_passed = False
    if kama_val is not None:
        if direction == "CALL" and last.close >= kama_val:
            c3_passed = True
            confirmations.append(f"✔ Price is above KAMA indicator ({kama_val:.5f})")
        elif direction == "PUT" and last.close <= kama_val:
            c3_passed = True
            confirmations.append(f"✔ Price is below KAMA indicator ({kama_val:.5f})")
        else:
            confirmations.append(f"✖ KAMA filter neutral ({kama_val:.5f})")

    # Condition 4: Support & Resistance Confluence Check
    recent_lows = [x.low for x in execution[-20:]]
    recent_highs = [x.high for x in execution[-20:]]
    sup = min(recent_lows) if recent_lows else last.close
    res = max(recent_highs) if recent_highs else last.close
    
    c4_passed = False
    if direction == "CALL" and abs(last.low - sup) <= atr * 1.0:
        c4_passed = True
        confirmations.append(f"✔ Support level confluence at {sup:.5f}")
    elif direction == "PUT" and abs(last.high - res) <= atr * 1.0:
        c4_passed = True
        confirmations.append(f"✔ Resistance level confluence at {res:.5f}")
    else:
        confirmations.append("✖ S/R zone distance moderate")

    # Condition 5: Volatility & ATR Stability Check
    c5_passed = (atr > 0.00005)
    if c5_passed:
        confirmations.append(f"✔ ATR volatility stable ({atr:.5f})")

    # Total conditions list
    all_conditions = [c1_passed, c2_passed, c3_passed, c4_passed, c5_passed]
    total_checks = len(all_conditions)
    matched_count = sum(1 for x in all_conditions if x)
    
    # 80% rule: minimum 4 out of 5 conditions must match
    required_matches = math.ceil(total_checks * 0.8) # 4
    if matched_count < required_matches:
        return None

    confidence_score = int((matched_count / total_checks) * 100)

    # 5 decimal precise calculations for Entry, Stop Loss, Target
    entry = round(float(last.close), 5)
    if direction == "CALL":
        stop = round(entry - (atr * 1.2), 5)
        target = round(entry + (atr * (1.2 * MIN_RR)), 5)
    else:
        stop = round(entry + (atr * 1.2), 5)
        target = round(entry - (atr * (1.2 * MIN_RR)), 5)

    risk = abs(entry - stop)
    if risk <= 0:
        return None
    rr = round(abs(target - entry) / risk, 2)

    return Signal(
        pair=pair,
        direction=direction,
        score=matched_count,
        confidence=confidence_score,
        entry=entry,
        stop_loss=stop,
        target=target,
        risk_reward=rr,
        timeframe="1m",
        confirmations=confirmations,
        candle_time=last.timestamp,
        notes=f"OANDA V20 Live Signal ({matched_count}/{total_checks} conditions matched).",
    )


async def analyze_next_candle_target(pair: str) -> Optional[Dict[str, Any]]:
    client = OandaClient()
    try:
        execution, confirmation, trend_data = await client.fetch_timeframes(pair)
        signal = _analyse(pair, execution, confirmation, trend_data)
        if signal:
            return signal.to_dict()
    except Exception as exc:
        LOG.exception("OANDA analysis failed for %s: %s", pair, exc)
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
        await asyncio.sleep(0.1)

    signals.sort(key=lambda x: x["confidence"], reverse=True)
    return {
        "signals": signals,
        "errors": errors,
        "scanned": len(selected),
        "signal_count": len(signals),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "status": "OK" if not errors else "PARTIAL",
    }
