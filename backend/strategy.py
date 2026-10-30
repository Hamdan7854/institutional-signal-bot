"""
strategy.py — Async multi-pair Forex signal scanner (DataDriv adapter)
Updated with KAMA, Hurst Exponent, Ranging Support/Resistance, and analyze_next_candle_target

IMPORTANT
---------
This is a research/backtesting scaffold, NOT a validated profitable strategy.
Do not use with real money until you have:
  1) matched DataDriv's exact endpoint, authentication and JSON schema;
  2) verified candle timestamps/prices against your broker;
  3) backtested with spread, slippage and out-of-sample data; and
  4) forward-tested on demo.

Install:
    pip install aiohttp

Required environment variables:
    DATADRIV_API_URL       Full candle endpoint URL
    DATADRIV_API_KEY       API key (if required)
Optional:
    DATADRIV_API_KEY_HEADER  default: Authorization
    DATADRIV_API_KEY_PREFIX default: Bearer
    DATADRIV_SYMBOL_PARAM   default: symbol
    DATADRIV_INTERVAL_PARAM default: interval
    DATADRIV_LIMIT_PARAM    default: limit
    DATADRIV_API_KEY_PARAM  If set, sends key as a query parameter instead
    DATADRIV_CANDLES_PATH   Optional dotted path to candle array, e.g. data.candles
    PAIRS                   Comma-separated symbols
    REQUEST_TIMEOUT        default 12 seconds
    MAX_CONCURRENCY        default 12
    CANDLE_LIMIT           default 300
    MIN_SCORE              default 7
    MIN_RR                  default 1.5

The DataDriv endpoint and payload vary by account/API version. Configure the
adapter below to match the documentation. No API credentials are hard-coded.
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

import aiohttp

LOG = logging.getLogger("forex_strategy")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

DEFAULT_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD",
    "AUDUSD", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP",
]

PAIRS = [p.strip().upper() for p in os.getenv(
    "PAIRS", ",".join(DEFAULT_PAIRS)
).split(",") if p.strip()]

# Execution timeframe is used for setup detection. Higher timeframes are
# fetched separately for directional context.
TIMEFRAMES = {
    "execution": os.getenv("EXECUTION_TIMEFRAME", "1m"),
    "confirmation": os.getenv("CONFIRMATION_TIMEFRAME", "5m"),
    "trend": os.getenv("TREND_TIMEFRAME", "15m"),
}

CANDLE_LIMIT = int(os.getenv("CANDLE_LIMIT", "300"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "12"))
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "12"))
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


def _get_nested(data: Any, dotted_path: str) -> Any:
    value = data
    for key in dotted_path.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def _number(row: dict, names: Sequence[str], default: Optional[float] = None):
    for name in names:
        value = row.get(name)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return default


def normalize_candles(payload: Any) -> List[Candle]:
    """Normalize common OHLC JSON shapes. Adapt this if DataDriv differs."""
    path = os.getenv("DATADRIV_CANDLES_PATH", "").strip()
    rows = _get_nested(payload, path) if path else payload

    if isinstance(rows, dict):
        # Common wrappers
        for key in ("candles", "data", "results", "items", "prices"):
            if isinstance(rows.get(key), list):
                rows = rows[key]
                break

    if not isinstance(rows, list):
        raise ValueError(
            "Could not locate candle list in DataDriv response. "
            "Set DATADRIV_CANDLES_PATH or edit normalize_candles()."
        )

    out: List[Candle] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        o = _number(row, ("open", "o", "Open"))
        h = _number(row, ("high", "h", "High"))
        l = _number(row, ("low", "l", "Low"))
        c = _number(row, ("close", "c", "Close", "price"))
        if None in (o, h, l, c):
            continue
        ts = row.get("timestamp", row.get("time", row.get("t", row.get("date"))))
        vol = _number(row, ("volume", "tick_volume", "v", "Volume"), 0.0) or 0.0
        if h < l or h < max(o, c) or l > min(o, c):
            continue
        out.append(Candle(ts, o, h, l, c, vol))

    try:
        out.sort(key=lambda x: float(x.timestamp))
    except (TypeError, ValueError):
        pass
    return out


class DataDrivClient:
    """Small async adapter. Match params/headers to your DataDriv API docs."""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.url = os.getenv("DATADRIV_API_URL", "").strip()
        self.api_key = os.getenv("DATADRIV_API_KEY", "").strip()
        self.sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async def candles(self, symbol: str, interval: str) -> List[Candle]:
        if not self.url:
            raise RuntimeError("DATADRIV_API_URL environment variable is missing")

        params = {
            os.getenv("DATADRIV_SYMBOL_PARAM", "symbol"): symbol,
            os.getenv("DATADRIV_INTERVAL_PARAM", "interval"): interval,
            os.getenv("DATADRIV_LIMIT_PARAM", "limit"): str(CANDLE_LIMIT),
        }
        headers = {"Accept": "application/json"}
        key_param = os.getenv("DATADRIV_API_KEY_PARAM", "").strip()

        if self.api_key:
            if key_param:
                params[key_param] = self.api_key
            else:
                header_name = os.getenv("DATADRIV_API_KEY_HEADER", "Authorization")
                prefix = os.getenv("DATADRIV_API_KEY_PREFIX", "Bearer")
                headers[header_name] = f"{prefix} {self.api_key}".strip()

        async with self.sem:
            last_error = None
            for attempt in range(3):
                try:
                    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                    async with self.session.get(
                        self.url, params=params, headers=headers, timeout=timeout
                    ) as response:
                        if response.status == 429 or response.status >= 500:
                            body = await response.text()
                            raise RuntimeError(
                                f"DataDriv HTTP {response.status}: {body[:200]}"
                            )
                        response.raise_for_status()
                        payload = await response.json(content_type=None)
                        candles = normalize_candles(payload)
                        if len(candles) < 60:
                            raise ValueError(
                                f"{symbol} {interval}: only {len(candles)} valid candles"
                            )
                        return candles
                except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                    last_error = exc
                    if attempt < 2:
                        await asyncio.sleep(0.4 * (2 ** attempt))
                except (ValueError, TypeError, json.JSONDecodeError):
                    raise
            raise RuntimeError(f"{symbol} {interval} fetch failed: {last_error}")


def _atr(c: Sequence[Candle], period: int = 14) -> float:
    trs = []
    for i in range(1, len(c)):
        prev = c[i - 1].close
        trs.append(max(
            c[i].high - c[i].low,
            abs(c[i].high - prev),
            abs(c[i].low - prev),
        ))
    if not trs:
        return 0.0
    return sum(trs[-period:]) / min(period, len(trs))


def _kama(c: Sequence[Candle], period: int = 10, fast_end: float = 2.0 / 3.0, slow_end: float = 2.0 / 31.0) -> Optional[float]:
    """Calculates Kaufman's Adaptive Moving Average (KAMA) for the latest sequence."""
    if len(c) < period + 1:
        return None
    closes = [x.close for x in c]
    
    kama_values = [sum(closes[:period]) / period]
    
    for i in range(period, len(closes)):
        change = abs(closes[i] - closes[i - period])
        volatility = sum(abs(closes[j] - closes[j - 1]) for j in range(i - period + 1, i + 1))
        
        if volatility == 0:
            er = 0.0
        else:
            er = change / volatility
            
        sc = (er * (fast_end - slow_end) + slow_end) ** 2
        prev_kama = kama_values[-1]
        current_kama = prev_kama + sc * (closes[i] - prev_kama)
        kama_values.append(current_kama)
        
    return kama_values[-1] if kama_values else None


