import os
import ccxt
import pandas as pd
import schedule
import time

from dotenv import load_dotenv
from telegram import Bot

from indicators import add_indicators
from strategy import generate_signal

from config import (
    CRYPTO_SYMBOLS,
    TIMEFRAMES,
    MIN_CONFIDENCE,
    SEND_TP1,
    SEND_TP2,
    SEND_TP3,
    SEND_CONFIDENCE_SCORE,
    SEND_MARKET_TREND
)

# =========================
# LOAD ENV
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================
# TELEGRAM BOT
# =========================

bot = Bot(token=BOT_TOKEN)

# =========================
# BINANCE
# =========================

exchange = ccxt.binance({
    "enableRateLimit": True
})

# =========================
# FETCH MARKET DATA
# =========================

def fetch_data(symbol, timeframe):

    ohlcv = exchange.fetch_ohlcv(
        symbol,
        timeframe,
        limit=300
    )

    df = pd.DataFrame(
        ohlcv,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]
    )

    # Convert numeric columns
    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]:
        df[col] = df[col].astype(float)

    # Timestamp
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="ms"
    )

    return df

# =========================
# SEND TELEGRAM MESSAGE
# =========================

def send_signal(message):

    try:

        bot.send_message(
            chat_id=CHAT_ID,
            text=message
        )

        print("Signal sent successfully")

    except Exception as e:

        print(f"Telegram Error: {e}")

# =========================
# ANALYZE MARKET
# =========================

def analyze_symbol(symbol):

    try:

        # Fetch market data
        df = fetch_data(
            symbol,
            TIMEFRAMES["entry"]
        )

        # Add indicators
        df = add_indicators(df)

        # Generate signal
        signal = generate_signal(df)

        if signal is None:
            return

        # Confidence filter
        if signal["confidence"] < MIN_CONFIDENCE:
            return

        # =========================
        # CREATE MESSAGE
        # =========================

        message = f"""
🚀 AI SIGNAL ALERT

Pair: {symbol}

Signal: {signal['signal']}

Entry: {signal['entry']}

SL: {signal['sl']}
"""

        if SEND_TP1:
            message += f"\nTP1: {signal['tp1']}"

        if SEND_TP2:
            message += f"\nTP2: {signal['tp2']}"

        if SEND_TP3:
            message += f"\nTP3: {signal['tp3']}"

        if SEND_CONFIDENCE_SCORE:
            message += (
                f"\n\nConfidence: "
                f"{signal['confidence']}%"
            )

        if SEND_MARKET_TREND:
            message += (
                f"\nTrend: "
                f"{signal['trend']}"
            )

        message += (
            "\n\nAI Institutional Engine"
        )

        # Send signal
        send_signal(message)

        print(message)

    except Exception as e:

        print(f"Analysis Error ({symbol}): {e}")

# =========================
# MAIN ANALYSIS LOOP
# =========================

def run_bot():

    print("AI SIGNAL BOT RUNNING...")

    for symbol in CRYPTO_SYMBOLS:

        analyze_symbol(symbol)

# =========================
# SCHEDULER
# =========================

schedule.every(5).minutes.do(run_bot)

# =========================
# START BOT
# =========================

run_bot()

while True:

    schedule.run_pending()

    time.sleep(1)