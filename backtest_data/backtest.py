"""
Backtest engine for the signal bot's strategy.

Design notes (why it's built this way):
- Indicators (EMA/RSI/MACD/ATR/ADX/BB/VWAP from `ta`) are all rolling/causal,
  so computing them once over the full history does not leak future data into
  past signals.
- Higher-timeframe (1h/4h) data is merged onto the 15m series using each
  higher-tf bar's *close* time (open time + timeframe duration), not its open
  time, so a signal at 15m bar T never sees a still-forming 1h/4h candle.
- Trade entry is simulated at the *next* 15m bar's open (not the signal bar's
  own close), since a live system can't fill on a price it used to decide.
- Outcome per bar: if a bar's range touches both SL and TP1, SL is assumed to
  have been hit first (conservative - we don't have intrabar tick order).
- Only one open trade per symbol at a time (skip new signals while a trade is
  live), matching how the live bot would actually behave.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators import add_indicators  # noqa: E402

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SYMBOLS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]

MAX_HOLD_BARS = 96  # 24h on 15m bars


def load_symbol_data(symbol):
    tag = symbol.replace("/", "_")
    df15 = pd.read_csv(os.path.join(DATA_DIR, f"{tag}_15m.csv"), parse_dates=["timestamp"])
    df1h = pd.read_csv(os.path.join(DATA_DIR, f"{tag}_1h.csv"), parse_dates=["timestamp"])
    df4h = pd.read_csv(os.path.join(DATA_DIR, f"{tag}_4h.csv"), parse_dates=["timestamp"])
    return df15, df1h, df4h


def add_htf_trend(df_htf, prefix):
    # Reuses the exact same ema_trend_bull/ema_trend_bear columns that
    # production indicators.py computes, so the backtest validates the
    # identical logic that ships (not a lookalike reimplementation).
    df = add_indicators(df_htf.copy())
    df[f"{prefix}_bull"] = df["ema_trend_bull"]
    df[f"{prefix}_bear"] = df["ema_trend_bear"]
    df[f"{prefix}_bull_no_vwap"] = df["ema_trend_bull_no_vwap"]
    df[f"{prefix}_bear_no_vwap"] = df["ema_trend_bear_no_vwap"]
    return df[["timestamp", f"{prefix}_bull", f"{prefix}_bear",
               f"{prefix}_bull_no_vwap", f"{prefix}_bear_no_vwap"]]


def merge_htf(df15, df_htf_trend, prefix, tf_duration):
    cols = [f"{prefix}_bull", f"{prefix}_bear", f"{prefix}_bull_no_vwap", f"{prefix}_bear_no_vwap"]
    htf = df_htf_trend.copy()
    htf["available_at"] = htf["timestamp"] + tf_duration
    htf = htf.sort_values("available_at")
    merged = pd.merge_asof(
        df15.sort_values("timestamp"),
        htf[["available_at"] + cols],
        left_on="timestamp",
        right_on="available_at",
        direction="backward",
    )
    for c in cols:
        merged[c] = merged[c].fillna(False).astype(bool)
    return merged.drop(columns=["available_at"])


def build_dataset(symbol):
    df15, df1h, df4h = load_symbol_data(symbol)
    df15 = add_indicators(df15)

    trend1h = add_htf_trend(df1h, "h1")
    trend4h = add_htf_trend(df4h, "h4")

    df15 = merge_htf(df15, trend1h, "h1", pd.Timedelta(hours=1))
    df15 = merge_htf(df15, trend4h, "h4", pd.Timedelta(hours=4))

    return df15.reset_index(drop=True)


def default_params():
    return dict(
        min_confidence=80,
        rsi_buy=55,
        rsi_sell=45,
        adx_min=25,
        volume_ratio_min=1.2,
        atr_mult_sl=1.5,
        tp1_r=1.5,
        tp2_r=2.0,
        tp3_r=3.0,
        use_mtf=False,
        require_pullback=False,
        pullback_atr_mult=1.0,
        min_bb_width_pct=None,  # e.g. 0.0 -> require bb_width above its own rolling mean (no squeeze)
        breakeven_at_r=None,  # e.g. 1.0 -> move SL to entry once price is +1R in favor
        use_vwap=True,  # False when volume data is unusable (e.g. Yahoo spot forex feed)
    )


def signal_at_row(row, params):
    use_vwap = params.get("use_vwap", True)
    trend_bull = "strong_bullish_trend" if use_vwap else "strong_bullish_trend_no_vwap"
    trend_bear = "strong_bearish_trend" if use_vwap else "strong_bearish_trend_no_vwap"
    buy_score_col = "buy_score" if use_vwap else "buy_score_no_vwap"
    sell_score_col = "sell_score" if use_vwap else "sell_score_no_vwap"

    buy = (
        row[buy_score_col] >= params["min_confidence"]
        and row[trend_bull]
        and row["rsi"] > params["rsi_buy"]
        and row["macd"] > row["macd_signal"]
        and (not use_vwap or row["close"] > row["vwap"])
        and row["adx"] > params["adx_min"]
        and (params["volume_ratio_min"] is None or row["volume_ratio"] > params["volume_ratio_min"])
    )
    sell = (
        row[sell_score_col] >= params["min_confidence"]
        and row[trend_bear]
        and row["rsi"] < params["rsi_sell"]
        and row["macd"] < row["macd_signal"]
        and (not use_vwap or row["close"] < row["vwap"])
        and row["adx"] > params["adx_min"]
        and (params["volume_ratio_min"] is None or row["volume_ratio"] > params["volume_ratio_min"])
    )

    bull_col = "h1_bull" if use_vwap else "h1_bull_no_vwap"
    bear_col = "h1_bear" if use_vwap else "h1_bear_no_vwap"
    bull_col4 = "h4_bull" if use_vwap else "h4_bull_no_vwap"
    bear_col4 = "h4_bear" if use_vwap else "h4_bear_no_vwap"

    if buy and params["use_mtf"]:
        buy = row[bull_col] and row[bull_col4]
    if sell and params["use_mtf"]:
        sell = row[bear_col] and row[bear_col4]

    if buy and params["require_pullback"]:
        buy = row["close"] <= row["ema9"] + params["pullback_atr_mult"] * row["atr"]
    if sell and params["require_pullback"]:
        sell = row["close"] >= row["ema9"] - params["pullback_atr_mult"] * row["atr"]

    if buy and params["min_bb_width_pct"] is not None:
        buy = not row["squeeze"]
    if sell and params["min_bb_width_pct"] is not None:
        sell = not row["squeeze"]

    if buy:
        return "BUY", row[buy_score_col]
    if sell:
        return "SELL", row[sell_score_col]
    return None, 0


def simulate_trades(df, params, start_idx=0, end_idx=None, spread=0.0):
    """
    spread: full round-trip bid/ask spread in price units (0 = crypto-style,
    no spread modeling). All OHLC in `df` is treated as the mid price - a
    BUY opens at mid+spread/2 (paying the ask) and closes at mid-spread/2
    (hitting the bid), and vice-versa for SELL. This makes stops trigger on
    a slightly smaller mid-price move than the nominal SL distance and
    targets require a slightly larger mid-price move than nominal - the
    real economic drag of spread, not just a flat fee bolted on after.
    """
    end_idx = len(df) if end_idx is None else end_idx
    trades = []
    i = start_idx
    warmup = 200  # ema200 warmup
    half_spread = spread / 2

    while i < end_idx - 1:
        if i < warmup:
            i += 1
            continue

        row = df.iloc[i]
        required_cols = ["ema200", "atr", "adx"]
        if params.get("use_vwap", True):
            required_cols.append("vwap")
        if row[required_cols].isna().any():
            i += 1
            continue

        signal, confidence = signal_at_row(row, params)

        if signal is None:
            i += 1
            continue

        entry_idx = i + 1
        entry_mid = df.iloc[entry_idx]["open"]
        atr = row["atr"]

        if signal == "BUY":
            entry = entry_mid + half_spread
            sl = entry - atr * params["atr_mult_sl"]
            risk = entry - sl
            tp1 = entry + risk * params["tp1_r"]
            tp2 = entry + risk * params["tp2_r"]
            tp3 = entry + risk * params["tp3_r"]
        else:
            entry = entry_mid - half_spread
            sl = entry + atr * params["atr_mult_sl"]
            risk = sl - entry
            tp1 = entry - risk * params["tp1_r"]
            tp2 = entry - risk * params["tp2_r"]
            tp3 = entry - risk * params["tp3_r"]

        if risk <= 0:
            i += 1
            continue

        outcome = None
        exit_r = None
        exit_idx = None
        cur_sl = sl
        breakeven_moved = False
        breakeven_r = params.get("breakeven_at_r")

        for j in range(entry_idx, min(entry_idx + MAX_HOLD_BARS, len(df))):
            bar = df.iloc[j]
            # Exiting a BUY sells at bid (mid-half_spread); exiting a SELL
            # buys at ask (mid+half_spread) - so mid needs to move further
            # to reach a given SL/TP level than the nominal distance implies.
            if signal == "BUY":
                hit_sl = bar["low"] <= cur_sl + half_spread
                hit_tp1 = bar["high"] >= tp1 + half_spread
                hit_tp2 = bar["high"] >= tp2 + half_spread
                hit_tp3 = bar["high"] >= tp3 + half_spread
            else:
                hit_sl = bar["high"] >= cur_sl - half_spread
                hit_tp1 = bar["low"] <= tp1 - half_spread
                hit_tp2 = bar["low"] <= tp2 - half_spread
                hit_tp3 = bar["low"] <= tp3 - half_spread

            if hit_sl:
                outcome = "LOSS"
                exit_r = 0.0 if breakeven_moved else -1.0
                exit_idx = j
                break
            if hit_tp1:
                if hit_tp3:
                    exit_r = params["tp3_r"]
                elif hit_tp2:
                    exit_r = params["tp2_r"]
                else:
                    exit_r = params["tp1_r"]
                outcome = "WIN"
                exit_idx = j
                break

            # Move stop to breakeven once price has moved breakeven_r in our
            # favor - takes effect from the NEXT bar onward (not retroactive
            # within the bar that triggered it, to avoid lookahead bias).
            if breakeven_r is not None and not breakeven_moved:
                favorable_r = (
                    (bar["high"] - half_spread - entry) / risk if signal == "BUY"
                    else (entry - (bar["low"] + half_spread)) / risk
                )
                if favorable_r >= breakeven_r:
                    cur_sl = entry
                    breakeven_moved = True

        if outcome is None:
            j = min(entry_idx + MAX_HOLD_BARS, len(df)) - 1
            last_close_mid = df.iloc[j]["close"]
            exit_fill = last_close_mid - half_spread if signal == "BUY" else last_close_mid + half_spread
            r = (exit_fill - entry) / risk if signal == "BUY" else (entry - exit_fill) / risk
            outcome = "WIN" if r > 0 else "LOSS"
            exit_r = r
            exit_idx = j

        trades.append(dict(
            entry_time=df.iloc[entry_idx]["timestamp"],
            signal=signal,
            confidence=confidence,
            entry=entry,
            sl=sl,
            tp1=tp1,
            outcome=outcome,
            r=exit_r,
        ))

        i = exit_idx + 1

    return trades


def stats_for_trades(trades):
    if not trades:
        return dict(n=0, win_rate=None, avg_r=None, profit_factor=None, expectancy=None)

    n = len(trades)
    wins = [t for t in trades if t["outcome"] == "WIN"]
    losses = [t for t in trades if t["outcome"] == "LOSS"]
    win_rate = len(wins) / n * 100

    gross_win = sum(t["r"] for t in wins)
    gross_loss = -sum(t["r"] for t in losses)
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    avg_r = sum(t["r"] for t in trades) / n
    expectancy = avg_r

    return dict(
        n=n,
        win_rate=win_rate,
        avg_r=avg_r,
        profit_factor=profit_factor,
        expectancy=expectancy,
    )


def run_backtest(params, split=None):
    """split: None = full history, or (start_frac, end_frac) tuple e.g. (0.0, 0.7)."""
    all_trades = []
    per_symbol = {}

    for symbol in SYMBOLS:
        df = build_dataset(symbol)
        n = len(df)
        if split is None:
            start_idx, end_idx = 0, n
        else:
            start_idx, end_idx = int(n * split[0]), int(n * split[1])

        trades = simulate_trades(df, params, start_idx=start_idx, end_idx=end_idx)
        per_symbol[symbol] = stats_for_trades(trades)
        all_trades.extend(trades)

    overall = stats_for_trades(all_trades)
    return overall, per_symbol, all_trades


if __name__ == "__main__":
    params = default_params()
    overall, per_symbol, _ = run_backtest(params)

    print("=== BASELINE STRATEGY (current strategy.py logic) ===")
    print(f"Overall: n={overall['n']} win_rate={overall['win_rate']:.1f}% "
          f"avg_r={overall['avg_r']:.2f} profit_factor={overall['profit_factor']:.2f}"
          if overall['n'] else "No trades")
    for sym, s in per_symbol.items():
        if s["n"]:
            print(f"  {sym}: n={s['n']} win_rate={s['win_rate']:.1f}% avg_r={s['avg_r']:.2f} "
                  f"profit_factor={s['profit_factor']:.2f}")
        else:
            print(f"  {sym}: no trades")
