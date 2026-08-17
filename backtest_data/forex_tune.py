"""
Grid search for the forex/gold variant, same train/test discipline as
tune.py used for crypto. Only ~60-84 days of 15m history is available here
(vs ~120 for crypto via KuCoin) - smaller sample, flagged in the report.
"""
import warnings
warnings.filterwarnings("ignore")

from backtest import simulate_trades, stats_for_trades
from forex_backtest import FOREX_SYMBOLS, build_dataset, forex_params, SPREADS

TRAIN_SPLIT = (0.0, 0.7)
TEST_SPLIT = (0.7, 1.0)

print("Building datasets...")
DATASETS = {s: build_dataset(s) for s in FOREX_SYMBOLS}
print("Done.\n")


def run_on_split(params, split, symbols=FOREX_SYMBOLS):
    all_trades = []
    per_symbol = {}
    for symbol in symbols:
        df = DATASETS[symbol]
        n = len(df)
        start_idx, end_idx = int(n * split[0]), int(n * split[1])
        trades = simulate_trades(df, params, start_idx=start_idx, end_idx=end_idx, spread=SPREADS[symbol])
        per_symbol[symbol] = stats_for_trades(trades)
        all_trades.extend(trades)
    return stats_for_trades(all_trades), per_symbol


def grid():
    for adx_min in [25, 30, 35]:
        for use_mtf in [False, True]:
            for require_pullback in [False, True]:
                for rsi_pair in [(55, 45), (60, 40)]:
                    for atr_mult_sl in [1.5, 2.0, 2.5]:
                        p = forex_params()
                        p["adx_min"] = adx_min
                        p["use_mtf"] = use_mtf
                        p["require_pullback"] = require_pullback
                        p["rsi_buy"], p["rsi_sell"] = rsi_pair
                        p["atr_mult_sl"] = atr_mult_sl
                        yield p


results = []
combos = list(grid())
print(f"Testing {len(combos)} combinations on TRAIN split...\n")

for p in combos:
    stats, _ = run_on_split(p, TRAIN_SPLIT)
    if stats["n"] and stats["n"] >= 20:
        results.append((stats, p))

results.sort(key=lambda x: (-x[0]["avg_r"], -x[0]["n"]))

print("=== TOP 10 ON TRAIN SPLIT (by avg_r, min 20 trades) ===")
for stats, p in results[:10]:
    print(f"avg_r={stats['avg_r']:.2f} win={stats['win_rate']:.1f}% n={stats['n']} pf={stats['profit_factor']:.2f} | "
          f"adx={p['adx_min']} mtf={p['use_mtf']} pullback={p['require_pullback']} "
          f"rsi=({p['rsi_buy']},{p['rsi_sell']}) sl_atr={p['atr_mult_sl']}")

print("\n=== VALIDATING TOP 5 ON HELD-OUT TEST SPLIT ===")
for stats, p in results[:5]:
    test_stats, per_symbol = run_on_split(p, TEST_SPLIT)
    print(f"TRAIN avg_r={stats['avg_r']:.2f} win={stats['win_rate']:.1f}% (n={stats['n']})  ->  "
          f"TEST avg_r={test_stats.get('avg_r')} win={test_stats.get('win_rate')} (n={test_stats['n']}) "
          f"pf={test_stats.get('profit_factor')}")
    for sym, s in per_symbol.items():
        print(f"    {sym}: n={s['n']} win={s['win_rate']} avg_r={s['avg_r']}")
