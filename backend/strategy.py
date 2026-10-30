"""
strategy.py — OANDA V20 API Forex Signal Scanner (Relaxed for Testing)
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

DEFAULT_PAIRS = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "EURJPY", "GBPJPY"]

TIMEFRAMES = {
    "execution": "M1",    # 1 minute
    "confirmation": "M5", # 5 minutes
    "trend": "M15",       # 15 minutes
}

# Testing ke liye score aur risk-reward ko relax kar diya hai
MIN_SCORE = int(os.getenv("MIN_SCORE", "2"))
MIN_RR = float(os.getenv("MIN_RR", "1.0"))


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

        if len(execution) < 30 or len(confirmation) < 30 or len(trend_data) < 30:
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


def _analyse(
    pair: str,
    execution: Sequence[Candle],
    confirmation: Sequence[Candle],
    trend_data: Sequence[Candle],
) -> Optional[Signal]:
    if min(len(execution), len(confirmation), len(trend_data)) < 30:
        return None

    last = execution[-1]
    prev_candle = execution[-2]
    atr = _atr(execution)

    # Relaxed momentum check for testing: green candle = CALL, red candle = PUT
    if last.close > prev_candle.close:
        direction = "CALL"
        confirmations = ["OANDA Live Tick Momentum: Bullish Candle"]
        score = 3
    else:
        direction = "PUT"
        confirmations = ["OANDA Live Tick Momentum: Bearish Candle"]
        score = 3

    entry = last.close
    if direction == "CALL":
        stop = entry - (atr * 1.0)
        target = entry + (atr * 1.5)
    else:
        stop = entry + (atr * 1.0)
        target = entry - (atr * 1.5)

    rr = abs(target - entry) / max(abs(entry - stop), 0.0001)

    return Signal(
        pair=pair,
        direction=direction,
        score=score,
        entry=entry,
        stop_loss=round(stop, 5),
        target=round(target, 5),
        risk_reward=round(rr, 2),
        timeframe="1m",
        confirmations=confirmations,
        candle_time=last.timestamp,
        notes="OANDA relaxed test signal successfully generated.",
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

    signals.sort(key=lambda x: x["score"], reverse=True)
    return {
        "signals": signals,
        "errors": errors,
        "scanned": len(selected),
        "signal_count": len(signals),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "status": "OK" if not errors else "PARTIAL",
        }
