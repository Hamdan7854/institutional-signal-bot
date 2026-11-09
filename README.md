MICP Signal Bot (OANDA demo data -> Telegram)

Har minute ke :40 second tak ka data dekh kar agli candle ki direction ka probability model chalata hai.
Signal Telegram par candle ke aakhri ~20 second mein jata hai, entry agli candle ke :00 par.
Bot sirf tab signal deta hai jab walk-forward out-of-sample natija payout ke breakeven se statistically upar ho.
Warna chup rehta hai ("NO EDGE").


Setup

pip install -r requirements.txt
export OANDA_TOKEN=...                 # OANDA practice API token
export TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=...
python main.py selftest                # API ke baghair pipeline check
python main.py backtest                # asal OANDA data par report (:40 snapshot timing)
python main.py run                     # live (demo)

Features


Timing: SIGNAL_SECOND=40 (config). Model isi 40-second snapshot par train/test hota hai, taake backtest live se match kare.

Spread filter: abhi ka spread <= MAX_SPREAD_PIPS (1.5) aur <= 2.5 x recent median, warna signal block.

Multi-timeframe: M5/M15 trend+momentum features (causal). MTF_FILTER=align se signal sirf M15 trend ki direction mein.

Telegram commands: /status /edge /pause /resume /help (sirf TELEGRAM_CHAT_ID ki chat).

Kill-switch: live 100 trades mein hit-rate breakeven se neeche ho to signals band.

Har 12 ghante background mein retrain + gate dobara check.


Zaroori baatein


Koi guaranteed edge nahi. Pehle backtest dekhein; "NO EDGE" aaye to yehi sahi jawab hai.

Signal OANDA spot-FX data par hai. Broker ke OTC/synthetic pairs par ye kaam nahi karega.

Signal :41-:43 par aata hai, aap ke paas ~15 second hain. Broker ka entry price/payout nateeja badal sakta hai.

Demo par 500+ trades test karein. Token/keys kabhi GitHub par commit na karein.

