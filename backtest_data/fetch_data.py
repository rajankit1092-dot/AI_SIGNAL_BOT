"""
Fetches historical OHLCV data for backtesting.

Binance (the bot's live exchange) is geo-blocked (HTTP 451) from this
environment, so KuCoin is used as a data source instead. It carries the same
pairs (BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT) with a comparable history depth
and liquidity profile, which is sufficient for strategy backtesting purposes.
"""
import os
import time
import ccxt
import pandas as pd

SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]
TIMEFRAMES = ["15m", "1h", "4h"]
DAYS_BACK = 120
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def fetch_full_history(exchange, symbol, timeframe, days_back):
    ms_per_bar = exchange.parse_timeframe(timeframe) * 1000
    since = exchange.milliseconds() - days_back * 24 * 60 * 60 * 1000

    all_bars = []
    while True:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1500)
        if not batch:
            break
        all_bars.extend(batch)
        last_ts = batch[-1][0]
        next_since = last_ts + ms_per_bar
        if next_since <= since:
            break
        since = next_since
        if len(batch) < 1500:
            break
        time.sleep(exchange.rateLimit / 1000)

    df = pd.DataFrame(all_bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def main():
    exchange = ccxt.kucoin({"enableRateLimit": True, "requests_trust_env": True})
    exchange.load_markets()

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            print(f"Fetching {symbol} {timeframe} ...")
            df = fetch_full_history(exchange, symbol, timeframe, DAYS_BACK)
            fname = f"{symbol.replace('/', '_')}_{timeframe}.csv"
            path = os.path.join(OUT_DIR, fname)
            df.to_csv(path, index=False)
            print(f"  saved {len(df)} bars -> {path} "
                  f"({df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]})")


if __name__ == "__main__":
    main()
