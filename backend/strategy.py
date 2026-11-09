"""Strategy layer: MICP probability + hard filters + kill-switch. Signal tab hi aata hai jab SAB shartein poori hon: 1. Edge gate pass (walk-forward out-of-sample Wilson lower bound > breakeven) 2. Model confidence >= calibrated threshold (aur MTF filter, agar on ho) 3. Trading session ghante ke andar 4. Volatility normal 5. Spread filter pass (abhi ka spread <= MAX_SPREAD_PIPS aur <= SPREAD_MULT x median) 6. Cooldown khatam, live kill-switch trigger nahi hua """
from dataclasses import dataclass
import numpy as np
import config
from prediction.micp_engine import MICPEngine
from features.micp_features import build_features


@dataclass
class Signal:
    symbol: str
    direction: str
    confidence: float
    entry: float
    target_time: object     # wo minute jis ki direction par bet hai (entry :00 par)


def spread_ok(now, median):
    if not config.SPREAD_FILTER:
        return True
    if now is None or np.isnan(now):
        return False                       # spread maloom nahi => conservative block
    if now > config.MAX_SPREAD_PIPS:
        return False
    if median is not None and not np.isnan(median) and median > 0 and now > config.SPREAD_MULT * median:
        return False
    return True


class Strategy:
    def __init__(self, symbol, db):
        self.symbol, self.db = symbol, db
        self.engine = MICPEngine()
        self.cooldown = 0
        self.paused_reason = None
        self.last_reason = "starting"

    def retrain(self, df, verbose=False):
        eng = MICPEngine()
        rep = eng.fit(df, verbose=verbose)
        self.engine = eng                  # atomic swap (background thread se bhi safe)
        return rep

    def kill_switch(self):
        n, wins = self.db.recent_stats(config.KILL_SWITCH_MIN_TRADES)
        if n >= config.KILL_SWITCH_MIN_TRADES and wins / n < config.BREAKEVEN:
            return f"Live hit-rate {wins / n:.1%} < breakeven {config.BREAKEVEN:.1%} ({n} trades)"
        return None

    def on_candle(self, df, spread_now=None, spread_med=None):
        """Har minute ke SIGNAL_SECOND par call karein. df ki aakhri row = chalti candle ka snapshot."""
        if self.cooldown > 0:
            self.cooldown -= 1
            self.last_reason = "cooldown"
            return None
        why = self.kill_switch()
        self.paused_reason = why
        if why:
            self.last_reason = "kill_switch"
            return None
        if not self.engine.has_edge:
            self.last_reason = "NO_EDGE (gate fail)"
            return None
        if len(df) < config.MIN_LIVE_ROWS:
            self.last_reason = "insufficient_data"
            return None
        last_t = df["time"].iloc[-1]
        if last_t.hour not in config.TRADE_HOURS_UTC:
            self.last_reason = "outside_session"
            return None
        vr = build_features(df.tail(200))["vol_ratio"].iloc[-1]
        if not (0.6 <= vr <= 2.0):
            self.last_reason = "volatility_filter"
            return None
        if not spread_ok(spread_now, spread_med):
            self.last_reason = f"spread_filter (now={spread_now}, med={spread_med})"
            return None
        direction, conf, reason = self.engine.predict_last(df)
        self.last_reason = reason
        if direction is None:
            return None
        self.cooldown = config.COOLDOWN_CANDLES
        return Signal(self.symbol, direction, conf, float(df["close"].iloc[-1]),
                      last_t + np.timedelta64(1, "m"))
```[cite: 21]

Is file ko update karke commit karne ke baad Render par **Manual Deploy -> Clear build cache & deploy** karein, aapka deploy bina kisi error ke successfully build ho jayega!
