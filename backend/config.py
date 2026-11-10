"""Saari settings yahin hain. Secrets hamesha environment variables se aayen, kabhi GitHub par push na karein."""
import os

# ---- OANDA (sirf PRACTICE/demo account) -----------------------------------
OANDA_API_KEY = os.getenv("OANDA_API_KEY", "") or os.getenv("OANDA_TOKEN", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT", "practice")  # practice | live

# ---- Telegram --------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_BOT_CHAT_ID = os.getenv("TELEGRAM_BOT_CHAT_ID", "") or os.getenv("TELEGRAM_CHAT_ID", "")  # sirf is chat ki commands sunni jati hain

# ---- Market ----------------------------------------------------------------
INSTRUMENTS = os.getenv("INSTRUMENTS", "EUR_USD").split(",")
HISTORY_MINUTES = int(os.getenv("HISTORY_MINUTES", "2000"))  # Startup timeout bachane ke liye optimized
TRADE_HOURS_UTC = list(range(7, 17))   # London + NY overlap

# ---- Signal timing ---------------------------------------------------------
# Candle ke 40wen second tak ka data dekh kar signal; entry agli candle ke :00 par.
SIGNAL_SECOND = int(os.getenv("SIGNAL_SECOND", "40"))   # 40 = candle ke aakhri 20 second ka aaghaz
FETCH_DELAY = 1.0                                       # S5 candle complete hone ka intezar (sec)
LATEST_SIGNAL_SECOND = 56                               # is ke baad signal nahi bhejna (bahut late)
MIN_LIVE_ROWS = 300                                     # live features ke liye kam az kam minutes

# ---- Binary option economics ----------------------------------------------
PAYOUT = float(os.getenv("PAYOUT", "0.85"))
BREAKEVEN = 1.0 / (1.0 + PAYOUT)                        # 0.85 par ~54.05%

# ---- MICP engine -----------------------------------------------------------
TRAIN_SIZE = int(os.getenv("TRAIN_SIZE", "10000"))
TEST_SIZE = int(os.getenv("TEST_SIZE", "2500"))
CAL_FRACTION = 0.25
L2 = 5.0
MIN_OOS_TRADES = int(os.getenv("MIN_OOS_TRADES", "250"))
WILSON_Z = 1.64
RETRAIN_EVERY_MIN = int(os.getenv("RETRAIN_EVERY_MIN", "720"))

# ---- Multi-timeframe -------------------------------------------------------
# MTF features hamesha model ko diye jate hain (M5/M15 trend, momentum).
# MTF_FILTER="align" ho to signal sirf M15 trend ki direction mein aayega (backtest gate is ko bhi naapta hai).
MTF_FILTER = os.getenv("MTF_FILTER", "off")             # off | align

# ---- Spread filter ---------------------------------------------------------
SPREAD_FILTER = os.getenv("SPREAD_FILTER", "on") == "on"
MAX_SPREAD_PIPS = float(os.getenv("MAX_SPREAD_PIPS", "1.5"))
SPREAD_MULT = float(os.getenv("SPREAD_MULT", "2.5"))    # abhi ka spread <= 2.5 x recent median

# ---- Safety ----------------------------------------------------------------
KILL_SWITCH_MIN_TRADES = 100
COOLDOWN_CANDLES = 2
DB_PATH = os.getenv("DB_PATH", "signals.db")
```[cite: 16]

Isay save karne ke baad Render par service foran baghair kisi timeout ke boot ho kar live ho jayegi aur aap Telegram par aram se commands use kar sakenge!
