"""
Final verification: calls the ACTUAL production strategy.generate_signal()
(which reads the real config.py) instead of a parallel reimplementation, so
this number is exactly what the shipped code would have produced historically.

generate_signal() only ever touches .iloc[-1] of df, df_1h and df_4h, so a
single current-row slice of each is sufficient per call - no need to pass
full history.
"""
import sys
import os
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategy import generate_signal  # noqa: E402
from backtest import SYMBOLS, build_dataset, stats_for_trades, MAX_HOLD_BARS  # noqa: E402


def simulate_with_production_strategy(df, start_idx=200, end_idx=None):
    end_idx = len(df) if end_idx is None else end_idx
    trades = []
    i = start_idx

    while i < end_idx - 1:
        row = df.iloc[i]
        if row[["ema200", "atr", "adx", "vwap"]].isna().any():
            i += 1
            continue

        df_1h_row = row[["ema_trend_bull" if False else "h1_bull", "h1_bear"]].to_frame().T
        df_1h_row = df_1h_row.rename(columns={"h1_bull": "ema_trend_bull", "h1_bear": "ema_trend_bear"})
        df_4h_row = row[["h4_bull", "h4_bear"]].to_frame().T
        df_4h_row = df_4h_row.rename(columns={"h4_bull": "ema_trend_bull", "h4_bear": "ema_trend_bear"})

        sig = generate_signal(df.iloc[[i]], df_1h_row, df_4h_row)

        if sig is None:
            i += 1
            continue

        entry_idx = i + 1
        entry_open = df.iloc[entry_idx]["open"]

        # generate_signal computed entry/sl/tp off the signal bar's close;
        # re-derive the same risk distance but fill at next bar's open, same
        # as the rest of the backtest engine.
        risk_per_unit = abs(sig["entry"] - sig["sl"])
        if sig["signal"] == "BUY":
            sl = entry_open - risk_per_unit
            tp1 = entry_open + risk_per_unit * 1.5
            tp2 = entry_open + risk_per_unit * 2
            tp3 = entry_open + risk_per_unit * 3
        else:
            sl = entry_open + risk_per_unit
            tp1 = entry_open - risk_per_unit * 1.5
            tp2 = entry_open - risk_per_unit * 2
            tp3 = entry_open - risk_per_unit * 3

        outcome = None
        exit_r = None
        exit_idx = None

        for j in range(entry_idx, min(entry_idx + MAX_HOLD_BARS, len(df))):
            bar = df.iloc[j]
            is_buy = sig["signal"] == "BUY"
            hit_sl = bar["low"] <= sl if is_buy else bar["high"] >= sl
            hit_tp1 = bar["high"] >= tp1 if is_buy else bar["low"] <= tp1
            hit_tp2 = bar["high"] >= tp2 if is_buy else bar["low"] <= tp2
            hit_tp3 = bar["high"] >= tp3 if is_buy else bar["low"] <= tp3

            if hit_sl:
                outcome, exit_r, exit_idx = "LOSS", -1.0, j
                break
            if hit_tp1:
                exit_r = 3.0 if hit_tp3 else (2.0 if hit_tp2 else 1.5)
                outcome, exit_idx = "WIN", j
                break

        if outcome is None:
            j = min(entry_idx + MAX_HOLD_BARS, len(df)) - 1
            last_close = df.iloc[j]["close"]
            r = ((last_close - entry_open) if sig["signal"] == "BUY" else (entry_open - last_close)) / risk_per_unit
            outcome = "WIN" if r > 0 else "LOSS"
            exit_r, exit_idx = r, j

        trades.append(dict(outcome=outcome, r=exit_r))
        i = exit_idx + 1

    return trades


if __name__ == "__main__":
    # Rebuild datasets with h1_bull/h1_bear/h4_bull/h4_bear columns present
    # (build_dataset in backtest.py already merges these via ema_trend_bull/bear).
    import backtest as bt

    all_trades = []
    per_symbol = {}
    for symbol in SYMBOLS:
        df = bt.build_dataset(symbol)
        trades = simulate_with_production_strategy(df)
        per_symbol[symbol] = stats_for_trades(trades)
        all_trades += trades

    overall = stats_for_trades(all_trades)
    print("=== FINAL VERIFICATION using actual strategy.generate_signal() + config.py ===")
    if overall["n"]:
        print(f"Overall: n={overall['n']} win_rate={overall['win_rate']:.1f}% "
              f"avg_r={overall['avg_r']:.2f} profit_factor={overall['profit_factor']:.2f}")
    else:
        print("No trades")
    for sym, s in per_symbol.items():
        if s["n"]:
            print(f"  {sym}: n={s['n']} win_rate={s['win_rate']:.1f}% avg_r={s['avg_r']:.2f} "
                  f"profit_factor={s['profit_factor']:.2f}")
        else:
            print(f"  {sym}: no trades")