def _hurst_exponent(c: Sequence[Candle], max_lag: int = 20) -> float:
    """Calculates Hurst Exponent to classify market regime (Mean-Reverting vs Trending)."""
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
        stdev = math.sqrt(variance) if variance > 0 else 1e-8
        tau.append(stdev)
        
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
        
    hurst = (n * sum_xy - sum_x * sum_y) / denominator
    return float(hurst)


def _support_resistance_zones(c: Sequence[Candle], lookback: int = 50) -> Tuple[Optional[float], Optional[float]]:
    """Identifies ranging local Support and Resistance zones based on recent swing boundaries."""
    if len(c) < lookback:
        return None, None
    recent = c[-lookback:]
    resistance = max(x.high for x in recent)
    support = min(x.low for x in recent)
    return support, resistance


def _swings(c: Sequence[Candle], left: int = 2, right: int = 2):
    highs, lows = [], []
    for i in range(left, len(c) - right):
        if all(c[i].high > c[j].high for j in range(i-left, i)) and \
           all(c[i].high >= c[j].high for j in range(i+1, i+right+1)):
            highs.append((i, c[i].high))
        if all(c[i].low < c[j].low for j in range(i-left, i)) and \
           all(c[i].low <= c[j].low for j in range(i+1, i+right+1)):
            lows.append((i, c[i].low))
    return highs, lows


