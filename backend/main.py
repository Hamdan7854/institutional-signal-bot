"""Entry point. python main.py run -> live loop (OANDA demo data + Telegram signals + commands) python main.py backtest -> OANDA history par walk-forward report (40-sec snapshot timing) python main.py selftest -> synthetic data par pipeline check (API ki zaroorat nahi) Timing: har minute ke SIGNAL_SECOND (default :40) tak ka data dekh kar signal; Telegram par candle ke aakhri ~20 second mein jata hai; TRADE ENTRY agli candle ke :00 par."""
import os
import sys

# ---- Preflight: missing / ghalat naam wali files ka saaf paigham (Render logs mein nazar aayega) ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_REQUIRED = ["config.py", "market_data.py", "strategy.py", "telegram_bot.py", "health.py",
             "data/candle_builder.py", "data/oanda_client.py", "storage/database.py",
             "features/micp_features.py", "prediction/micp_engine.py"]
_missing = [f for f in _REQUIRED if not os.path.exists(os.path.join(_HERE, f))]
if _missing:
    print("\n❌ YE FILES MISSING HAIN (naam bilkul exact hona chahiye, chhote huroof, underscore, .py):")
    for f in _missing:
        print(" -", f)
    print("📂 Is folder mein asal files:", sorted(os.listdir(_HERE)), "\n")
    sys.exit(1)

# Render port binding ke liye health server foran start karein
import health
health.start()

import threading
import time
import numpy as np
import pandas as pd
import config
import telegram_bot as tg
from storage.database import DB
from strategy import Strategy
from prediction.micp_engine import walk_forward


def sleep_to_second(sec):
    now = time.time()
    time.sleep((sec - (now % 60)) % 60 or 0.0)


def report_text(symbol, rep, thr):
    return (f"[{symbol}] Walk-forward OOS ({config.SIGNAL_SECOND}s snapshot): trades={rep['trades']} "
            f"hit={rep['hit_rate']:.2%} WilsonLB={rep['wilson_lb']:.2%} breakeven={rep['breakeven']:.2%} "
            f"thr={thr} => {'EDGE OK' if rep['passed'] else 'NO EDGE (bot chup rahega)'}")


