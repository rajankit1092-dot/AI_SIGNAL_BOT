import ta
import pandas as pd
import numpy as np

def add_indicators(df):

    # =========================
    # EMA
    # =========================
    df["ema9"] = ta.trend.ema_indicator(df["close"], window=9)
    df["ema21"] = ta.trend.ema_indicator(df["close"], window=21)
    df["ema50"] = ta.trend.ema_indicator(df["close"], window=50)
    df["ema200"] = ta.trend.ema_indicator(df["close"], window=200)

    # =========================
    # RSI
    # =========================
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)

    # =========================
    # MACD
    # =========================
    macd = ta.trend.MACD(df["close"])

    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    # =========================
    # ATR
    # =========================
    df["atr"] = ta.volatility.average_true_range(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    # =========================
    # ADX
    # =========================
    df["adx"] = ta.trend.adx(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    # =========================
    # Bollinger Bands
    # =========================
    bb = ta.volatility.BollingerBands(
        close=df["close"],
        window=20,
        window_dev=2
    )

    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = (
        df["bb_upper"] - df["bb_lower"]
    ) / df["bb_middle"]

    # =========================
    # VWAP
    # =========================
    df["vwap"] = ta.volume.volume_weighted_average_price(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        volume=df["volume"]
    )

    # =========================
    # Momentum
    # =========================
    df["momentum"] = ta.momentum.roc(
        df["close"],
        window=10
    )

    # =========================
    # Stochastic RSI
    # =========================
    stoch = ta.momentum.StochRSIIndicator(
        close=df["close"],
        window=14
    )

    df["stoch_rsi"] = stoch.stochrsi()

    # =========================
    # Volume Analysis
    # =========================
    df["volume_sma"] = df["volume"].rolling(20).mean()

    df["volume_ratio"] = (
        df["volume"] / df["volume_sma"]
    )

    # =========================
    # Trend Strength
    # =========================
    df["strong_bullish_trend"] = (
        (df["ema9"] > df["ema21"]) &
        (df["ema21"] > df["ema50"]) &
        (df["close"] > df["vwap"]) &
        (df["adx"] > 25)
    )

    df["strong_bearish_trend"] = (
        (df["ema9"] < df["ema21"]) &
        (df["ema21"] < df["ema50"]) &
        (df["close"] < df["vwap"]) &
        (df["adx"] > 25)
    )

    # EMA-alignment trend direction without the ADX strength requirement.
    # Used for higher-timeframe confirmation, where the entry timeframe's
    # own ADX filter already screens for a strong-enough move.
    df["ema_trend_bull"] = (
        (df["ema9"] > df["ema21"]) &
        (df["ema21"] > df["ema50"]) &
        (df["close"] > df["vwap"])
    )

    df["ema_trend_bear"] = (
        (df["ema9"] < df["ema21"]) &
        (df["ema21"] < df["ema50"]) &
        (df["close"] < df["vwap"])
    )

    # =========================
    # Bollinger Squeeze
    # =========================
    df["squeeze"] = (
        df["bb_width"] <
        df["bb_width"].rolling(20).mean()
    )

    # =========================
    # Buy Strength Score
    # =========================
    df["buy_score"] = 0

    df.loc[df["ema9"] > df["ema21"], "buy_score"] += 10
    df.loc[df["ema21"] > df["ema50"], "buy_score"] += 10
    df.loc[df["rsi"] > 55, "buy_score"] += 10
    df.loc[df["macd"] > df["macd_signal"], "buy_score"] += 10
    df.loc[df["adx"] > 25, "buy_score"] += 10
    df.loc[df["close"] > df["vwap"], "buy_score"] += 10
    df.loc[df["volume_ratio"] > 1.5, "buy_score"] += 10
    df.loc[df["momentum"] > 0, "buy_score"] += 10
    df.loc[df["stoch_rsi"] > 0.8, "buy_score"] += 10
    df.loc[df["strong_bullish_trend"], "buy_score"] += 10

    # =========================
    # Sell Strength Score
    # =========================
    df["sell_score"] = 0

    df.loc[df["ema9"] < df["ema21"], "sell_score"] += 10
    df.loc[df["ema21"] < df["ema50"], "sell_score"] += 10
    df.loc[df["rsi"] < 45, "sell_score"] += 10
    df.loc[df["macd"] < df["macd_signal"], "sell_score"] += 10
    df.loc[df["adx"] > 25, "sell_score"] += 10
    df.loc[df["close"] < df["vwap"], "sell_score"] += 10
    df.loc[df["volume_ratio"] > 1.5, "sell_score"] += 10
    df.loc[df["momentum"] < 0, "sell_score"] += 10
    df.loc[df["stoch_rsi"] < 0.2, "sell_score"] += 10
    df.loc[df["strong_bearish_trend"], "sell_score"] += 10

    return df
