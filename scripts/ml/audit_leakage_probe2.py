"""Follow-up probes: fix cross-day bleed test, add cost + managed null."""
import os, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
os.environ.setdefault("FMP_API_KEY", "cache-only")
from tsla_decoded.fmp_client import FMPClient
from tsla_decoded import data_loader as dl
from tsla_decoded import signal_backtest as sb

client = FMPClient(api_key=os.environ["FMP_API_KEY"], cache_dir=Path("data/raw"))
bars = dl.intraday(client, "TSLA", "1min", "2026-04-01", "2026-07-02")
daily = dl.daily(client, "TSLA", "2026-04-01", "2026-07-02")
feat = sb.compute_features(bars, sb.DEFAULTS, daily["close"])
sig = sb.generate_signals(feat, sb.DEFAULTS)
day = pd.Series(feat.index.date, index=feat.index)

# ---- PROBE 1 (fixed): compare multi-day early-bar features to isolated-day,
# only where BOTH are non-null. If multi-day has a value where isolated is NaN
# (still warming up), that value came from prior-day rows = cross-day bleed.
probe_day = pd.Timestamp("2026-06-30").date()  # a normal day with a prior day
iso = bars[pd.Series(bars.index.date, index=bars.index) == probe_day]
feat_iso = sb.compute_features(iso, sb.DEFAULTS, daily["close"])
fm = feat[day == probe_day]
print("=== PROBE 1 FIXED: cross-day rolling bleed on", probe_day, "===")
for c, w in [("imb",30),("relvol",50)]:
    multi_nonnull_first = fm[c].notna().idxmax()
    iso_nonnull_first = feat_iso[c].notna().idxmax()
    n_bleed = int((fm[c].notna() & feat_iso[c].isna()).sum())
    print(f"  {c}: first non-null multi={multi_nonnull_first.time()} iso={iso_nonnull_first.time()} "
          f"| bars where multi has value but isolated-day still warming up = {n_bleed}")

# Does a BUY/opening-SELL actually fire during the contaminated warm-up region?
warm = sig[sig.apply(lambda r: feat.loc[r["ts"],"min_of_day"] < 50, axis=1)] if len(sig) else sig
print("  signals firing in first 50 min of a day (relvol window partly prior-day):", len(warm))
print("  breakdown:", warm["trigger"].value_counts().to_dict() if len(warm) else {})

# ---- Managed-return shuffled null + cost sensitivity ----
aud = sb.audit_signals(feat, sig, sb.DEFAULTS["target_pct"])
by_day = {d: feat[feat.index.date==d] for d in set(feat.index.date)}
rng = np.random.default_rng(1)
null_mgd=[]
for _ in range(2000):
    vals=[]
    for _, r in sig.iterrows():
        db = by_day[r["ts"].date()]; db=db[db.index<db.index[-1]]
        if db.empty: continue
        rt=rng.choice(db.index); sgn=1 if r["signal"]=="BUY" else -1
        entry=float(by_day[r["ts"].date()].loc[rt,"close"])
        after=by_day[r["ts"].date()].loc[by_day[r["ts"].date()].index>rt]
        path=(after["close"]/entry-1)*100*sgn
        mgd=float(path.iloc[-1]) if len(path) else 0.0
        for ts,v in path.items():
            if v>=sb.DEFAULTS["target_pct"]: mgd=sb.DEFAULTS["target_pct"]; break
            crossed=(after.loc[ts,"close"]<after.loc[ts,"vwap"]) if sgn==1 else (after.loc[ts,"close"]>after.loc[ts,"vwap"])
            if crossed: mgd=float(v); break
        vals.append(mgd)
    null_mgd.append(np.mean(vals) if vals else 0.0)
null_mgd=np.array(null_mgd)
obs=aud["managed"].mean()
print("\n=== PROBE 4b: managed-return shuffled-entry null ===")
print(f"observed managed mean={obs:+.3f}%  null mean={null_mgd.mean():+.3f}%  "
      f"p(null>=obs)={(null_mgd>=obs).mean():.3f}")

# ---- Cost sensitivity on forward returns ----
fwd = sb.forward_returns(feat, sig)
print("\n=== COST SENSITIVITY (round-trip ~ 2*(1.5bps + half-spread)) ===")
# TSLA ~ $300, spread ~1-2 cents -> half-spread ~ 0.5c/300 ~ 0.0017%. per side ~1.5bps+0.17bps
cost_rt = 2*(0.015 + 0.02)  # % round trip ~0.07%  (1.5bps fee + ~2bps half-spread per side)
for h in (15,30,60):
    col=fwd[f"fwd_{h}m"].dropna()
    from scipy import stats
    t,p = stats.ttest_1samp(col,0)
    net=col.mean()-cost_rt
    print(f"  fwd_{h}m: n={len(col)} gross={col.mean():+.3f}% t={t:.2f} p={p:.3f} "
          f"hit={ (col>0).mean():.0%} | net-of-{cost_rt:.2f}%cost={net:+.3f}%")
print("\nDONE2")