class Bot:
    def __init__(self, client, db):
        from market_data import MarketData
        self.client, self.db = client, db
        self.books = {}            # sym -> dict(md, st, retraining, spread)
        self.manual_pause = False
        self.started = time.time()
        for sym in config.INSTRUMENTS:
            md = MarketData(client, sym)
            print(sym, "history minutes:", md.bootstrap())
            st = Strategy(sym, db)
            rep = st.retrain(md.df)
            tg.send(report_text(sym, rep, st.engine.thr))
            self.books[sym] = dict(md=md, st=st, retraining=False, spread=(None, None))

    # ---------- Telegram commands ----------
    def cmd_status(self):
        up = (time.time() - self.started) / 3600
        lines = [f"🤖 MICP Bot | uptime {up:.1f}h | manual_pause={self.manual_pause}",
                 f"Signal @:{config.SIGNAL_SECOND:02d}, entry @:00 | payout {config.PAYOUT:.0%} breakeven {config.BREAKEVEN:.2%}",
                 f"MTF_FILTER={config.MTF_FILTER} SPREAD_FILTER={config.SPREAD_FILTER} (max {config.MAX_SPREAD_PIPS} pips)"]
        for sym, b in self.books.items():
            st, eng = b["st"], b["st"].engine
            n, wins = self.db.recent_stats(100)
            tot, w, l = self.db.totals(sym)
            age = (time.time() - eng.trained_at) / 3600 if eng.trained_at else float("nan")
            sp = b["spread"]
            ls = self.db.last_signal(sym)
            lines += [
                f"\n[{sym}] edge={'OK' if eng.has_edge else 'NO'} thr={eng.thr} trained {age:.1f}h ago",
                f"OOS: hit={eng.report['hit_rate']:.2%} LB={eng.report['wilson_lb']:.2%} trades={eng.report['trades']}" if eng.report else "OOS: n/a",
                f"Live: total={tot} W={w} L={l} | last100: {wins}/{n}" + (f" ({wins / n:.1%})" if n else ""),
                f"Spread now={sp[0] if sp[0] is None else round(sp[0], 2)} med={sp[1] if sp[1] is None else round(sp[1], 2)} pips",
                f"Last decision: {st.last_reason}" + (f" | PAUSED: {st.paused_reason}" if st.paused_reason else ""),
                f"Last signal: {ls}" if ls else "Last signal: none",
            ]
        return "\n".join(lines)

    def cmd_edge(self):
        return "\n".join(report_text(s, b["st"].engine.report, b["st"].engine.thr)
                         for s, b in self.books.items() if b["st"].engine.report)

    def cmd_pause(self):
        self.manual_pause = True
        return "⏸ Signals pause kar diye gaye. /resume se dobara shuru karein."

    def cmd_resume(self):
        self.manual_pause = False
        return "▶️ Signals dobara shuru."

    def cmd_signal(self):
        if self.manual_pause:
            return "⏸ Bot paused hai. Pehle /resume karein."
        results = ["🔍 Manual Scan Results:"]
        found = 0
        for sym, b in self.books.items():
            try:
                df, sp_now, sp_med = b["md"].snapshot()
                b["spread"] = (sp_now, sp_med)
                if df.empty:
                    results.append(f"• {sym}: Data nahi mila")
                    continue
                sig = b["st"].on_candle(df, sp_now, sp_med)
                if sig:
                    found += 1
                    entry_t = pd.Timestamp(sig.target_time).strftime("%H:%M:00")
                    tg.send(f"📶 {sym} {sig.direction} | 1 min\nENTRY: {entry_t} UTC\nConfidence: {sig.confidence:.1%}")
                    results.append(f"• {sym}: 🟢 SIGNAL ({sig.direction})")
                else:
                    results.append(f"• {sym}: ⏳ No edge")
            except Exception as e:
                results.append(f"• {sym}: Error")
        if found == 0:
            results.append("\n❌ Filhal kisi pair par edge nahi mili.")
        return "\n".join(results)

    def cmd_help(self):
        return "/signal - abhi scan kar ke signal check karein\n/status - bot ki halat\n/edge - walk-forward report\n/pause - signals band\n/resume - signals shuru"

    def handlers(self):
        return {"/signal": self.cmd_signal, "/status": self.cmd_status, "/edge": self.cmd_edge, "/pause": self.cmd_pause,
                "/resume": self.cmd_resume, "/help": self.cmd_help, "/start": self.cmd_help}

    # ---------- core loop ----------
    def resolve_pending(self, sym, df):
        if df.empty:
            return
        cur_min = df["time"].iloc[-1]
        for sid, direction, target, entry in self.db.pending(sym):
            t = pd.Timestamp(target)
            row = df[df["time"] == t]
            if t < cur_min and not row.empty:
                o, c = float(row["full_open"].iloc[0]), float(row["full_close"].iloc[0])
                if c == o:
                    self.db.resolve(sid, c, None)
                    tg.send(f"➖ DRAW {sym} {direction} (open=close)")
                    continue
                win = (c > o) == (direction == "CALL")
                self.db.resolve(sid, c, win)
                tg.send(f"{'✅ WIN' if win else '❌ LOSS'} {sym} {direction} | open {o:.5f} close {c:.5f}")
            elif t < cur_min - pd.Timedelta(minutes=10):
                self.db.resolve(sid, entry, None)

    def _retrain_bg(self, sym):
        b = self.books[sym]
        try:
            b["md"].bootstrap()
            rep = b["st"].retrain(b["md"].df)
            tg.send("🔄 Retrained. " + report_text(sym, rep, b["st"].engine.thr))
        except Exception as e:
            print("retrain error:", e)
        finally:
            b["retraining"] = False

    def tick(self):
        for sym, b in self.books.items():
            try:
                df, sp_now, sp_med = b["md"].snapshot()
                b["spread"] = (sp_now, sp_med)
                if df.empty:
                    continue
                self.resolve_pending(sym, df)
                eng = b["st"].engine
                if (not b["retraining"] and time.time() - eng.trained_at > config.RETRAIN_EVERY_MIN * 60):
                    b["retraining"] = True
                    threading.Thread(target=self._retrain_bg, args=(sym,), daemon=True).start()
                if self.manual_pause:
                    b["st"].last_reason = "manual_pause"
                    continue
                sec_now = time.time() % 60
                if sec_now > config.LATEST_SIGNAL_SECOND:
                    b["st"].last_reason = f"too_late ({sec_now:.0f}s)"
                    continue
                sig = b["st"].on_candle(df, sp_now, sp_med)
                if sig:
                    self.db.add_signal(sym, sig.direction, sig.confidence, sig.target_time, sig.entry)
                    entry_t = pd.Timestamp(sig.target_time).strftime("%H:%M:00")
                    tg.send(f"📶 {sym} {sig.direction} | 1 min\n"
                            f"ENTRY: {entry_t} UTC (candle open par)\n"
                            f"Confidence {sig.confidence:.1%} | spread {sp_now:.2f} pips\n"
                            f"(Pehle DEMO par test karein.)")
            except Exception as e:
                print("loop error:", sym, e)

    def run_forever(self):
        tg.start_listener(self.handlers())
        tg.send(f"✅ Bot live. /signal command se abhi scan kar sakte hain. /help dekhein.")
        while True:
            sleep_to_second(config.SIGNAL_SECOND + config.FETCH_DELAY)
            self.tick()


