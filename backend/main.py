import time
from config import PAIRS
from market_data import MarketDataProvider
from strategy import InstitutionalStrategyEngine
from telegram_bot import send_telegram_signal

def run_scanner():
    print("🚀 Starting Major Forex Pairs Scanner Engine...")
    provider = MarketDataProvider()

    for pair in PAIRS:
        df = provider.fetch_recent_candles(pair)
        engine = InstitutionalStrategyEngine(df)
        signal = engine.evaluate_signal(pair)

        print(f"[{pair}] Result: {signal['action']} | Score: {signal.get('score', 0)} | Reason: {signal['reason']}")

        if signal["action"] in ["CALL", "PUT"]:
            send_telegram_signal(signal)

if __name__ == "__main__":
    run_scanner()
