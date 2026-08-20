"""
One-off manual order: places a REAL order right now on the given symbol,
bypassing strategy.generate_signal() entirely. Exists to test the
order-placement code path itself (lot sizing, order_send, SL/TP, filling
mode) directly - DRY_RUN in mt5_config.py never exercises this, since
analyze_symbol() returns before calling place_order() while DRY_RUN is True,
so that code has never actually executed even once.

Reuses the exact same calc_lot_size()/place_order() from mt5_bot.py, so a
successful run here validates the automated bot's order mechanics too.
SL/TP are computed the same ATR-based way generate_signal() would, just with
the direction forced rather than waiting for real entry conditions to align.

Ignores DRY_RUN, MAX_DAILY_TRADES, MAX_CONSECUTIVE_LOSSES, and the
"already have an open position" check that the automated loop applies -
this is a deliberate manual override, not a signal. Only ever run this
against a DEMO account. Every run places a new real order.

Usage: python mt5_manual_order.py [SYMBOL_NAME] [BUY|SELL]
  e.g. python mt5_manual_order.py XAUUSD BUY   (defaults shown)
"""
import sys

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

import mt5_config as cfg
from indicators import add_indicators
from mt5_bot import fetch_data, calc_lot_size, place_order


def main(symbol_name="XAUUSD", direction="BUY"):
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not installed / not on Windows - see mt5_setup.md")

    symbol = cfg.MT5_SYMBOLS.get(symbol_name) or cfg.MT5_SYMBOLS_OPTIONAL.get(symbol_name)
    if symbol is None:
        raise RuntimeError(f"{symbol_name} not in mt5_config.py's MT5_SYMBOLS or MT5_SYMBOLS_OPTIONAL")

    init_kwargs = {"login": cfg.MT5_LOGIN, "password": cfg.MT5_PASSWORD, "server": cfg.MT5_SERVER}
    if cfg.MT5_TERMINAL_PATH:
        init_kwargs["path"] = cfg.MT5_TERMINAL_PATH
    if not mt5.initialize(**init_kwargs):
        raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")

    try:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Could not select {symbol} in Market Watch - check the symbol name")

        existing = mt5.positions_get(symbol=symbol)
        if existing and any(p.magic == cfg.MAGIC_NUMBER for p in existing):
            print(f"WARNING: bot already has an open {symbol} position - placing another anyway (manual override)")

        df = add_indicators(fetch_data(symbol, cfg.TIMEFRAMES["entry"]))
        atr = df.iloc[-1]["atr"]

        tick = mt5.symbol_info_tick(symbol)
        entry = tick.ask if direction == "BUY" else tick.bid

        if direction == "BUY":
            sl = entry - atr * cfg.ATR_MULTIPLIER
            tp1 = entry + (entry - sl) * 1.5
        else:
            sl = entry + atr * cfg.ATR_MULTIPLIER
            tp1 = entry - (sl - entry) * 1.5

        signal = {"signal": direction, "entry": round(entry, 2), "sl": round(sl, 2), "tp1": round(tp1, 2)}
        print(f"Placing MANUAL {direction} {symbol}: entry={signal['entry']} sl={signal['sl']} tp1={signal['tp1']}")

        result = place_order(symbol, signal)
        if result is None:
            print("Order was NOT placed - see the error above.")
        else:
            print(f"Order result: retcode={result.retcode} deal={result.deal} order={result.order}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    symbol_arg = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    direction_arg = sys.argv[2].upper() if len(sys.argv) > 2 else "BUY"
    main(symbol_arg, direction_arg)