def run():
    from data.oanda_client import OandaClient
    Bot(OandaClient(), DB()).run_forever()


def backtest():
    from data.oanda_client import OandaClient
    from market_data import MarketData
    client = OandaClient()
    for sym in config.INSTRUMENTS:
        md = MarketData(client, sym)
        md.bootstrap()
        rep = walk_forward(md.df, verbose=True)
        print(report_text(sym, rep, None))


# ------------------------------------------------------------------ selftest
def synthetic_minutes(n, edge=0.0, seed=1):
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    noise = rng.normal(0, 1e-4, n)
    for i in range(1, n):
        r[i] = -edge * r[i - 1] + noise[i]
    close = 1.1 + np.cumsum(r)
    open_ = np.r_[1.1, close[:-1]]
    hi = np.maximum(open_, close) + np.abs(rng.normal(0, 3e-5, n))
    lo = np.minimum(open_, close) - np.abs(rng.normal(0, 3e-5, n))
    t = pd.date_range("2025-01-06", periods=n, freq="min", tz="UTC")
    return pd.DataFrame(dict(time=t, open=open_, high=hi, low=lo, close=close,
                             volume=rng.integers(20, 200, n).astype(float)))


def synthetic_s5(minutes, seed=2):
    rng = np.random.default_rng(seed)
    n = minutes * 12
    c = 1.1 + np.cumsum(rng.normal(0, 3e-5, n))
    o = np.r_[1.1, c[:-1]]
    t = pd.date_range("2025-01-06", periods=n, freq="5s", tz="UTC")
    return pd.DataFrame(dict(time=t, open=o, high=np.maximum(o, c) + 1e-5, low=np.minimum(o, c) - 1e-5,
                             close=c, volume=rng.integers(1, 30, n).astype(float), complete=True))


def selftest():
    from data.candle_builder import build_minutes
    from strategy import spread_ok
    ok = True
    s5 = synthetic_s5(50)
    m = build_minutes(s5, 40)
    row, first = m.iloc[10], s5.iloc[120:132]
    chk = (np.isclose(row["open"], first["open"].iloc[0]) and np.isclose(row["close"], first["close"].iloc[7])
           and np.isclose(row["full_close"], first["close"].iloc[11]) and np.isclose(row["high"], first["high"].iloc[:8].max()))
    print("snapshot builder correct:", bool(chk)); ok &= bool(chk)
    sf = (spread_ok(0.8, 0.7) and not spread_ok(2.5, 0.7) and not spread_ok(1.2, 0.3) and not spread_ok(None, None))
    print("spread filter correct:", sf); ok &= sf
    for label, edge in (("RANDOM WALK (edge=0)", 0.0), ("STRONG synthetic mean-reversion", 0.35)):
        rep = walk_forward(synthetic_minutes(40000, edge), train=6000, test=2000)
        print(f"{label}: trades={rep['trades']} hit={rep['hit_rate']:.2%} WilsonLB={rep['wilson_lb']:.2%} "
              f"breakeven={rep['breakeven']:.2%} passed={rep['passed']}")
    rep = walk_forward(build_minutes(synthetic_s5(14000), 40), train=6000, test=2000)
    print(f"S5 snapshot pipeline (random): trades={rep['trades']} hit={rep['hit_rate']:.2%} passed={rep['passed']}")
    print("SELFTEST", "OK" if ok else "FAILED")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": run, "backtest": backtest, "selftest": selftest}[mode]()
