"""Out-of-sample backtest of the FlowForensics_Absorption distribution SELL.

Runs the exact thinkScript rule (high-volume rejection at a session high, then a
VWAP-loss distribution bar) over ~3 months of 1-min TSLA data and measures
short-side edge: forward returns, MFE/MAE, win rate. July 2 (the day the rule was
derived from) is reported separately as the in-sample anchor; everything before it
is out-of-sample.
"""
import sys, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "src")
import numpy as np, pandas as pd
from tsla_decoded.config import load_settings
from tsla_decoded.fmp_client import FMPClient
from tsla_decoded import data_loader as dl
from tsla_decoded.features import anchored_vwap

REJ_RELVOL, WICK, DIST_RELVOL, LOOKBACK, HIGH_FRAC, COOLDOWN_MIN = 2.0, 0.40, 1.5, 10, 0.999, 30


def signals(m):
    reg = m[m.session == "regular"].copy()
    if reg.empty:
        return reg
    day = pd.Series(reg.index.date, index=reg.index)
    reg["vwap"] = anchored_vwap(reg)
    reg["relvol"] = reg.volume / reg.volume.rolling(50).mean()
    rng = (reg.high - reg.low).replace(0, np.nan)
    reg["upwick"] = ((reg.high - reg[["open", "close"]].max(axis=1)) / rng).fillna(0)
    reg["dayhigh"] = reg.groupby(day.values)["high"].cummax()
    reg["reject"] = (reg.relvol >= REJ_RELVOL) & (reg.upwick >= WICK) & (reg.high >= reg.dayhigh * HIGH_FRAC)
    reg["recent"] = reg.groupby(day.values)["reject"].transform(
        lambda x: x.rolling(LOOKBACK, min_periods=1).max()).astype(bool)
    reg["distrib"] = (reg.relvol >= DIST_RELVOL) & (reg.close < reg.vwap) & (reg.close < reg.open)
    reg["sell"] = reg.recent & (reg.close < reg.vwap) & reg.distrib
    reg["edge"] = reg.sell & ~reg.sell.shift(fill_value=False)
    return reg


def backtest(reg):
    """Short-side outcomes per signal: forward returns and rest-of-day MFE/MAE."""
    rows, last = [], {}
    for ts in reg.index[reg.edge]:
        d = ts.date()
        if d in last and (ts - last[d]).total_seconds() < COOLDOWN_MIN * 60:
            continue
        last[d] = ts
        entry = reg.loc[ts, "close"]
        day_after = reg[(reg.index.date == d) & (reg.index > ts)]
        if day_after.empty:
            continue
        # short pnl (%) = (entry - price)/entry * 100 ; positive = profit
        path = (entry - day_after["close"]) / entry * 100
        f30 = path[day_after.index <= ts + pd.Timedelta(minutes=30)]
        f60 = path[day_after.index <= ts + pd.Timedelta(minutes=60)]
        rows.append({
            "ts": ts, "entry": round(entry, 2),
            "fwd30": round(f30.iloc[-1], 2) if len(f30) else np.nan,
            "fwd60": round(f60.iloc[-1], 2) if len(f60) else np.nan,
            "eod": round(path.iloc[-1], 2),
            "mfe": round(path.max(), 2),   # best short excursion (max drop)
            "mae": round(path.min(), 2),   # worst (max rise against short)
        })
    return pd.DataFrame(rows)


def main():
    s = load_settings()
    c = FMPClient(s.api_key, s.cache_dir)
    print("pulling ~3 months of 1-min TSLA (cached after first run)...")
    m = dl.intraday(c, "TSLA", "1min", "2026-04-01", "2026-07-02")
    reg = signals(m)
    bt = backtest(reg)
    anchor = bt[bt["ts"].dt.date == pd.Timestamp("2026-07-02").date()]
    oos = bt[bt["ts"].dt.date < pd.Timestamp("2026-07-02").date()]
    ndays = len(set(reg.index.date))
    print(f"\n{ndays} trading days tested | {len(bt)} signals total "
          f"({len(oos)} out-of-sample, {len(anchor)} on the Jul-2 anchor)\n")
    print("=== OUT-OF-SAMPLE signals (Apr 1 - Jul 1), short-side % ===")
    if len(oos):
        print(oos.assign(ts=oos["ts"].astype(str).str[:16]).to_string(index=False))
        for col in ("fwd30", "fwd60", "eod"):
            v = oos[col].dropna()
            print(f"  {col}: mean {v.mean():+.2f}%  median {v.median():+.2f}%  "
                  f"win {(v > 0).mean():.0%}  n={len(v)}")
        print(f"  avg MFE (max drop captured) {oos.mfe.mean():+.2f}%  | "
              f"avg MAE (heat taken) {oos.mae.mean():+.2f}%")
        exp = oos["eod"].mean()
        print(f"\n  EDGE VERDICT: mean EOD short return {exp:+.2f}% per signal over "
              f"{len(oos)} OOS signals, {(oos.eod>0).mean():.0%} profitable")
    else:
        print("  no OOS signals")
    print("\n=== Jul-2 anchor (in-sample) ===")
    if len(anchor):
        print(anchor.assign(ts=anchor["ts"].astype(str).str[:16]).to_string(index=False))


if __name__ == "__main__":
    main()
