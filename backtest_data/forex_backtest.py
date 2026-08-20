"""
Forex/gold backtest, reusing the same engine as backtest.py (indicators,
htf-merge, simulate_trades) but with:
  - forex/gold CSVs from fetch_forex.py instead of KuCoin crypto data
  - volume_ratio_min=None (Yahoo's forex feed reports 0 volume for every
    bar, so that filter can't be backtested here - see fetch_forex.py)
  - a modeled bid/ask spread per symbol, since spread is a much bigger
    fraction of a 15m ATR move in forex than in crypto
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest import add_htf_trend, merge_htf, simulate_trades, stats_for_trades, default_params  # noqa: E402

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

FOREX_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]

# Round-trip spread assumed per symbol, in price units - conservative
# estimates for a standard (non-ECN) retail MT5 demo account. These are
# ASSUMPTIONS, not the user's actual broker spread - verify against the
# real demo account's Market Watch before trusting live results.
SPREADS = {
    "EURUSD": 0.00012,   # ~1.2 pips
    "GBPUSD": 0.00016,   # ~1.6 pips
    "USDJPY": 0.018,     # ~1.8 pips (JPY pip = 0.01)
    "XAUUSD": 0.35,      # ~35 cents/oz
}


def load_symbol_data(symbol):
    df15 = pd.read_csv(os.path.join(DATA_DIR, f"{symbol}_15m.csv"), parse_dates=["timestamp"])
    df1h = pd.read_csv(os.path.join(DATA_DIR, f"{symbol}_1h.csv"), parse_dates=["timestamp"])
    df4h = pd.read_csv(os.path.join(DATA_DIR, f"{symbol}_4h.csv"), parse_dates=["timestamp"])
    return df15, df1h, df4h


def build_dataset(symbol):
    from indicators import add_indicators

    df15, df1h, df4h = load_symbol_data(symbol)
    df15 = add_indicators(df15)

    trend1h = add_htf_trend(df1h, "h1")
    trend4h = add_htf_trend(df4h, "h4")

    df15 = merge_htf(df15, trend1h, "h1", pd.Timedelta(hours=1))
    df15 = merge_htf(df15, trend4h, "h4", pd.Timedelta(hours=4))

    return df15.reset_index(drop=True)


def forex_params(**overrides):
    # Starts from the params actually shipped for crypto (config.py as of
    # the BNB-drop commit), not backtest.py's pre-tuning defaults - "does
    # the crypto-tuned strategy transfer to forex" is the real question.
    p = default_params()
    p.update(
        use_mtf=True,
        require_pullback=True,
        pullback_atr_mult=1.0,
        adx_min=30,
        rsi_buy=55,
        rsi_sell=45,
        atr_mult_sl=2.0,
        volume_ratio_min=None,  # no usable volume data from Yahoo forex feed
        use_vwap=False,  # VWAP is NaN with zero volume - see fetch_forex.py
    )
    p.update(overrides)
    return p


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    params = forex_params()
    all_trades = []
    per_symbol = {}

    for symbol in FOREX_SYMBOLS:
        df = build_dataset(symbol)
        trades = simulate_trades(df, params, spread=SPREADS[symbol])
        per_symbol[symbol] = stats_for_trades(trades)
        all_trades += trades

    overall = stats_for_trades(all_trades)
    print("=== BASELINE (crypto-tuned params, unchanged) ON FOREX/GOLD, WITH SPREAD ===")
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