def _trend(c: Sequence[Candle]) -> str:
    """Simple structure trend from last two confirmed swing highs/lows."""
    highs, lows = _swings(c[-100:])
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    lh = highs[-1][1] < highs[-2][1]
    ll = lows[-1][1] < lows[-2][1]
    if hh and hl:
        return "BULLISH"
    if lh and ll:
        return "BEARISH"
    return "NEUTRAL"


def _liquidity_sweep(c: Sequence[Candle], lookback: int = 20):
    """Sweep = wick beyond prior range followed by close back inside."""
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
    """Close beyond recent local structure in direction of the setup."""
    recent = c[-lookback-1:-1]
    if not recent:
        return False
    if direction == "CALL":
        return c[-1].close > max(x.high for x in recent)
    return c[-1].close < min(x.low for x in recent)


def _fvg(c: Sequence[Candle], direction: str):
    """Three-candle fair value gap; returns latest zone or None."""
    for i in range(len(c) - 1, max(1, len(c) - 12), -1):
        first, third = c[i - 2], c[i]
        if direction == "CALL" and first.high < third.low:
            return (first.high, third.low)
        if direction == "PUT" and first.low > third.high:
            return (third.high, first.low)
    return None


def _approx_volume_profile(c: Sequence[Candle], bins: int = 24):
    """
    Tick-volume approximation, not exchange-traded volume.
    Allocates each candle's volume to its typical price bin.
    """
    lo = min(x.low for x in c)
    hi = max(x.high for x in c)
    if hi <= lo:
        return None
    width = (hi - lo) / bins
    hist = [0.0] * bins
    for x in c:
        typical = (x.high + x.low + x.close) / 3
        idx = min(bins - 1, max(0, int((typical - lo) / width)))
        hist[idx] += max(0.0, x.volume)
    if max(hist) <= 0:
        return None
    poc_idx = max(range(bins), key=lambda i: hist[i])
    return lo + (poc_idx + 0.5) * width


def _analyse(
    pair: str,
    execution: Sequence[Candle],
    confirmation: Sequence[Candle],
    trend_data: Sequence[Candle],
) -> Optional[Signal]:
    if min(len(execution), len(confirmation), len(trend_data)) < 60:
        return None

    last = execution[-1]
    atr = _atr(execution)
    if atr <= 0:
        return None

    candle_range = last.high - last.low
    if candle_range < atr * 0.15 or candle_range > atr * 3.0:
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
    if mid_trend not in (htf_trend, "NEUTRAL"):
        return None

    confirmations = [
        f"{sweep_type} at {swept_level:.5f}",
        "Execution-timeframe MSS",
        f"Higher-timeframe trend: {htf_trend}",
    ]
    score = 3

    # KAMA FILTER
    kama_val = _kama(execution)
    if kama_val is not None:
        confirmations.append(f"KAMA level: {kama_val:.5f}")
        if direction == "CALL" and last.close > kama_val:
            score += 1
        elif direction == "PUT" and last.close < kama_val:
            score += 1

    # HURST EXPONENT REGIME FILTER
    hurst = _hurst_exponent(execution)
    confirmations.append(f"Hurst Exponent: {hurst:.2f}")
    if hurst < 0.5:
        score += 1
    elif hurst > 0.55:
        score += 1

    # RANGING SUPPORT / RESISTANCE ZONES
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
        confirmations.append(f"FVG zone {gap[0]:.5f}–{gap[1]:.5f}")
        score += 2

    poc = _approx_volume_profile(execution[-100:])
    if poc is not None:
        distance = abs(last.close - poc)
        if distance <= atr * 0.75:
            confirmations.append(f"Approx. tick-volume POC confluence {poc:.5f}")
            score += 1

    body = abs(last.close - last.open)
    if body >= atr * 0.5 and (
        (direction == "CALL" and last.close > last.open) or
        (direction == "PUT" and last.close < last.open)
    ):
        confirmations.append("Directional displacement")
        score += 1

    recent = execution[-8:-1]
    ob = None
    for candle in reversed(recent):
        if direction == "CALL" and candle.close < candle.open:
            ob = candle
            break
        if direction == "PUT" and candle.close > candle.open:
            ob = candle
            break
    if ob:
        confirmations.append("Recent opposite-candle order-block proxy")
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
        timeframe=TIMEFRAMES["execution"],
        confirmations=confirmations,
        candle_time=last.timestamp,
        notes=(
            "Rule-based research signal with KAMA, Hurst & S/R. Tick-volume profile is approximate; "
            "broker spread, slippage and feed alignment are not included."
        ),
    )


