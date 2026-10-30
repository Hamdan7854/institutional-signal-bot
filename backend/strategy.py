"""
strategy.py — Dual-Condition ICT/SMC & Quantitative Forex Signal Scanner (Golden Limits Applied)
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

DEFAULT_PAIRS = [
    "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", 
    "USDCAD", "USDCHF", "NZDUSD", "EURJPY", 
    "GBPJPY", "EURGBP"
]

TIMEFRAMES = {
    "execution": "M1",    # 1 minute execution
    "confirmation": "M5", # 5 minutes structure
    "trend": "M15",       # 15 minutes trend regime
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
    """OANDA V20 REST API Client for real-time data."""

    def __init__(self):
        self.api_key = os.getenv("OANDA_API_KEY", "").strip()
        self.account_id = os.getenv("OANDA_ACCOUNT_ID", "").strip()
        self.base_url = "https://api-fxpractice.oanda.com/v3"

    def _fetch_candles(self, symbol: str, granularity: str) -> List[Candle]:
        if not self.api_key:
            raise RuntimeError("OANDA_API_KEY environment variable missing")

        oanda_symbol = f"{symbol[:3]}_{symbol[3:]}"
        url = f"{self.base_url}/instruments/{oanda_symbol}/candles"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept-Datetime-Format": "UNIX"
        }
        params = {
            "granularity": granularity,
            "count": 100,
            "price": "MBA"
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
            vol = float(rc.get("volume", 0))
            out.append(Candle(
                timestamp=float(rc.get("time", 0)),
                open=float(mid.get("o", 0)),
                high=float(mid.get("h", 0)),
                low=float(mid.get("l", 0)),
                close=float(mid.get("c", 0)),
                volume=vol
            ))
        return out

    async def fetch_timeframes(self, symbol: str) -> Tuple[List[Candle], List[Candle], List[Candle]]:
        loop = asyncio.get_running_loop()
        execution = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["execution"])
        await asyncio.sleep(0.05)
        confirmation = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["confirmation"])
        await asyncio.sleep(0.05)
        trend_data = await loop.run_in_executor(None, self._fetch_candles, symbol, TIMEFRAMES["trend"])

        if len(execution) < 40 or len(confirmation) < 40 or len(trend_data) < 40:
            raise ValueError(f"{symbol}: Insufficient candles received from OANDA")

        return execution, confirmation, trend_data


# --- Indicator & SMC Calculations ---

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


def _hurst_exponent(c: Sequence[Candle], max_lag: int = 20) -> float:
    closes = [x.close for x in c[-100:]]
    if len(closes) < 30:
        return 0.5
    lags = range(2, max_lag)
    tau = []
    for lag in lags:
        pp = [closes[i + lag] - closes[i] for i in range(len(closes) - lag)]
        std = math.sqrt(sum(x ** 2 for x in pp) / len(pp)) if pp else 0.00001
        tau.append(std if std > 0 else 0.00001)
    reg = [math.log(t) for t in tau]
    x_vals = [math.log(l) for l in lags]
    mean_x = sum(x_vals) / len(x_vals)
    mean_y = sum(reg) / len(reg)
    num = sum((x_vals[i] - mean_x) * (reg[i] - mean_y) for i in range(len(x_vals)))
    den = sum((x_vals[i] - mean_x) ** 2 for i in range(len(x_vals)))
    hurst = (num / den) if den != 0 else 0.5
    return max(0.0, min(1.0, hurst))


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


def _mss(c: Sequence[Candle], direction: str, lookback: int = 15) -> bool:
    recent = c[-lookback-1:-1]
    if not recent:
        return False
    if direction == "BUY":
        return c[-1].close > max(x.high for x in recent)
    return c[-1].close < min(x.low for x in recent)


def _detect_fvg(c: Sequence[Candle]) -> Tuple[bool, Optional[float]]:
    if len(c) < 3:
        return False, None
    c1, _, c3 = c[-3], c[-2], c[-1]
    if c3.low > c1.high:
        return True, c1.high
    elif c3.high < c1.low:
        return True, c1.low
    return False, None


def _detect_order_block(c: Sequence[Candle]) -> Tuple[bool, Optional[float]]:
    if len(c) < 5:
        return False, None
    last = c[-1]
    if last.close > last.open:
        for i in range(-2, -6, -1):
            if c[i].close < c[i].open:
                return True, c[i].low
    else:
        for i in range(-2, -6, -1):
            if c[i].close > c[i].open:
                return True, c[i].high
    return False, None


def _volume_profile(c: Sequence[Candle], bins: int = 10) -> Tuple[float, float, float]:
    if not c:
        return 0.0, 0.0, 0.0
    lows = [x.low for x in c[-50:]]
    highs = [x.high for x in c[-50:]]
    min_p, max_p = min(lows), max(highs)
    if min_p == max_p:
        return min_p, min_p, min_p
    step = (max_p - min_p) / bins
    v_bins = [0.0] * bins
    for candle in c[-50:]:
        bin_idx = min(int((candle.close - min_p) / step), bins - 1)
        v_bins[bin_idx] += candle.volume if candle.volume > 0 else 1.0
    max_v = max(v_bins)
    poc_idx = v_bins.index(max_v)
    poc = min_p + (poc_idx + 0.5) * step
    return poc, poc, poc


def _support_resistance_zones(c: Sequence[Candle], lookback: int = 50) -> Tuple[float, float]:
    recent = c[-lookback:]
    sup = min(x.low for x in recent)
    res = max(x.high for x in recent)
    return sup, res


# --- Main Strategy Logic with Dual-Condition Grouping & Golden Limits ---

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
    direction = "BUY" if last.close >= prev.close else "SELL"

    confirmations = []

    # --- CONDITION GROUP 1: ICT/SMC & Volume Profile ---
    sweep_data = _liquidity_sweep(execution)
    sweep_passed = bool(sweep_data)
    mss_passed = _mss(execution, direction)
    fvg_found, _ = _detect_fvg(execution)
    ob_found, _ = _detect_order_block(execution)
    smc_passed = fvg_found or ob_found
    
    poc, _, _ = _volume_profile(execution)
    vp_passed = abs(last.close - poc) <= atr * 2.0

    smc_score = sum([sweep_passed, mss_passed, smc_passed, vp_passed])
    condition_1_met = (smc_score >= 2)

    # --- CONDITION GROUP 2: Golden Limits (Hurst, S/R, KAMA, ATR) ---
    # 1. Hurst Exponent Threshold (>= 0.55 for solid trend persistence)
    hurst_val = _hurst_exponent(execution)
    hurst_passed = (hurst_val >= 0.55)

    # 2. Support & Resistance Confluence Zone (Exact bounce zone within 1.0 * ATR)
    sup, res = _support_resistance_zones(execution)
    sr_passed = False
    if direction == "BUY" and abs(last.low - sup) <= atr * 1.0:
        sr_passed = True
    elif direction == "SELL" and abs(last.high - res) <= atr * 1.0:
        sr_passed = True

    # 3. KAMA Distance (Price within 1.5 * ATR of KAMA level)
    kama_val = _kama(execution)
    kama_passed = False
    if kama_val is not None and abs(last.close - kama_val) <= atr * 1.5:
        if direction == "BUY" and last.close >= kama_val:
            kama_passed = True
        elif direction == "SELL" and last.close <= kama_val:
            kama_passed = True

    # 4. ATR Volatility Golden Range (0.00008 to 0.00025)
    atr_passed = (0.00008 <= atr <= 0.00025)

    quant_score = sum([hurst_passed, sr_passed, kama_passed, atr_passed])
    condition_2_met = (quant_score >= 2)

    # --- Requirement Check: Condition 1, Condition 2, or Both ---
    if not condition_1_met and not condition_2_met:
        return None

    # Construct explicit reasons for Telegram
    if condition_1_met and condition_2_met:
        match_reason = "🔥 BOTH Condition 1 & Condition 2 Matched!"
    elif condition_1_met:
        match_reason = "⚡ Condition 1 (ICT/SMC & Volume Profile) Matched"
    else:
        match_reason = "📊 Condition 2 (Golden Limits Quant) Matched"

    confirmations.append(match_reason)
    if sweep_passed: confirmations.append("✔ SMC Liquidity Sweep Confirmed")
    if mss_passed: confirmations.append("✔ Market Structure Shift (MSS)")
    if smc_passed: confirmations.append("✔ FVG / Order Block Active")
    if vp_passed: confirmations.append(f"✔ Volume Profile POC ({poc:.5f})")
    if hurst_passed: confirmations.append(f"✔ Hurst Exponent ({hurst_val:.2f})")
    if sr_passed: confirmations.append("✔ S/R Zone Confluence")
    if kama_passed: confirmations.append(f"✔ KAMA Trend Alignment ({kama_val:.5f})")
    if atr_passed: confirmations.append(f"✔ ATR Volatility Stable ({atr:.5f})")

    total_matched = smc_score + quant_score
    confidence_score = int((total_matched / 8) * 100)
    confidence_score = max(50, min(confidence_score, 98))

    # 5-Decimal Calculations for Next Candle Target
    entry = round(float(last.close), 5)
    if direction == "BUY":
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
        score=total_matched,
        confidence=confidence_score,
        entry=entry,
        stop_loss=stop,
        target=target,
        risk_reward=rr,
        timeframe="1m",
        confirmations=confirmations,
        candle_time=last.timestamp,
        notes=match_reason,
    )


async def analyze_next_candle_target(pair: str) -> Optional[Dict[str, Any]]:
    client = OandaClient()
    try:
        execution, confirmation, trend_data = await client.fetch_timeframes(pair)
        signal = _analyse(pair, execution, confirmation, trend_data)
        if signal:
            return signal.to_dict()
    except Exception as exc:
        LOG.exception("OANDA analysis error on pair %s: %s", pair, exc)
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
        await asyncio.sleep(0.08)

    signals.sort(key=lambda x: x["confidence"], reverse=True)
    return {
        "signals": signals,
        "errors": errors,
        "scanned": len(selected),
        "signal_count": len(signals),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "status": "OK" if not errors else "PARTIAL",
    }
