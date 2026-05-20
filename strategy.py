def generate_signal(df):

    latest = df.iloc[-1]

    signal = None
    confidence = 0

    # =========================
    # BUY CONDITIONS
    # =========================
    if (

        latest["buy_score"] >= 80 and

        latest["strong_bullish_trend"] and

        latest["rsi"] > 55 and

        latest["macd"] > latest["macd_signal"] and

        latest["close"] > latest["vwap"] and

        latest["adx"] > 25 and

        latest["volume_ratio"] > 1.2

    ):

        signal = "BUY"
        confidence = latest["buy_score"]

    # =========================
    # SELL CONDITIONS
    # =========================
    elif (

        latest["sell_score"] >= 80 and

        latest["strong_bearish_trend"] and

        latest["rsi"] < 45 and

        latest["macd"] < latest["macd_signal"] and

        latest["close"] < latest["vwap"] and

        latest["adx"] > 25 and

        latest["volume_ratio"] > 1.2

    ):

        signal = "SELL"
        confidence = latest["sell_score"]

    # =========================
    # NO SIGNAL
    # =========================
    if signal is None:
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

        sl = entry - (atr * 1.5)

        risk = entry - sl

        tp1 = entry + (risk * 1.5)

        tp2 = entry + (risk * 2)

        tp3 = entry + (risk * 3)

    else:

        sl = entry + (atr * 1.5)

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