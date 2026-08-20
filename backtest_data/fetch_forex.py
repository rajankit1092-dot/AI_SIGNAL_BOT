"""
Fetches historical forex/commodity OHLCV data for backtesting the MT5
variant of the strategy.

Uses the Yahoo Finance chart API directly via `requests` rather than the
`yfinance` package - yfinance's internal HTTP client (curl_cffi) doesn't
respect this environment's proxy/CA configuration and fails outright, while
plain `requests` (which does) reaches the same endpoint fine.

Yahoo only serves ~60 days of intraday (15m/60m) history, versus the ~120
days available for crypto via KuCoin - a smaller sample, noted in the
backtest report.

Gold has no working Yahoo spot ticker (XAUUSD=X / XAU=X both 404); GC=F
(COMEX gold futures) is used as a close proxy - it tracks spot gold tightly
but isn't identical, which matters for exact SL/TP price levels later.
"""
import os
import time
import requests
import pandas as pd

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "XAUUSD": "GC=F",  # gold futures proxy - see module docstring
}

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_chart(yahoo_symbol, interval, rng):
    r = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}",
        params={"interval": interval, "range": rng},
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()["chart"]["result"]
    if not data:
        raise ValueError(f"No data for {yahoo_symbol} {interval} {rng}")

    result = data[0]
    ts = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(ts, unit="s", utc=True).tz_localize(None),
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"],
        "volume": quote["volume"],
    })
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    return df


def main():
    for name, yahoo_symbol in SYMBOLS.items():
        print(f"Fetching {name} ({yahoo_symbol}) ...")

        df15 = fetch_chart(yahoo_symbol, "15m", "60d")
        df15.to_csv(os.path.join(OUT_DIR, f"{name}_15m.csv"), index=False)
        print(f"  15m: {len(df15)} bars ({df15['timestamp'].iloc[0]} to {df15['timestamp'].iloc[-1]})")
        time.sleep(1)

        df1h = fetch_chart(yahoo_symbol, "60m", "2y")
        df1h.to_csv(os.path.join(OUT_DIR, f"{name}_1h.csv"), index=False)
        print(f"  1h: {len(df1h)} bars ({df1h['timestamp'].iloc[0]} to {df1h['timestamp'].iloc[-1]})")
        time.sleep(1)

        # Yahoo has no native 4h interval - resample from 1h.
        df4h = (
            df1h.set_index("timestamp")
            .resample("4h")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
            .reset_index()
        )
        df4h.to_csv(os.path.join(OUT_DIR, f"{name}_4h.csv"), index=False)
        print(f"  4h: {len(df4h)} bars (resampled)")


if __name__ == "__main__":
    main()