def analyze_next_candle_target(
    pair: str,
    execution: Sequence[Candle],
    confirmation: Sequence[Candle],
    trend_data: Sequence[Candle]
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function matching main.py import expectations to analyze candles and return signal dictionary.
    """
    signal = _analyse(pair, execution, confirmation, trend_data)
    if signal:
        return signal.to_dict()
    return None


async def scan_pair(client: DataDrivClient, pair: str) -> Tuple[str, Optional[Signal], Optional[str]]:
    """Fetch this pair's timeframes concurrently."""
    try:
        execution, confirmation, trend_data = await asyncio.gather(
            client.candles(pair, TIMEFRAMES["execution"]),
            client.candles(pair, TIMEFRAMES["confirmation"]),
            client.candles(pair, TIMEFRAMES["trend"]),
        )
        signal = _analyse(pair, execution, confirmation, trend_data)
        return pair, signal, None
    except Exception as exc:
        LOG.exception("Scan failed for %s", pair)
        return pair, None, str(exc)


async def scan_all(pairs: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    selected = [p.upper().strip() for p in (pairs or PAIRS) if p.strip()]
    started = time.perf_counter()
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENCY, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        client = DataDrivClient(session)
        results = await asyncio.gather(
            *(scan_pair(client, pair) for pair in selected),
            return_exceptions=True,
        )

    signals: List[Signal] = []
    errors: Dict[str, str] = {}
    for pair, result in zip(selected, results):
        if isinstance(result, Exception):
            errors[pair] = str(result)
            continue
        result_pair, signal, error = result
        if error:
            errors[result_pair] = error
        elif signal:
            signals.append(signal)

    signals.sort(key=lambda x: x.score, reverse=True)
    return {
        "signals": [s.to_dict() for s in signals],
        "errors": errors,
        "scanned": len(selected),
        "signal_count": len(signals),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "status": "OK" if not errors else "PARTIAL",
    }


def format_telegram(result: Dict[str, Any]) -> str:
    signals = result.get("signals", [])
    lines = [
        "📊 FOREX SIGNAL SCAN (KAMA + Hurst + S/R)",
        f"Pairs scanned: {result.get('scanned', 0)}",
        f"Scan time: {result.get('elapsed_seconds', 0)} sec",
        "",
    ]
    if not signals:
        lines.append("NO TRADE — No setup met the configured confirmation filters.")
    else:
        for s in signals[:5]:
            emoji = "🟢" if s["direction"] == "CALL" else "🔴"
            lines.extend([
                f"{emoji} {s['pair']} — {s['direction']}",
                f"Entry: {s['entry']}",
                f"Stop: {s['stop_loss']}",
                f"Target: {s['target']}",
                f"Score: {s['score']} | R:R {s['risk_reward']}",
                "Confirmations: " + ", ".join(s["confirmations"]),
                "",
            ])
    if result.get("errors"):
        lines.append(f"⚠️ Data errors: {len(result['errors'])} pair(s).")
    lines.extend([
        "",
        "⚠️ Research signal only; not a guarantee. Verify broker feed, spread and execution.",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    async def _main():
        result = await scan_all()
        print(json.dumps(result, indent=2))
        print()
        print(format_telegram(result))

    asyncio.run(_main())
