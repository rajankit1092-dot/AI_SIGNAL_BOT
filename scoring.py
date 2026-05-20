def calculate_score(df):

    latest = df.iloc[-1]

    score = 0

    if latest["ema9"] > latest["ema21"]:
        score += 30

    if latest["rsi"] > 55:
        score += 30

    if latest["macd"] > latest["macd_signal"]:
        score += 30

    if latest["atr"] > 0:
        score += 10

    return score