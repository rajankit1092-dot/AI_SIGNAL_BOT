import config as default_config


def _htf_confirms(df_htf, direction, use_vwap):
    """Does the higher-timeframe trend (already-closed bar) agree with direction?"""
    if df_htf is None or len(df_htf) == 0:
        return False

    latest = df_htf.iloc[-1]
    col = "ema_trend_bull" if use_vwap else "ema_trend_bull_no_vwap"
    if direction == "SELL":
        col = "ema_trend_bear" if use_vwap else "ema_trend_bear_no_vwap"

    return bool(latest[col])


def generate_signal(df, df_1h=None, df_4h=None, cfg=default_config):

    latest = df.iloc[-1]

    signal = None
    confidence = 0

    use_vwap = getattr(cfg, "ENABLE_VWAP_FILTER", True)
    use_volume = getattr(cfg, "ENABLE_VOLUME_FILTER", True)
    rsi_buy = getattr(cfg, "RSI_BUY_THRESHOLD", 55)
    rsi_sell = getattr(cfg, "RSI_SELL_THRESHOLD", 45)

    trend_col_bull = "strong_bullish_trend" if use_vwap else "strong_bullish_trend_no_vwap"
    trend_col_bear = "strong_bearish_trend" if use_vwap else "strong_bearish_trend_no_vwap"
    buy_score_col = "buy_score" if use_vwap else "buy_score_no_vwap"
    sell_score_col = "sell_score" if use_vwap else "sell_score_no_vwap"

    # =========================
    # BUY CONDITIONS
    # =========================
    buy = (

        latest[buy_score_col] >= cfg.MIN_CONFIDENCE and

        latest[trend_col_bull] and

        latest["rsi"] > rsi_buy and

        latest["macd"] > latest["macd_signal"] and

        (not use_vwap or latest["close"] > latest["vwap"]) and

        latest["adx"] > cfg.MIN_ADX and

        (not use_volume or latest["volume_ratio"] > cfg.MIN_VOLUME_RATIO)

    )

    # =========================
    # SELL CONDITIONS
    # =========================
    sell = (

        latest[sell_score_col] >= cfg.MIN_CONFIDENCE and

        latest[trend_col_bear] and

        latest["rsi"] < rsi_sell and

        latest["macd"] < latest["macd_signal"] and

        (not use_vwap or latest["close"] < latest["vwap"]) and

        latest["adx"] > cfg.MIN_ADX and

        (not use_volume or latest["volume_ratio"] > cfg.MIN_VOLUME_RATIO)

    )

    if buy:
        signal = "BUY"
        confidence = latest[buy_score_col]
    elif sell:
        signal = "SELL"
        confidence = latest[sell_score_col]

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
    if getattr(cfg, "ENABLE_MULTI_TIMEFRAME", True):

        if not _htf_confirms(df_1h, signal, use_vwap):
            return None

        if not _htf_confirms(df_4h, signal, use_vwap):
            return None

    # =========================
    # PULLBACK FILTER
    # =========================
    # Requires price to still be close to the fast EMA rather than already
    # extended away from it, so entries are pullbacks into the trend instead
    # of chasing a move that's already run.
    if getattr(cfg, "REQUIRE_PULLBACK", False):

        pullback_band = cfg.PULLBACK_ATR_MULT * latest["atr"]

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

        sl = entry - (atr * cfg.ATR_MULTIPLIER)

        risk = entry - sl

        tp1 = entry + (risk * 1.5)

        tp2 = entry + (risk * 2)

        tp3 = entry + (risk * 3)

    else:

        sl = entry + (atr * cfg.ATR_MULTIPLIER)

        risk = sl - entry

        tp1 = entry - (risk * 1.5)

        tp2 = entry - (risk * 2)

        tp3 = entry - (risk * 3)

    # =========================
    # RETURN SIGNAL
    # =========================
    return {

        "signal": signal,

        "entry": round(entry, 5),

        "sl": round(sl, 5),

        "tp1": round(tp1, 5),

        "tp2": round(tp2, 5),

        "tp3": round(tp3, 5),

        "confidence": int(confidence),

        "trend": (
            "Bullish"
            if signal == "BUY"
            else "Bearish"
        )

    }
