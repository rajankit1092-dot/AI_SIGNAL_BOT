"""
Grid search over strategy parameters on the TRAIN split only, then validates
the best candidates on the held-out TEST split to check for overfitting
before anything is called a real result.
"""
import itertools
import warnings
warnings.filterwarnings("ignore")

from backtest import (
    SYMBOLS, build_dataset, simulate_trades, stats_for_trades, default_params,
)

TRAIN_SPLIT = (0.0, 0.7)
TEST_SPLIT = (0.7, 1.0)

print("Building datasets (indicators + MTF merge) once...")
DATASETS = {s: build_dataset(s) for s in SYMBOLS}
print("Done.\n")


def run_on_split(params, split):
    all_trades = []
    per_symbol = {}
    for symbol, df in DATASETS.items():
        n = len(df)
        start_idx, end_idx = int(n * split[0]), int(n * split[1])
        trades = simulate_trades(df, params, start_idx=start_idx, end_idx=end_idx)
        per_symbol[symbol] = stats_for_trades(trades)
        all_trades.extend(trades)
    return stats_for_trades(all_trades), per_symbol


def grid():
    base = default_params()
    for use_mtf in [False, True]:
        for require_pullback in [False, True]:
            for adx_min in [25, 30]:
                for rsi_pair in [(55, 45), (60, 40)]:
                    for vol_min in [1.2, 1.5]:
                        for atr_mult_sl in [1.5, 2.0]:
                            p = dict(base)
                            p["use_mtf"] = use_mtf
                            p["require_pullback"] = require_pullback
                            p["pullback_atr_mult"] = 1.0
                            p["adx_min"] = adx_min
                            p["rsi_buy"], p["rsi_sell"] = rsi_pair
                            p["volume_ratio_min"] = vol_min
                            p["atr_mult_sl"] = atr_mult_sl
                            yield p


results = []
combos = list(grid())
print(f"Testing {len(combos)} parameter combinations on TRAIN split...\n")

for idx, p in enumerate(combos):
    stats, _ = run_on_split(p, TRAIN_SPLIT)
    if stats["n"] and stats["n"] >= 25:
        results.append((stats, p))

results.sort(key=lambda x: (-x[0]["win_rate"], -x[0]["n"]))

print("=== TOP 10 ON TRAIN SPLIT (win rate, min 25 trades) ===")
for stats, p in results[:10]:
    print(f"win_rate={stats['win_rate']:.1f}% n={stats['n']} avg_r={stats['avg_r']:.2f} "
          f"pf={stats['profit_factor']:.2f} | mtf={p['use_mtf']} pullback={p['require_pullback']} "
          f"adx={p['adx_min']} rsi=({p['rsi_buy']},{p['rsi_sell']}) vol={p['volume_ratio_min']} "
          f"sl_atr={p['atr_mult_sl']}")

print("\n=== VALIDATING TOP 5 ON HELD-OUT TEST SPLIT ===")
for stats, p in results[:5]:
    test_stats, per_symbol = run_on_split(p, TEST_SPLIT)
    if test_stats["n"]:
        print(f"TRAIN win_rate={stats['win_rate']:.1f}% (n={stats['n']})  ->  "
              f"TEST win_rate={test_stats['win_rate']:.1f}% (n={test_stats['n']}) "
              f"avg_r={test_stats['avg_r']:.2f} pf={test_stats['profit_factor']:.2f} | params={p}")
    else:
        print(f"TRAIN win_rate={stats['win_rate']:.1f}% (n={stats['n']})  ->  TEST: no trades | params={p}")
