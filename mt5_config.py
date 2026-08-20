import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt5.env"))

# =========================
# MT5 CONNECTION
# =========================
# Never hardcode these - set them in a local mt5.env file (gitignored).
# See mt5.env.example for the template.

MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
# Only needed if MT5 isn't installed at the default path, e.g.
# "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
MT5_TERMINAL_PATH = os.getenv("MT5_TERMINAL_PATH", "") or None

# =========================
# SAFETY
# =========================

# True: compute and log every signal (with intended lot size/SL/TP) but
# never call mt5.order_send(). False: places real orders on your demo
# account. Start with True, watch it run for a while, THEN flip to False -
# this code has never been run against a live MT5 terminal from here (no
# Windows/MT5 available in the environment it was written in), and the
# forex/gold backtest it's based on covers a much shorter, less-validated
# window than the crypto strategy (see backtest_data/forex_tune.py output).
DRY_RUN = True

MAGIC_NUMBER = 20260817  # tags orders this bot places, so it can tell its own trades apart from manual ones

MAX_DAILY_TRADES = 5

MAX_CONSECUTIVE_LOSSES = 3

RISK_PER_TRADE_PERCENT = 1.0  # % of current account balance risked per trade, used to size the lot

# =========================
# SYMBOLS
# =========================
# Keys are the internal names used in logs/Telegram messages; values are
# EXACTLY what your broker calls the symbol in MT5's Market Watch - many
# brokers suffix these (e.g. "GBPUSDm", "GBPUSD.a", "XAUUSD.raw"). Check
# Market Watch and edit these before running, or symbol lookups will fail.

# GBPUSD and XAUUSD showed a real (if modest) edge in backtesting;
# EURUSD/USDJPY were net-negative over the ~70-day window tested - included
# here but OFF by default. Enable them only if you want to forward-test
# them yourself; this call is less confident than the BNB/USDT exclusion
# in the crypto bot, which had a longer window and a clear root-cause
# (direction-split) diagnosis behind it. This one doesn't.
MT5_SYMBOLS = {
    "GBPUSD": "GBPUSD",
    "XAUUSD": "XAUUSD",
}

MT5_SYMBOLS_OPTIONAL = {
    "EURUSD": "EURUSD",
    "USDJPY": "USDJPY",
}

TIMEFRAMES = {
    "trend": "H4",
    "confirmation": "H1",
    "entry": "M15",
}

# =========================
# SIGNAL SETTINGS
# =========================
# Tuned on backtest_data/forex_tune.py's train split (crypto's tuned
# params didn't transfer well as-is - see that script's baseline output).

MIN_CONFIDENCE = 80

MIN_ADX = 30

RSI_BUY_THRESHOLD = 55

RSI_SELL_THRESHOLD = 45

ENABLE_MULTI_TIMEFRAME = True

# Off: MT5 tick_volume is real (unlike Yahoo's spot-forex feed used for
# backtesting, which reports 0 and makes VWAP NaN), but volume/VWAP-based
# filtering on tick_volume was never backtested here - only disabled
# filters were validated. Don't re-enable without a fresh backtest.
ENABLE_VWAP_FILTER = False

ENABLE_VOLUME_FILTER = False

MIN_VOLUME_RATIO = None  # unused while ENABLE_VOLUME_FILTER is False

REQUIRE_PULLBACK = False

PULLBACK_ATR_MULT = 1.0

# =========================
# RISK MANAGEMENT
# =========================

ATR_MULTIPLIER = 2.0

# =========================
# TELEGRAM ALERTS (optional, reuses the crypto bot's credentials/pattern)
# =========================

SEND_TELEGRAM_ALERTS = True
