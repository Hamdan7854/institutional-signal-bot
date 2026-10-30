"""
strategy.py — Async multi-pair Forex signal scanner (Optimized for EURUSD & USDJPY)
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import websockets

LOG = logging.getLogger("forex_strategy")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

# Sirf EURUSD aur USDJPY rakhe hain taake speed fast ho aur HTTP 520 error na aaye
DEFAULT_PAIRS = [
    "EURUSD", "USDJPY",
]

PAIRS = [p.strip().upper() for p in os.getenv(
    "PAIRS", ",".join(DEFAULT_PAIRS)
).split(",") if p.strip()]

TIMEFRAMES = {
    "execution": "1m",
    "confirmation": "5m",
    "trend": "15m",
}

CANDLE_LIMIT = int(os.getenv("CANDLE_LIMIT", "200"))
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


class DerivClient:
    """Safe Deriv WebSocket adapter fetching timeframes securely."""

    def __init__(self):
        self.app_id = os.getenv("DERIV_APP_ID", "").strip()
        self.api_token = os.getenv("DERIV_API_TOKEN", "").strip()
        self.sem = asyncio.Semaphore(1)

    async def _fetch_single_tf(self, websocket, deriv_symbol: str, granularity: int) -> List[Candle]:
        req = {
            "ticks_history": deriv_symbol,
            "adjust_start_time": 1,
            "count": CANDLE_LIMIT,
            "end": "latest",
            "granularity": granularity,
            "style": "candles"
        }
        await websocket.send(json.dumps(req))
        resp = await websocket.recv()
        data = json.loads(resp)

        if "error" in data:
            raise RuntimeError(f"Deriv API error: {data['error'].get('message')}")

        candles_data = data.get("candles", [])
        out: List[Candle] = []
        for row in candles_data:
            ts = row.get("epoch")
            o = float(row.get("open", 0))
            h = float(row.get("high", 0))
            l = float(row.get("low", 0))
            c = float(row.get("close", 0))
            if h < l or h < max(o, c) or l > min(o, c):
                continue
            out.append(Candle(ts, o, h, l, c, 0.0))
        return out

    async def fetch_timeframes(self, symbol: str) -> Tuple[List[Candle], List[Candle], List[Candle]]:
        if not self.app_id:
            raise RuntimeError("DERIV_APP_ID environment variable is missing")

        deriv_symbol = symbol if symbol.startswith("frx") or symbol.startswith("R_") else f"frx{symbol}"
        uri = f"wss://ws.derivws.com/websockets_v3?app_id={self.app_id}"

        gran_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900
        }

        async with self.sem:
            last_err = None
            for attempt in range(3):
                try:
                    async with websockets.connect(uri, open_timeout=25) as websocket:
                        if self.api_token:
                            await websocket.send(json.dumps({"authorize": self.api_token}))
                            await websocket.recv()

                        execution = await self._fetch_single_tf(websocket, deriv_symbol, gran_map["1m"])
                        await asyncio.sleep(0.2)
                        confirmation = await self._fetch_single_tf(websocket, deriv_symbol, gran_map["5m"])
                        await asyncio.sleep(0.2)
                        trend_data = await self._fetch_single_tf(websocket, deriv_symbol, gran_map["15m"])

                        if len(execution) < 50 or len(confirmation) < 50 or len(trend_data) < 50:
                            raise ValueError(f"{symbol}: Insufficient valid candles received")

                        return execution, confirmation, trend_data

                except Exception as exc:
                    last_err = exc
                    if attempt < 2:
                        await asyncio.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"Failed to fetch {symbol} from Deriv: {last_err}")


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


def _hurst_exponent(c: Sequence[Candle], max_lag: int = 20) -> float:
    closes = [x.close for x in c]
    if len(closes) < max_lag * 2:
        return 0.5
    lags = range(2, max_lag)
    tau = []
    for lag in lags:
        diffs = [closes[i] - closes[i - lag] for i in range(lag, len(closes))]
        if not diffs:
            continue
        variance = sum((d - (sum(diffs)/len(diffs))) ** 2 for d in diffs) / len(diffs)
        tau.append(math.sqrt(variance) if variance > 0 else 1e-8)
    if len(tau) < 2:
        return 0.5
    log_lags = [math.log(l) for l in lags[:len(tau)]]
    log_tau = [math.log(t) if t > 0 else 0 for t in tau]
    n = len(log_lags)
    sum_x = sum(log_lags)
    sum_y = sum(log_tau)
    sum_xy = sum(x * y for x, y in zip(log_lags, log_tau))
    sum_xx = sum(x * x for x in log_lags)
    denominator = (n * sum_xx - sum_x ** 2)
    if denominator == 0:
        return 0.5
    return float((n * sum_xy - sum_x * sum_y) / denominator)


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


def _fvg(c: Sequence[Candle], direction: str):
    for i in range(len(c) - 1, max(1, len(c) - 12), -1):
        first, third = c[i - 2], c[i]
        if direction == "CALL" and first.high < third.low:
            return (first.high, third.low)
        if direction == "PUT" and first.low > third.high:
            return (third.high, first.low)
    return None


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

    hurst = _hurst_exponent(execution)
    confirmations.append(f"Hurst Exponent: {hurst:.2f}")
    if hurst < 0.5:
        score += 1

    sup, res = _support_resistance_zones(execution)
    if sup is not None and res is not None:
        if direction == "CALL" and abs(last.low - sup) <= atr * 0.75:
            confirmations.append(f"Ranging Support confluence at {sup:.5f}")
            score += 1
        elif direction == "PUT" and abs(last.high - res) <= atr * 0.75:
            confirmations.append(f"Ranging Resistance confluence at {res:.5f}")
            score += 1

    gap = _fvg(execution, direction)
    if gap:
        confirmations.append(f"FVG zone")
        score += 2

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
        timeframe=TIMEFRAMES["execution"],
        confirmations=confirmations,
        candle_time=last.timestamp,
        notes="Optimized Deriv WebSocket signal.",
    )


async def analyze_next_candle_target(pair: str) -> Optional[Dict[str, Any]]:
    client = DerivClient()
    try:
        execution, confirmation, trend_data = await client.fetch_timeframes(pair)
        signal = _analyse(pair, execution, confirmation, trend_data)
        if signal:
            return signal.to_dict()
    except Exception as exc:
        LOG.exception("Analysis failed for %s", pair)
    return None


async def scan_all(pairs: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    selected = [p.upper().strip() for p in (pairs or PAIRS) if p.strip()]
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
