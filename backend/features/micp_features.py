"""MICP = Multi-Indicator Confluence Probability. Features sirf time t tak ke data se bante hain (look-ahead nahi). Label: kya agli poori minute bullish hui. df ki aakhri row = 'snapshot' candle (minute ke pehle SIGNAL_SECOND second)."""
import numpy as np
import pandas as pd

FEATURES = [
    "r1", "r2", "r3", "r5", "body", "up_wick", "lo_wick", "clv",
    "rsi14", "rsi5", "ema9_d", "ema21_d", "ema_slope", "bb_z", "streak",
    "vol_ratio", "tick_vol", "hour_s", "hour_c",
    # rule votes (reversal / momentum) - model decide karta hai inka wazan
    "vote_reversal", "vote_momentum",
    # multi-timeframe (causal, sirf mukammal guzri hui minutes se)
    "m5_trend", "m15_trend", "m5_mom", "m15_mom",
]


def _rsi(close, n):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _streak(color):
    out = np.zeros(len(color))
    s = 0
    for i, c in enumerate(color):
        if c == 0:
            s = 0
        elif i > 0 and np.sign(s) == c:
            s += c
        else:
            s = c
        out[i] = s
    return out


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
    lr = np.log(c).diff()
    sd = lr.rolling(50).std().replace(0, np.nan)

    f = pd.DataFrame(index=df.index)
    for k in (1, 2, 3, 5):
        f[f"r{k}"] = np.log(c).diff(k) / (sd * np.sqrt(k))
    rng = (h - l).replace(0, np.nan)
    f["body"] = (c - o) / atr14
    f["up_wick"] = (h - np.maximum(o, c)) / atr14
    f["lo_wick"] = (np.minimum(o, c) - l) / atr14
    f["clv"] = ((c - l) / rng).fillna(0.5) - 0.5
    f["rsi14"] = (_rsi(c, 14) - 50) / 50
    f["rsi5"] = (_rsi(c, 5) - 50) / 50
    e9, e21 = c.ewm(span=9, adjust=False).mean(), c.ewm(span=21, adjust=False).mean()
    f["ema9_d"] = (c - e9) / atr14
    f["ema21_d"] = (c - e21) / atr14
    f["ema_slope"] = (e9 - e9.shift(3)) / atr14
    ma20, sd20 = c.rolling(20).mean(), c.rolling(20).std().replace(0, np.nan)
    f["bb_z"] = (c - ma20) / sd20
    f["streak"] = _streak(np.sign((c - o).values))
    f["vol_ratio"] = tr.rolling(5).mean() / tr.rolling(50).mean().replace(0, np.nan)
    v = df["volume"].replace(0, np.nan)
    f["tick_vol"] = np.log(v / v.rolling(50).mean())
    t = pd.to_datetime(df["time"], utc=True)
    hr = t.dt.hour + t.dt.minute / 60
    f["hour_s"] = np.sin(2 * np.pi * hr / 24)
    f["hour_c"] = np.cos(2 * np.pi * hr / 24)

    # Rule votes: +1 = agli candle bullish, -1 = bearish, 0 = koi raye nahi
    rev = np.zeros(len(df))
    rev[(f["bb_z"] > 2.2) & (f["rsi5"] > 0.7) & (f["body"] > 0.8)] = -1
    rev[(f["bb_z"] < -2.2) & (f["rsi5"] < -0.7) & (f["body"] < -0.8)] = 1
    f["vote_reversal"] = rev
    mom = np.zeros(len(df))
    ok = f["vol_ratio"].between(0.8, 1.6)
    mom[(f["streak"] >= 3) & (f["ema_slope"] > 0) & ok] = 1
    mom[(f["streak"] <= -3) & (f["ema_slope"] < 0) & ok] = -1
    f["vote_momentum"] = mom

    # Multi-timeframe: M5/M15 ko scaled EMAs se approximate. fc = poori guzri hui minute ki close,
    # shift(1) => sirf wo minutes jo signal se pehle mukammal ho chuki hon (look-ahead nahi).
    fc = (df["full_close"] if "full_close" in df.columns else c).shift(1)
    f["m5_trend"] = (fc.ewm(span=45, adjust=False).mean() - fc.ewm(span=105, adjust=False).mean()) / atr14
    f["m15_trend"] = (fc.ewm(span=90, adjust=False).mean() - fc.ewm(span=210, adjust=False).mean()) / atr14
    f["m5_mom"] = np.log(fc).diff(5) / (sd * np.sqrt(5))
    f["m15_mom"] = np.log(fc).diff(15) / (sd * np.sqrt(15))
    return f[FEATURES]


def build_labels(df: pd.DataFrame) -> pd.Series:
    """1 = agli candle (poori minute :00-:59) bullish, 0 = bearish, NaN = doji / gap / aakhri row."""
    if "full_open" in df.columns and "full_close" in df.columns:
        o, c = df["full_open"].shift(-1), df["full_close"].shift(-1)
    else:
        o, c = df["open"].shift(-1), df["close"].shift(-1)
    nxt = np.sign(c - o)
    y = pd.Series(np.where(nxt > 0, 1.0, np.where(nxt < 0, 0.0, np.nan)), index=df.index)
    t = pd.to_datetime(df["time"], utc=True)
    y[(t.shift(-1) - t) != pd.Timedelta(minutes=1)] = np.nan   # agli row asli agli minute nahi
    y.iloc[-1] = np.nan
    return y
```[cite: 23]

Aap isay save karke Render par dobara **Manual Deploy -> Clear build cache & deploy** kar dein, ab yeh module not found error bhi khatam ho jayega aur bot chal padega!
