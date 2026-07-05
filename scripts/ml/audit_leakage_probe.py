"""LEAKAGE/LOOK-AHEAD audit probes for FlowForensics.
Run against cached FMP 1-min data (offline). Writes findings to output/ml/.
Prefix: audit_leakage
"""
import os, sys, json
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
os.environ.setdefault("FMP_API_KEY", "cache-only")

from tsla_decoded.fmp_client import FMPClient
from tsla_decoded import data_loader as dl
from tsla_decoded import signal_backtest as sb

OUT = Path("output/ml"); OUT.mkdir(parents=True, exist_ok=True)
client = FMPClient(api_key=os.environ["FMP_API_KEY"], cache_dir=Path("data/raw"))

# Full cached window
START, END = "2026-04-01", "2026-07-02"
bars = dl.intraday(client, "TSLA", "1min", START, END)
daily = dl.daily(client, "TSLA", "2026-04-01", "2026-07-02")
print("bars:", bars.shape, "days:", len({t.date() for t in bars.index}))

feat = sb.compute_features(bars, sb.DEFAULTS, daily["close"])
sig = sb.generate_signals(feat, sb.DEFAULTS)
ndays = len({t.date() for t in feat.index})
print("=== SIGNAL COUNT (shipped DEFAULTS, full 64d cached) ===")
print("total signals:", len(sig), "over", ndays, "days ->", round(len(sig)/ndays,3), "/day")
if len(sig):
    print(sig["signal"].value_counts().to_dict())
    print(sig["trigger"].value_counts().to_dict())

# ---- PROBE 1: cross-day rolling-window bleed --------------------------------
# imb rolling(30) and relvol slow rolling(50) do NOT reset at the day boundary
# because df is a continuous regular-session frame. Check feature values in the
# first minutes of a day: do they depend on the prior day's tail?
day = pd.Series(feat.index.date, index=feat.index)
first_days = sorted(set(day))
# Recompute features on a SINGLE isolated day and compare to the multi-day frame
probe_day = pd.Timestamp("2026-07-02").date()
iso = bars[pd.Series(bars.index.date, index=bars.index) == probe_day]
feat_iso = sb.compute_features(iso, sb.DEFAULTS, daily["close"])
feat_multi = feat[day == probe_day]
cols = ["imb", "relvol"]
join = feat_multi[cols].join(feat_iso[cols], rsuffix="_iso")
# early bars where the 50-bar slow window reaches into the prior day
early = join.head(50)
maxdiff = {c: float((join[c]-join[c+"_iso"]).abs().max()) for c in cols}
early_diff = {c: float((early[c]-early[c+"_iso"]).abs().max()) for c in cols}
print("\n=== PROBE 1: cross-day rolling bleed (isolated-day vs multi-day feature) ===")
print("max abs diff over full day:", maxdiff)
print("max abs diff in first 50 bars:", early_diff)

# ---- PROBE 2: tune() target-fitting (in-sample selection) -------------------
# Does the tuner pick thresholds using knowledge of the two target events?
week_1m = dl.intraday(client, "TSLA", "1min", "2026-06-29", "2026-07-02")
base_1m = dl.intraday(client, "TSLA", "1min", "2026-05-04", "2026-06-26")
wf = sb.compute_features(week_1m, sb.DEFAULTS, daily["close"])
bf = sb.compute_features(base_1m, sb.DEFAULTS, daily["close"])
bdays = len({t.date() for t in bf.index})
chosen, trials = sb.tune(wf, bf, bdays)
print("\n=== PROBE 2: tuner ===")
print("chosen buy/sell thresh:", chosen["buy_thresh"], chosen["sell_thresh"])
print("score components reward catching Jul-2 SELL & Jun-29 BUY (the known events).")
best = max(trials, key=lambda t: t["score"])
print("best trial:", {k: best[k] for k in ("buy_thresh","sell_thresh","score","sell_by_1005","buy_in_morning_drive","baseline_signals_per_day")})

# ---- PROBE 3: entry-fill optimism (signal-bar close vs next-bar open) --------
fwd = sb.forward_returns(feat, sig)
def fwd_nextopen(feat, signals, horizons=(15,30,60)):
    closes = feat["close"]; opens = feat["open"]
    rows=[]
    for _, r in signals.iterrows():
        dbars = feat[(feat.index.date==r["ts"].date()) & (feat.index > r["ts"])]
        if dbars.empty: continue
        entry = float(dbars["open"].iloc[0])  # realistic: next bar open
        rr = {"ts": r["ts"], "signal": r["signal"]}
        for h in horizons:
            tgt = r["ts"] + pd.Timedelta(minutes=h)
            db = closes[(closes.index.date==r["ts"].date()) & (closes.index<=tgt)]
            exitp = float(db.iloc[-1]) if len(db) else np.nan
            f=(exitp/entry-1)*100
            rr[f"fwd_{h}m"]=round(f if r["signal"]=="BUY" else -f,3)
        rows.append(rr)
    return pd.DataFrame(rows)
fwd2 = fwd_nextopen(feat, sig)
print("\n=== PROBE 3: entry fill (close-of-signal-bar vs next-bar-open) ===")
for h in (15,30,60):
    a=fwd[f"fwd_{h}m"].mean() if len(fwd) else float('nan')
    b=fwd2[f"fwd_{h}m"].mean() if len(fwd2) else float('nan')
    print(f"fwd_{h}m mean: signal-close-entry={a:+.3f}%  next-open-entry={b:+.3f}%  delta={a-b:+.3f}%")

# ---- PROBE 4: shuffled-label null for the forward returns --------------------
# Are managed outcomes distinguishable from random entries on the same days?
aud = sb.audit_signals(feat, sig, sb.DEFAULTS["target_pct"])
print("\n=== PROBE 4: shuffled-entry null (managed return) ===")
print("n signals:", len(aud), "observed mean managed:", round(aud["managed"].mean(),3) if len(aud) else None)
rng = np.random.default_rng(0)
null_means=[]
by_day = {d: feat[feat.index.date==d] for d in set(feat.index.date)}
for it in range(1000):
    vals=[]
    for _, r in sig.iterrows():
        db = by_day[r["ts"].date()]
        db = db[db.index < db.index[-1]]
        if db.empty: continue
        rt = rng.choice(db.index)
        sgn = 1 if r["signal"]=="BUY" else -1
        path = (by_day[r["ts"].date()].loc[by_day[r["ts"].date()].index>rt, "close"]/float(db.loc[rt,"close"])-1)*100*sgn
        vals.append(float(path.iloc[-1]) if len(path) else 0.0)
    null_means.append(np.mean(vals) if vals else 0.0)
null_means=np.array(null_means)
if len(aud):
    obs=aud["to_close"].mean()
    p=(null_means>=obs).mean()
    print(f"observed to_close mean={obs:+.3f}%  null mean={null_means.mean():+.3f}%  p(null>=obs)={p:.3f}")

print("\nDONE")
