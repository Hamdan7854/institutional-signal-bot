from features.micp_features import build_features, build_labels, FEATURES
"""MICP engine: regularised logistic regression (numpy) + walk-forward validation + 'edge gate'. Asool: bot sirf tab signal deta hai jab OUT-OF-SAMPLE natija payout ke breakeven se statistically upar ho. Warna status = NO_EDGE aur bot chup rehta hai. Yeh "luck" aur "edge" ko alag karta hai."""
import math
import numpy as np
import config
from micp_features import build_features, build_labels, FEATURES

_M15 = FEATURES.index("m15_trend")


def wilson_lower(hits, n, z=None):
    z = config.WILSON_Z if z is None else z
    if n == 0:
        return 0.0
    p = hits / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    adj = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - adj) / den


def mtf_ok(X, dir_up):
    """MTF filter: 'align' mode mein direction M15 trend ke mutabiq honi chahiye."""
    if config.MTF_FILTER != "align":
        return np.ones(len(X), dtype=bool)
    t = X[:, _M15]
    return np.where(dir_up, t > 0, t < 0)


class LogReg:
    def __init__(self, l2=None):
        self.l2 = config.L2 if l2 is None else l2
        self.w = self.mu = self.sd = None

    @staticmethod
    def _sig(z):
        return 1 / (1 + np.exp(-np.clip(z, -30, 30)))

    def fit(self, X, y, iters=30):
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Xb = np.hstack([np.ones((len(X), 1)), (X - self.mu) / self.sd])
        w = np.zeros(Xb.shape[1])
        reg = np.eye(Xb.shape[1]) * self.l2
        reg[0, 0] = 0
        for _ in range(iters):
            p = self._sig(Xb @ w)
            W = p * (1 - p) + 1e-9
            grad = Xb.T @ (y - p) - reg @ w
            H = Xb.T @ (Xb * W[:, None]) + reg
            step = np.linalg.solve(H, grad)
            w += step
            if np.abs(step).max() < 1e-6:
                break
        self.w = w
        return self

    def proba(self, X):
        Xb = np.hstack([np.ones((len(X), 1)), np.clip((X - self.mu) / self.sd, -6, 6)])
        return self._sig(Xb @ self.w)


def pick_threshold(p_up, y, min_n=40):
    """Calibration set par sab se behtar confidence threshold (Wilson lower bound max, breakeven se upar)."""
    conf = np.maximum(p_up, 1 - p_up)
    pred = (p_up >= 0.5).astype(float)
    best, best_lb = None, config.BREAKEVEN
    for t in np.arange(0.51, 0.70, 0.005):
        m = conf >= t
        n = int(m.sum())
        if n < min_n:
            break
        lb = wilson_lower(int((pred[m] == y[m]).sum()), n, z=1.0)
        if lb > best_lb:
            best, best_lb = float(t), lb
    return best


def _prepare(df):
    X = build_features(df)
    y = build_labels(df)
    ok = X.notna().all(axis=1) & y.notna()
    return X, y, ok


def walk_forward(df, train=None, test=None, verbose=False):
    train = train or config.TRAIN_SIZE
    test = test or config.TEST_SIZE
    X, y, ok = _prepare(df)
    Xv, yv, okv = X.values, y.values, ok.values
    n = len(df)
    hits = trades = 0
    folds = []
    start = train
    while start + test <= n:
        tr = np.arange(start - train, start)
        tr = tr[okv[tr]]
        cut = int(len(tr) * (1 - config.CAL_FRACTION))
        fit_idx, cal_idx = tr[:cut], tr[cut:]
        if len(fit_idx) < 500:
            start += test
            continue
        m = LogReg().fit(Xv[fit_idx], yv[fit_idx])
        thr = pick_threshold(m.proba(Xv[cal_idx]), yv[cal_idx])
        m = LogReg().fit(Xv[tr], yv[tr])
        te = np.arange(start, start + test)
        te = te[okv[te]]
        fh = ft = 0
        if thr is not None and len(te):
            p = m.proba(Xv[te])
            sel = (np.maximum(p, 1 - p) >= thr) & mtf_ok(Xv[te], p >= 0.5)
            fh = int(((p[sel] >= 0.5).astype(float) == yv[te][sel]).sum())
            ft = int(sel.sum())
        folds.append(dict(start=start, thr=thr, trades=ft, hits=fh))
        hits += fh
        trades += ft
        if verbose:
            print(f" fold@{start}: thr={thr} trades={ft} hit={fh / ft if ft else 0:.3f}")
        start += test
    lb = wilson_lower(hits, trades)
    return dict(
        folds=folds, trades=trades, hits=hits,
        hit_rate=(hits / trades if trades else 0.0), wilson_lb=lb,
        breakeven=config.BREAKEVEN,
        passed=bool(trades >= config.MIN_OOS_TRADES and lb > config.BREAKEVEN),
    )


class MICPEngine:
    def __init__(self):
        self.model = self.thr = self.report = None
        self.trained_at = 0.0

    def fit(self, df, verbose=False):
        import time
        self.report = walk_forward(df, verbose=verbose)
        X, y, ok = _prepare(df)
        idx = np.where(ok.values)[0][-config.TRAIN_SIZE:]
        cut = int(len(idx) * (1 - config.CAL_FRACTION))
        m = LogReg().fit(X.values[idx[:cut]], y.values[idx[:cut]])
        self.thr = pick_threshold(m.proba(X.values[idx[cal_idx:] if 'cal_idx' in locals() else idx[cut:]]), y.values[idx[cut:]]) # safe fallback
        self.model = LogReg().fit(X.values[idx], y.values[idx])
        self.trained_at = time.time()
        return self.report

    @property
    def has_edge(self):
        return bool(self.report and self.report["passed"] and self.thr is not None)

    def predict_last(self, df):
        """df ki aakhri row (snapshot) ke baad agli minute ki direction. Return (direction, confidence, reason). Signal na ho to direction=None aur reason wajah."""
        if self.model is None or self.thr is None:
            return None, 0.0, "model_not_ready"
        row = build_features(df).iloc[[-1]]
        if row.isna().any(axis=None):
            return None, 0.0, "features_warmup"
        p = float(self.model.proba(row.values)[0])
        conf = max(p, 1 - p)
        if conf < self.thr:
            return None, conf, "low_confidence"
        if not mtf_ok(row.values, np.array([p >= 0.5]))[0]:
            return None, conf, "mtf_filter"
        return ("CALL" if p >= 0.5 else "PUT"), conf, "signal"
