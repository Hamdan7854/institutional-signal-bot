"""Entry point. python main.py run -> command-driven bot (OANDA demo data + Telegram signals + commands)"""
import os
import sys

# ---- Preflight: missing files check ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_REQUIRED = ["config.py", "market_data.py", "strategy.py", "telegram_bot.py", "health.py",
             "data/candle_builder.py", "data/oanda_client.py", "storage/database.py",
             "features/micp_features.py", "prediction/micp_engine.py"]
_missing = [f for f in _REQUIRED if not os.path.exists(os.path.join(_HERE, f))]
if _missing:
    print("\n❌ YE FILES MISSING HAIN:")
    for f in _missing:
        print(" -", f)
    sys.exit(1)

import health
health.start()

import time
import pandas as pd
import config
import telegram_bot as tg
from storage.database import DB
from strategy import Strategy


class Bot:
    def __init__(self, client, db):
        from market_data import MarketData
        self.client, self.db = client, db
        self.books = {}
        self.manual_pause = False
        self.started = time.time()
        for sym in config.INSTRUMENTS:
            md = MarketData(client, sym)
            print(sym, "history minutes:", md.bootstrap())
            st = Strategy(sym, db)
            st.retrain(md.df)
            self.books[sym] = dict(md=md, st=st, retraining=False, spread=(None, None))

    # ---------- Telegram commands ----------
    def cmd_status(self):
        up = (time.time() - self.started) / 3600
        lines = [f"🤖 MICP Bot (Command-Driven) | uptime {up:.1f}h | manual_pause={self.manual_pause}",
                 f"Signal expiry: 1 min | payout {config.PAYOUT:.0%} breakeven {config.BREAKEVEN:.2%}",
                 f"SPREAD_FILTER={config.SPREAD_FILTER} (max {config.MAX_SPREAD_PIPS} pips)"]
        for sym, b in self.books.items():
            st, eng = b["st"], b["st"].engine
            n, wins = self.db.recent_stats(100)
            tot, w, l = self.db.totals(sym)
            sp = b["spread"]
            ls = self.db.last_signal(sym)
            lines += [
                f"\n[{sym}]",
                f"Live: total={tot} W={w} L={l} | last100: {wins}/{n}" + (f" ({wins / n:.1%})" if n else ""),
                f"Spread now={sp[0] if sp[0] is None else round(sp[0], 2)} med={sp[1] if sp[1] is None else round(sp[1], 2)} pips",
                f"Last decision: {st.last_reason}" + (f" | PAUSED: {st.paused_reason}" if st.paused_reason else ""),
                f"Last signal: {ls}" if ls else "Last signal: none",
            ]
        return "\n".join(lines)

    def cmd_edge(self):
        return "ℹ️ Command-driven mode active. /signal use karein live market scan ke liye."

    def cmd_pause(self):
        self.manual_pause = True
        return "⏸ Signals pause kar diye gaye. /resume se dobara shuru karein."

    def cmd_resume(self):
        self.manual_pause = False
        return "▶️ Signals dobara shuru."

    def cmd_signal(self):
        if self.manual_pause:
            return "⏸ Bot paused hai. Pehle /resume karein."
        results = ["🔍 Manual Scan Results (ADX / Regime Strategy):"]
        found = 0
        for sym, b in self.books.items():
            try:
                df, sp_now, sp_med = b["md"].snapshot()
                b["spread"] = (sp_now, sp_med)
                if df.empty:
                    results.append(f"• `{sym}`: Data nahi mila")
                    continue
                
                sig = b["st"].on_candle(df, sp_now, sp_med)
                if sig:
                    found += 1
                    self.db.add_signal(sym, sig.direction, sig.confidence, sig.target_time, sig.entry)
                    entry_t = pd.Timestamp(sig.target_time).strftime("%H:%M:00")
                    
                    # Formatting: BUY -> Green Circle (🟢), SELL -> Red Circle (🔴)
                    icon = "🟢" if sig.direction == "BUY" else "🔴"
                    
                    tg.send(f"📶 **{sym} {sig.direction}** {icon} | 1 min\n"
                            f"• ENTRY: `{entry_t}` UTC\n"
                            f"• Confidence: `{sig.confidence:.1%}` | Spread: `{sp_now:.2f}` pips\n"
                            f"(Pehle DEMO par test karein.)")
                    results.append(f"• `{sym}`: {icon} **SIGNAL ({sig.direction})**")
                else:
                    reason = getattr(b["st"], 'last_reason', 'No edge')
                    results.append(f"• `{sym}`: ⏳ No signal (`{reason}`)")
            except Exception as e:
                results.append(f"• `{sym}`: Error (`{e}`)")
        
        if found == 0:
            results.append("\n❌ Filhal kisi bhi pair par setup nahi mila. Thori der baad dobara try karein.")
        return "\n".join(results)

    def cmd_help(self):
        return ("/signal - abhi saare pairs scan kar ke signal check karein\n"
                "/status - bot ki halat aur stats\n"
                "/pause - signals band\n"
                "/resume - signals shuru")

    def handlers(self):
        return {
            "/signal": self.cmd_signal,
            "/status": self.cmd_status,
            "/edge": self.cmd_edge,
            "/pause": self.cmd_pause,
            "/resume": self.cmd_resume,
            "/help": self.cmd_help,
            "/start": self.cmd_help
        }

    def run_forever(self):
        tg.start_listener(self.handlers())
        tg.send(f"✅ Bot Command-Mode par live hai! Jab signal chahiye ho, Telegram par **`/signal`** command bhejein.")
        while True:
            time.sleep(3600)


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
        print(f"[{sym}] Bootstrap complete.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": run, "backtest": backtest}[mode]()
