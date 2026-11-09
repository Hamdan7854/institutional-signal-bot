"""OANDA JSON candles -> DataFrame, S5 -> '40-second snapshot' minute candles, tick builder."""
import numpy as np
import pandas as pd


def candles_to_df(raw):
    if not raw:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume", "complete", "spread"])
    times = [c["time"] for c in raw]
    mid = [c["mid"] for c in raw]
    spread = []
    for c in raw:
        if "bid" in c and "ask" in c:
            spread.append(float(c["ask"]["c"]) - float(c["bid"]["c"]))
        else:
            spread.append(np.nan)
    df = pd.DataFrame({
        "time": pd.to_datetime(times, utc=True),
        "open": [float(m["o"]) for m in mid],
        "high": [float(m["h"]) for m in mid],
        "low": [float(m["l"]) for m in mid],
        "close": [float(m["c"]) for m in mid],
        "volume": [float(c.get("volume", 0)) for c in raw],
        "complete": [bool(c.get("complete", True)) for c in raw],
        "spread": spread,
    })
    return df.drop_duplicates("time").sort_values("time").reset_index(drop=True)


def build_minutes(s5: pd.DataFrame, cutoff: int = 40) -> pd.DataFrame:
    """S5 candles se har minute ke liye: open/high/low/close/volume = sirf minute ke pehle `cutoff` second ka SNAPSHOT (jo signal ke waqt maloom hota hai) full_open/full_close = poore minute ki open/close (label aur resolution ke liye) Model isi snapshot par train hota hai, taake backtest live timing se match kare."""
    d = s5[s5["complete"]].copy() if "complete" in s5 else s5.copy()
    if d.empty:
        return pd.DataFrame()
    d["minute"] = d["time"].dt.floor("min")
    d["sec"] = (d["time"] - d["minute"]).dt.total_seconds()
    full = d.groupby("minute").agg(full_open=("open", "first"), full_close=("close", "last"))
    snap = d[d["sec"] < cutoff].groupby("minute").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"))
    out = snap.join(full, how="inner").reset_index().rename(columns={"minute": "time"})
    return out


class TickCandleBuilder:
    """Streaming ticks (time, price) se M1 candles banata hai (optional, abhi main loop use nahi karta)."""

    def __init__(self):
        self.cur, self.done = None, []

    def add_tick(self, ts: pd.Timestamp, price: float):
        minute = ts.floor("min")
        if self.cur is None or minute != self.cur["time"]:
            if self.cur is not None:
                self.done.append(self.cur)
            self.cur = dict(time=minute, open=price, high=price, low=price, close=price, volume=1)
        else:
            self.cur["high"] = max(self.cur["high"], price)
            self.cur["low"] = min(self.cur["low"], price)
            self.cur["close"] = price
            self.cur["volume"] += 1

    def pop_completed(self):
        d, self.done = self.done, []
        return d
