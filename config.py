# =========================
# SYMBOLS
# =========================

CRYPTO_SYMBOLS = [

    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT"

]

# =========================
# INDIAN MARKETS
# =========================

INDIAN_INDICES = {

    "NIFTY50": True,
    "BANKNIFTY": True,
    "SENSEX": True,
    "FINNIFTY": True

}

# =========================
# COMMODITIES
# =========================

COMMODITIES = {

    "GOLD": True,
    "SILVER": True,
    "CRUDEOIL": True,
    "NATURALGAS": True

}

# =========================
# TIMEFRAMES
# =========================

TIMEFRAMES = {

    "trend": "4h",
    "confirmation": "1h",
    "entry": "15m"

}

# =========================
# SIGNAL SETTINGS
# =========================

MIN_CONFIDENCE = 80

MIN_ADX = 25

MIN_VOLUME_RATIO = 1.2

ENABLE_MULTI_TIMEFRAME = True

ENABLE_VWAP_FILTER = True

ENABLE_VOLUME_FILTER = True

ENABLE_BB_SQUEEZE = True

ENABLE_TREND_FILTER = True

# =========================
# RISK MANAGEMENT
# =========================

RISK_REWARD_RATIO = 2

ATR_MULTIPLIER = 1.5

MAX_DAILY_TRADES = 10

MAX_CONSECUTIVE_LOSSES = 3

MAX_RISK_PER_TRADE = 2

# =========================
# AI SETTINGS
# =========================

ENABLE_AI_SCORING = True

ENABLE_AI_FILTER = True

BUY_SCORE_THRESHOLD = 80

SELL_SCORE_THRESHOLD = 80

# =========================
# MARKET CONDITIONS
# =========================

AVOID_LOW_VOLUME = True

AVOID_EXTREME_VOLATILITY = True

ENABLE_MOMENTUM_FILTER = True

ENABLE_MACD_FILTER = True

ENABLE_RSI_FILTER = True

ENABLE_ADX_FILTER = True

# =========================
# TELEGRAM SETTINGS
# =========================

SEND_ONLY_HIGH_CONFIDENCE = True

SEND_TP1 = True

SEND_TP2 = True

SEND_TP3 = True

SEND_MARKET_TREND = True

SEND_CONFIDENCE_SCORE = True

# =========================
# MODES
# =========================

ENABLE_INTRADAY = True

ENABLE_SWING = True

# =========================
# FUTURE FEATURES
# =========================

ENABLE_NEWS_FILTER = False

ENABLE_SMART_MONEY = False

ENABLE_OI_ANALYSIS = False

ENABLE_FUNDING_RATE = False

ENABLE_MACHINE_LEARNING = False