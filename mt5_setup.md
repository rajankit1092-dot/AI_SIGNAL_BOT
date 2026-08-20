# Running the strategy on your MT5 demo account

`mt5_bot.py` connects to a locally installed MetaTrader5 terminal, runs the
same indicator/signal logic as the crypto bot, and can place demo orders.
It **only runs on the Windows machine where your MT5 terminal is
installed and logged in** - the MetaTrader5 Python package talks to the
terminal over local IPC, not the network, so this can't run in a cloud
session and was never tested end-to-end against a real terminal. Treat the
first runs as a real test of the integration code itself, not just the
strategy.

## Why forex/gold, and why this is less validated than the crypto bot

The crypto strategy (BTC/ETH/SOL) was backtested on ~120 days of real
exchange data with full volume, and a clear diagnostic (a direction-split
breakdown) backed the decision to drop BNB. The forex/gold version here:

- Only has ~60-84 days of history available (Yahoo Finance's intraday
  data limit), a smaller and more regime-sensitive sample.
- Runs on Yahoo's spot-forex feed, which reports **zero volume** for
  every bar - VWAP and volume-based filters had to be disabled
  (`ENABLE_VWAP_FILTER`/`ENABLE_VOLUME_FILTER = False` in
  `mt5_config.py`) because they're mathematically undefined (NaN) without
  real volume. MT5 itself provides real tick_volume live, but that path
  was never backtested here, so don't re-enable those filters without a
  fresh backtest against real tick data.
- The spread costs used in backtesting (`backtest_data/forex_backtest.py`
  `SPREADS` dict) are estimates, not your actual broker's spread - check
  your broker's real spread on GBPUSD/XAUUSD and compare.
- GBPUSD/XAUUSD were kept as the default symbols and EURUSD/USDJPY were
  left disabled (net-negative in backtesting), but that call is based on
  a much shorter window and no root-cause diagnosis, unlike BNB in the
  crypto bot - it's a weaker signal, treat it as provisional.

None of this means it won't work - it means you should run it in dry-run
mode and actually look at what it does before trusting it with orders,
even demo ones.

## Setup

1. **Install MetaTrader5 terminal** (Windows) if you haven't, and log into
   your demo account through the terminal UI at least once so the
   credentials are known-good.

2. **Copy this repo** to the Windows machine (or clone it there directly).

3. **Install dependencies** (in addition to `requirements.txt`):
   ```
   pip install -r requirements.txt -r requirements-mt5.txt
   ```

4. **Set up credentials** - copy `mt5.env.example` to `mt5.env` and fill
   in your demo account's login number, password, and server name (found
   in MT5 under File > Login to Trade Account, or in the email your
   broker sent you). `mt5.env` is gitignored - never commit it.

5. **Check your symbol names.** Open MT5's Market Watch, find your
   broker's exact names for GBPUSD and Gold (often just `GBPUSD` and
   `XAUUSD`, but brokers commonly suffix these, e.g. `GBPUSDm`,
   `GBPUSD.a`, `XAUUSD.raw`). Edit `MT5_SYMBOLS` in `mt5_config.py` to
   match exactly - a wrong name fails silently to `symbol_select` and that
   symbol gets skipped every cycle.

6. **Run it in dry-run mode** (the default - `DRY_RUN = True` in
   `mt5_config.py`):
   ```
   python mt5_bot.py
   ```
   It polls every 60 seconds, only acts on a new closed 15m candle, and
   logs (and optionally Telegram-alerts, if `SEND_TELEGRAM_ALERTS = True`
   and you've set `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` in `.env`) every
   signal it would have taken, with the entry/SL/TP1-3 it computed and the
   lot size it would have used - without calling `order_send`.

7. **Watch it for a while.** Let it run across a range of market
   conditions (at minimum several days covering both quiet and active
   sessions) and sanity-check the logged signals - do the entry/SL/TP
   levels look reasonable for the instrument? Is it skipping symbols it
   shouldn't be (wrong symbol name)? Does the lot sizing look right for
   your account balance and `RISK_PER_TRADE_PERCENT`?

8. **Go live on demo.** Once you're satisfied, set `DRY_RUN = False` in
   `mt5_config.py` and restart. Orders will now actually post via
   `mt5.order_send()` to your demo account. Watch the first few trades
   fill in the MT5 terminal directly to confirm SL/TP attached correctly
   and the fill price/lot size match what was logged.

## Known limitations of this first version

- **Single TP per position.** MT5 positions carry one SL/TP pair; TP1 is
  used as the position's take-profit. TP2/TP3 from the signal are logged
  but not acted on - no partial-close scaling is implemented yet.
- **`type_filling: ORDER_FILLING_IOC`** is hardcoded in `mt5_bot.py`'s
  order request. Some brokers reject this ("Unsupported filling mode") and
  need `ORDER_FILLING_FOK` or `ORDER_FILLING_RETURN` instead - if orders
  fail with that error, check `mt5.symbol_info(symbol).filling_mode` and
  adjust.
- **Daily trade count / consecutive-loss tracking** lives in a local
  `mt5_bot_state.json` next to the script, not in MT5 itself - if you run
  multiple instances or wipe that file, the counters reset.
- **No weekend/market-closed handling beyond MT5's own behavior** - it'll
  just get empty/stale rates when the market's shut, and `symbol_select`
  or `copy_rates_from_pos` should fail gracefully, but this hasn't been
  observed against a real closed session.
