from config import (
    MIN_CONFIDENCE,
    MIN_ADX,
    MIN_VOLUME_RATIO,
    ATR_MULTIPLIER,
    ENABLE_MULTI_TIMEFRAME,
    REQUIRE_PULLBACK,
    PULLBACK_ATR_MULT,
)


def _htf_confirms(df_htf, direction):
    """Does the higher-timeframe trend (already-closed bar) agree with direction?"""
    if df_htf is None or len(df_htf) == 0:
        return False

    latest = df_htf.iloc[-1]

    if direction == "BUY":
        return bool(latest["ema_trend_bull"])

    return bool(latest["ema_trend_bear"])


def generate_signal(df, df_1h=None, df_4h=None):

    latest = df.iloc[-1]

    signal = None
    confidence = 0

    # =========================
    # BUY CONDITIONS
    # =========================
    if (

        latest["buy_score"] >= MIN_CONFIDENCE and

        latest["strong_bullish_trend"] and

        latest["rsi"] > 55 and

        latest["macd"] > latest["macd_signal"] and

        latest["close"] > latest["vwap"] and

        latest["adx"] > MIN_ADX and

        latest["volume_ratio"] > MIN_VOLUME_RATIO

    ):

        signal = "BUY"
        confidence = latest["buy_score"]

    # =========================
    # SELL CONDITIONS
    # =========================
    elif (

        latest["sell_score"] >= MIN_CONFIDENCE and

        latest["strong_bearish_trend"] and

        latest["rsi"] < 45 and

        latest["macd"] < latest["macd_signal"] and

        latest["close"] < latest["vwap"] and

        latest["adx"] > MIN_ADX and

        latest["volume_ratio"] > MIN_VOLUME_RATIO

    ):

        signal = "SELL"
        confidence = latest["sell_score"]

    # =========================
    # NO SIGNAL
    # =========================
    if signal is None:
        return None

    # =========================
    # MULTI-TIMEFRAME CONFIRMATION
    # =========================
    # Requires the 1h and 4h trend to agree with the entry-timeframe signal,
    # so trades aren't taken against the higher-timeframe trend.
    if ENABLE_MULTI_TIMEFRAME:

        if not _htf_confirms(df_1h, signal):
            return None

        if not _htf_confirms(df_4h, signal):
            return None

    # =========================
    # PULLBACK FILTER
    # =========================
    # Requires price to still be close to the fast EMA rather than already
    # extended away from it, so entries are pullbacks into the trend instead
    # of chasing a move that's already run.
    if REQUIRE_PULLBACK:

        pullback_band = PULLBACK_ATR_MULT * latest["atr"]

        if signal == "BUY" and latest["close"] > latest["ema9"] + pullback_band:
            return None

        if signal == "SELL" and latest["close"] < latest["ema9"] - pullback_band:
            return None

    # =========================
    # ENTRY PRICE
    # =========================
    entry = latest["close"]

    # =========================
    # ATR-BASED SL
    # =========================
    atr = latest["atr"]

    if signal == "BUY":

        sl = entry - (atr * ATR_MULTIPLIER)

        risk = entry - sl

        tp1 = entry + (risk * 1.5)

        tp2 = entry + (risk * 2)

        tp3 = entry + (risk * 3)

    else:

        sl = entry + (atr * ATR_MULTIPLIER)

        risk = sl - entry

        tp1 = entry - (risk * 1.5)

        tp2 = entry - (risk * 2)

        tp3 = entry - (risk * 3)

    # =========================
    # RETURN SIGNAL
    # =========================
    return {

        "signal": signal,

        "entry": round(entry, 2),

        "sl": round(sl, 2),

        "tp1": round(tp1, 2),

        "tp2": round(tp2, 2),

        "tp3": round(tp3, 2),

        "confidence": int(confidence),

        "trend": (
            "Bullish"
            if signal == "BUY"
            else "Bearish"
        )

    }
