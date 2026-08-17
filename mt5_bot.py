"""
MT5 demo-account connector for the signal strategy (forex/gold variant).

IMPORTANT: this can only run on Windows (or Wine) with the MetaTrader5
terminal installed and logged into your account - the MetaTrader5 Python
package talks to a locally running terminal via IPC, not over the network.
It cannot be run from the sandbox this was written in, so it has not been
tested end-to-end against a real terminal. Run it in DRY_RUN mode first
(the default in mt5_config.py) and watch the logs/Telegram alerts for at
least a few dozen signals before flipping DRY_RUN to False.

See mt5_setup.md for step-by-step setup instructions.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # allows --check-config / lint to run off-Windows

import mt5_config as cfg
from indicators import add_indicators
from strategy import generate_signal

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt5_bot_state.json")

TIMEFRAME_MAP = {
    "M15": "TIMEFRAME_M15",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
}


def mt5_timeframe(name):
    return getattr(mt5, TIMEFRAME_MAP[name])


# =========================
# STATE (daily trade count / consecutive losses - MT5 itself doesn't
# track these per-strategy, so a small local file does)
# =========================

def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            state = json.load(f)
    else:
        state = {}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("date") != today:
        state = {"date": today, "trades_today": 0, "consecutive_losses": 0, "last_bar": {}}

    state.setdefault("last_bar", {})
    return state


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


# =========================
# TELEGRAM (optional, reuses the crypto bot's env vars)
# =========================

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


# =========================
# MT5 DATA
# =========================

def fetch_data(symbol, timeframe_name, count=300):
    rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe(timeframe_name), 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates for {symbol} {timeframe_name}: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


# =========================
# POSITION SIZING
# =========================

def calc_lot_size(symbol, entry, sl):
    info = mt5.symbol_info(symbol)
    account = mt5.account_info()
    if info is None or account is None:
        return None

    risk_amount = account.balance * (cfg.RISK_PER_TRADE_PERCENT / 100)
    price_distance = abs(entry - sl)
    if price_distance <= 0 or info.trade_tick_size <= 0:
        return None

    ticks_at_risk = price_distance / info.trade_tick_size
    loss_per_lot = ticks_at_risk * info.trade_tick_value
    if loss_per_lot <= 0:
        return None

    lots = risk_amount / loss_per_lot

    # snap to the broker's allowed volume step/min/max
    step = info.volume_step or 0.01
    lots = round(lots / step) * step
    lots = max(info.volume_min, min(info.volume_max, lots))
    return round(lots, 2)


# =========================
# ORDER PLACEMENT
# =========================

def place_order(symbol, signal):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"No tick for {symbol}, skipping order")
        return None

    is_buy = signal["signal"] == "BUY"
    price = tick.ask if is_buy else tick.bid
    lot = calc_lot_size(symbol, signal["entry"], signal["sl"])
    if not lot:
        print(f"Could not size a lot for {symbol}, skipping order")
        return None

    # MT5 positions carry a single SL/TP - TP1 is used as the position's
    # take-profit. TP2/TP3 from the signal are informational only in this
    # version (no partial-close scaling implemented yet).
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": signal["sl"],
        "tp": signal["tp1"],
        "deviation": 20,
        "magic": cfg.MAGIC_NUMBER,
        "comment": "ai-signal-bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"order_send returned None for {symbol}: {mt5.last_error()}")
        return None
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed for {symbol}: retcode={result.retcode} comment={result.comment}")
        return None

    print(f"Order placed: {symbol} {signal['signal']} lot={lot} sl={signal['sl']} tp={signal['tp1']}")
    return result


# =========================
# ANALYZE ONE SYMBOL
# =========================

def analyze_symbol(name, symbol, state):
    df = add_indicators(fetch_data(symbol, cfg.TIMEFRAMES["entry"]))
    df_1h = add_indicators(fetch_data(symbol, cfg.TIMEFRAMES["confirmation"]))
    df_4h = add_indicators(fetch_data(symbol, cfg.TIMEFRAMES["trend"]))

    latest_bar_time = str(df.iloc[-1]["timestamp"])
    if state["last_bar"].get(name) == latest_bar_time:
        return  # already analyzed this bar, nothing new since last poll

    state["last_bar"][name] = latest_bar_time

    signal = generate_signal(df, df_1h, df_4h, cfg=cfg)
    if signal is None:
        return

    if state["trades_today"] >= cfg.MAX_DAILY_TRADES:
        print(f"{name}: signal found but MAX_DAILY_TRADES reached, skipping")
        return

    if state["consecutive_losses"] >= cfg.MAX_CONSECUTIVE_LOSSES:
        print(f"{name}: signal found but MAX_CONSECUTIVE_LOSSES reached, skipping")
        return

    existing = mt5.positions_get(symbol=symbol)
    if existing and any(p.magic == cfg.MAGIC_NUMBER for p in existing):
        print(f"{name}: already have an open position, skipping")
        return

    message = (
        f"{'[DRY RUN] ' if cfg.DRY_RUN else ''}{signal['signal']} {name}\n"
        f"Entry: {signal['entry']}  SL: {signal['sl']}\n"
        f"TP1: {signal['tp1']}  TP2: {signal['tp2']}  TP3: {signal['tp3']}\n"
        f"Confidence: {signal['confidence']}%"
    )
    print(message)
    send_telegram(message)

    if cfg.DRY_RUN:
        return

    result = place_order(symbol, signal)
    if result is not None:
        state["trades_today"] += 1


# =========================
# MAIN LOOP
# =========================

def run_once(state):
    all_symbols = dict(cfg.MT5_SYMBOLS)
    for name, symbol in all_symbols.items():
        try:
            if not mt5.symbol_select(symbol, True):
                print(f"Could not select {symbol} in Market Watch - check the symbol name in mt5_config.py")
                continue
            analyze_symbol(name, symbol, state)
        except Exception as e:
            print(f"Error analyzing {name}: {e}")


def main():
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed / not on Windows - see mt5_setup.md")

    if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD,
                           server=cfg.MT5_SERVER, path=cfg.MT5_TERMINAL_PATH):
        raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")

    print(f"Connected to MT5. DRY_RUN={cfg.DRY_RUN}. Symbols: {list(cfg.MT5_SYMBOLS)}")
    if cfg.DRY_RUN:
        print("Running in DRY RUN mode - no real orders will be placed.")

    state = load_state()

    try:
        while True:
            state = load_state()  # reload in case the day rolled over
            run_once(state)
            save_state(state)
            time.sleep(60)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
