"""History (S5 -> snapshot minutes) aur live snapshot + spread."""
import numpy as np
import pandas as pd
from candle_builder import candles_to_df, build_minutes
import config


def pip_size(symbol):
    return 0.01 if "JPY" in symbol else 0.0001


class MarketData:
    def __init__(self, client, instrument):
        self.client, self.instrument = client, instrument
        self.df = pd.DataFrame()      # training history (snapshot minutes)

    def bootstrap(self, minutes=None):
        n = (minutes or config.HISTORY_MINUTES) * 12          # 12 S5 candles per minute
        s5 = candles_to_df(self.client.history(self.instrument, n, "S5"))
        m = build_minutes(s5, config.SIGNAL_SECOND)
        self.df = m.iloc[:-1].reset_index(drop=True)          # aakhri (adhoori) minute hata do
        return len(self.df)

    def snapshot(self):
        """Abhi ka live snapshot: df (aakhri row = chalti candle ke pehle SIGNAL_SECOND second), spread (pips) abhi ka aur median. Spread MBA price se aata hai."""
        raw = self.client.candles(self.instrument, "S5", count=5000, price="MBA")
        s5 = candles_to_df(raw)
        s5 = s5[s5["complete"]]
        df = build_minutes(s5, config.SIGNAL_SECOND)
        ps = pip_size(self.instrument)
        sp = (s5["spread"] / ps).dropna()
        now = float(sp.iloc[-1]) if len(sp) else None
        med = float(sp.tail(720).median()) if len(sp) else None
        return df, now, med
