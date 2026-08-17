"""
Live forward paper-test for the MT5 forex/gold strategy variant.

Unlike backtest_data/forex_backtest.py (which replays HISTORICAL data),
this fetches CURRENT market data on each run and evaluates the actual
production strategy.generate_signal() + mt5_config.py against it, going
forward in real time from whenever it's first run. It never touches MT5
and never places real orders - it's a paper-trading journal, meant to
accumulate genuine forward evidence (as opposed to backtested/in-sample
evidence) while MT5 setup happens separately on the user's machine.

Runs anywhere with outbound HTTPS to Yahoo Finance's chart API (does not
need MT5 or Windows) - designed to be invoked repeatedly (e.g. hourly) by
something external, since it re-fetches fresh data and picks up wherever
the journal file left off each time rather than looping internally.
"""
import json
import os

os.environ.setdefault("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")

import pandas as pd  # noqa: E402
import requests  # noqa: E402

from indicators import add_indicators  # noqa: E402
from strategy import generate_signal  # noqa: E402
import mt5_config as cfg  # noqa: E402

JOURNAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_test_journal.json")

# Same Yahoo tickers / spread assumptions as backtest_data/fetch_forex.py
# and forex_backtest.py, for GBPUSD + XAUUSD (mt5_config.MT5_SYMBOLS).
YAHOO_SYMBOLS = {"GBPUSD": "GBPUSD=X", "XAUUSD": "GC=F"}
SPREADS = {"GBPUSD": 0.00016, "XAUUSD": 0.35}

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_chart(yahoo_symbol, interval, rng):
    r = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}",
        params={"interval": interval, "range": rng},
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    result = r.json()["chart"]["result"]
    if not result:
        raise ValueError(f"No data for {yahoo_symbol}")
    result = result[0]
    quote = result["indicators"]["quote"][0]
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_localize(None),
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"],
        "volume": quote["volume"],
    })
    return df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)


def load_journal():
    if os.path.exists(JOURNAL_PATH):
        with open(JOURNAL_PATH) as f:
            return json.load(f)
    return {"open_positions": {}, "closed_trades": [], "last_bar_seen": {}}


def save_journal(j):
    with open(JOURNAL_PATH, "w") as f:
        json.dump(j, f, indent=2, default=str)


def send_telegram(message):
    if not getattr(cfg, "SEND_TELEGRAM_ALERTS", False):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return
        from telegram import Bot
        Bot(token=token).send_message(chat_id=chat_id, text=message)
    except Exception as e:
        print(f"Telegram alert failed: {e}")


def check_open_position(name, pos, df15):
    """Same conservative same-bar-touch handling and spread modeling as
    backtest_data/backtest.py's simulate_trades - walks bars after entry
    looking for SL or TP1 touched, SL wins ties."""
    half_spread = SPREADS[name] / 2
    entry_time = pd.Timestamp(pos["entry_time"])
    is_buy = pos["signal"] == "BUY"

    for _, bar in df15[df15["timestamp"] > entry_time].iterrows():
        if is_buy:
            hit_sl = bar["low"] <= pos["sl"] + half_spread
            hit_tp = bar["high"] >= pos["tp1"] + half_spread
        else:
            hit_sl = bar["high"] >= pos["sl"] - half_spread
            hit_tp = bar["low"] <= pos["tp1"] - half_spread

        if hit_sl:
            return "LOSS", -1.0, str(bar["timestamp"])
        if hit_tp:
            return "WIN", 1.5, str(bar["timestamp"])

    return None, None, None


def run_once():
    journal = load_journal()
    events = []

    for name, yahoo_symbol in YAHOO_SYMBOLS.items():
        df15 = add_indicators(fetch_chart(yahoo_symbol, "15m", "5d"))
        df1h = add_indicators(fetch_chart(yahoo_symbol, "60m", "5d"))
        df4h_raw = (
            fetch_chart(yahoo_symbol, "60m", "20d")
            .set_index("timestamp")
            .resample("4h")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
            .reset_index()
        )
        df4h = add_indicators(df4h_raw)

        if name in journal["open_positions"]:
            pos = journal["open_positions"][name]
            outcome, r, exit_time = check_open_position(name, pos, df15)
            if outcome:
                pos.update(outcome=outcome, r=r, exit_time=exit_time)
                journal["closed_trades"].append(pos)
                del journal["open_positions"][name]
                msg = f"[PAPER TEST] {name} trade CLOSED {outcome} ({r:+.1f}R)"
                events.append(msg)
                send_telegram(msg)
            continue  # one open paper position per symbol, matches backtest assumption

        latest_closed_time = str(df15.iloc[-2]["timestamp"])  # -1 may be a still-forming bar
        if journal["last_bar_seen"].get(name) == latest_closed_time:
            continue
        journal["last_bar_seen"][name] = latest_closed_time

        signal = generate_signal(df15.iloc[:-1], df1h, df4h, cfg=cfg)
        if signal is None:
            continue

        journal["open_positions"][name] = {
            "signal": signal["signal"],
            "entry": signal["entry"],
            "sl": signal["sl"],
            "tp1": signal["tp1"],
            "tp2": signal["tp2"],
            "tp3": signal["tp3"],
            "confidence": signal["confidence"],
            "entry_time": latest_closed_time,
        }
        msg = (
            f"[PAPER TEST] {name} OPENED {signal['signal']} entry={signal['entry']} "
            f"sl={signal['sl']} tp1={signal['tp1']} confidence={signal['confidence']}%"
        )
        events.append(msg)
        send_telegram(msg)

    save_journal(journal)

    closed = journal["closed_trades"]
    if closed:
        wins = sum(1 for t in closed if t["outcome"] == "WIN")
        win_rate = wins / len(closed) * 100
        avg_r = sum(t["r"] for t in closed) / len(closed)
        summary = f"Paper-test so far: {len(closed)} closed trades, {win_rate:.1f}% win, avg {avg_r:+.2f}R"
    else:
        open_n = len(journal["open_positions"])
        summary = f"Paper-test so far: 0 closed trades yet ({open_n} open)"

    return events, summary


if __name__ == "__main__":
    events, summary = run_once()
    for e in events:
        print(e)
    print(summary)
