"""Fast: fixed cross-day bleed test + cost sensitivity + managed null (300 iters)."""
import os, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
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

probe_day = pd.Timestamp("2026-06-30").date()
iso = bars[pd.Series(bars.index.date, index=bars.index) == probe_day]
feat_iso = sb.compute_features(iso, sb.DEFAULTS, daily["close"])
fm = feat[day == probe_day]
print("=== PROBE 1 FIXED: cross-day rolling bleed on", probe_day, "===")
for c in ("imb","relvol"):
    fm_first = fm[c].notna().idxmax(); iso_first = feat_iso[c].notna().idxmax()
    n_bleed = int((fm[c].notna() & feat_iso[c].isna()).sum())
    print(f"  {c}: first non-null multi-day={fm_first.time()} vs isolated-day={iso_first.time()} "
          f"-> {n_bleed} early bars valued only via prior-day rows (bleed)")
warm = sig[[feat.loc[t,"min_of_day"] < 50 for t in sig["ts"]]] if len(sig) else sig
print("  signals in first 50 min (relvol-50 window spans prior day):", len(warm),
      warm["trigger"].value_counts().to_dict() if len(warm) else {})

fwd = sb.forward_returns(feat, sig)
cost_rt = 2*(0.015 + 0.02)  # ~0.07% round trip: 1.5bps fee + ~2bps half-spread per side
print("\n=== COST SENSITIVITY (n, gross mean, t/p vs 0, net of ~%.2f%% round-trip) ==="%cost_rt)
for h in (15,30,60):
    col = fwd[f"fwd_{h}m"].dropna()
    t,p = stats.ttest_1samp(col,0)
    print(f"  fwd_{h}m: n={len(col)} gross={col.mean():+.3f}% t={t:.2f} p={p:.3f} "
          f"hit={(col>0).mean():.0%} net={col.mean()-cost_rt:+.3f}%")

aud = sb.audit_signals(feat, sig, sb.DEFAULTS["target_pct"])
by_day = {d: feat[feat.index.date==d] for d in set(feat.index.date)}
rng = np.random.default_rng(1); null=[]
for _ in range(300):
    vals=[]
    for _, r in sig.iterrows():
        db = by_day[r["ts"].date()]; dbx=db[db.index<db.index[-1]]
        if dbx.empty: continue
        rt=rng.choice(dbx.index); sgn=1 if r["signal"]=="BUY" else -1
        after=db.loc[db.index>rt]; entry=float(db.loc[rt,"close"])
        path=(after["close"]/entry-1)*100*sgn
        m=float(path.iloc[-1]) if len(path) else 0.0
        for ts,v in path.items():
            if v>=sb.DEFAULTS["target_pct"]: m=sb.DEFAULTS["target_pct"]; break
            cr=(after.loc[ts,"close"]<after.loc[ts,"vwap"]) if sgn==1 else (after.loc[ts,"close"]>after.loc[ts,"vwap"])
            if cr: m=float(v); break
        vals.append(m)
    null.append(np.mean(vals) if vals else 0.0)
null=np.array(null); obs=aud["managed"].mean()
print("\n=== MANAGED shuffled-entry null (300 iters) ===")
print(f"  observed managed mean={obs:+.3f}%  null mean={null.mean():+.3f}%  p(null>=obs)={(null>=obs).mean():.3f}")
print("DONE3")
