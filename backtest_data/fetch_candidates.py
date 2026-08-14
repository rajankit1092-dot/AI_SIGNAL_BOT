import ccxt
from fetch_data import fetch_full_history, OUT_DIR, TIMEFRAMES, DAYS_BACK
import os

CANDIDATES = ["XRP/USDT", "ADA/USDT", "DOGE/USDT", "LTC/USDT", "AVAX/USDT", "LINK/USDT"]

exchange = ccxt.kucoin({"enableRateLimit": True, "requests_trust_env": True})
exchange.load_markets()

for symbol in CANDIDATES:
    for timeframe in TIMEFRAMES:
        print(f"Fetching {symbol} {timeframe} ...")
        df = fetch_full_history(exchange, symbol, timeframe, DAYS_BACK)
        fname = f"{symbol.replace('/', '_')}_{timeframe}.csv"
        path = os.path.join(OUT_DIR, fname)
        df.to_csv(path, index=False)
        print(f"  saved {len(df)} bars -> {path}")
