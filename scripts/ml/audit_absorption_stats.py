"""Statistical-validity audit of scripts/absorption_backtest.py.
Recomputes the OOS distribution, t-test, a block/day-shuffled null, cost
sensitivity, and a stop-managed variant to check the PLAYBOOK +5.3% claim.
Prefix: audit_absorption
"""
import sys, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "src")
import numpy as np, pandas as pd
from scipy import stats
from tsla_decoded.config import load_settings
from tsla_decoded.fmp_client import FMPClient
from tsla_decoded import data_loader as dl
from tsla_decoded.features import anchored_vwap
sys.path.insert(0, "scripts")
import absorption_backtest as ab

s = load_settings()
c = FMPClient(s.api_key, s.cache_dir)
m = dl.intraday(c, "TSLA", "1min", "2026-04-01", "2026-07-02")
reg = ab.signals(m)
bt = ab.backtest(reg)
bt["date"] = bt["ts"].dt.date
oos = bt[bt["ts"].dt.date < pd.Timestamp("2026-07-02").date()].copy()
n = len(oos)
print(f"n_total={len(bt)} n_oos={n} unique_days_oos={oos['date'].nunique()}")

for col in ("fwd30","fwd60","eod"):
    v = oos[col].dropna().values
    t,p = stats.ttest_1samp(v, 0.0)
    # one-sample against 0; also Wilcoxon
    try: w,pw = stats.wilcoxon(v)
    except Exception: pw=float('nan')
    print(f"{col}: mean={v.mean():+.3f} sd={v.std(ddof=1):.3f} t={t:.3f} p={p:.3f} "
          f"wilcoxon_p={pw:.3f} win={(v>0).mean():.0%} n={len(v)}")

# ---- Stop-managed variant (reproduce PLAYBOOK: +1.25% target, stop at rejection high) ----
# Stop = reclaim of the rejection-bar high (approx: entry * (1+risk)). Use per-signal
# actual: exit when path hits +target, or MAE stop, else EOD.
TARGET, STOPFRAC = 1.25, None
def managed(reg, target=1.25):
    rows=[]; last={}
    for ts in reg.index[reg.edge]:
        d=ts.date()
        if d in last and (ts-last[d]).total_seconds()<ab.COOLDOWN_MIN*60: continue
        last[d]=ts
        entry=reg.loc[ts,"close"]
        # rejection-bar high in the lookback window as the stop level
        win=reg[(reg.index.date==d)&(reg.index<=ts)].tail(ab.LOOKBACK)
        stop_lvl=win["high"].max()
        da=reg[(reg.index.date==d)&(reg.index>ts)]
        if da.empty: continue
        exitpnl=None
        for _,bar in da.iterrows():
            # short: adverse if price rises to stop
            if bar["high"]>=stop_lvl:
                exitpnl=(entry-stop_lvl)/entry*100; break
            tgt_px=entry*(1-target/100)
            if bar["low"]<=tgt_px:
                exitpnl=target; break
        if exitpnl is None:
            exitpnl=(entry-da["close"].iloc[-1])/entry*100
        rows.append({"ts":ts,"managed":exitpnl})
    return pd.DataFrame(rows)
mg=managed(reg)
mg["date"]=mg["ts"].dt.date
mg_oos=mg[mg["ts"].dt.date < pd.Timestamp("2026-07-02").date()]
mv=mg_oos["managed"].values
print(f"\nSTOP-MANAGED oos: mean={mv.mean():+.3f} cumulative={mv.sum():+.2f} "
      f"win={(mv>0).mean():.0%} n={len(mv)} t={stats.ttest_1samp(mv,0)[0]:.3f} p={stats.ttest_1samp(mv,0)[1]:.3f}")
print("managed all incl anchor cumulative:", round(mg['managed'].sum(),2), "n", len(mg))

# ---- Day-permutation null: is short-at-open-on-these-days better than random days? ----
# Null A: random entry minute on the SAME signal days (controls day selection)
reg_reg = reg[reg.session=="regular"]
by_day={d:reg_reg[reg_reg.index.date==d] for d in set(reg_reg.index.date)}
rng=np.random.default_rng(0)
obs=oos["eod"].mean()
nulls=[]
for _ in range(5000):
    vals=[]
    for d in oos["date"]:
        db=by_day[d]; db=db[db.index<db.index[-1]]
        if db.empty: continue
        rt=rng.choice(db.index); e=float(db.loc[rt,"close"])
        path=(e-by_day[d].loc[by_day[d].index>rt,"close"].iloc[-1])/e*100
        vals.append(path)
    nulls.append(np.mean(vals))
nulls=np.array(nulls)
print(f"\nNULL-A (random entry, same days): obs eod mean={obs:+.3f} "
      f"null mean={nulls.mean():+.3f} p(null>=obs)={(nulls>=obs).mean():.3f}")

# Null B: same time-of-day (09:3x short) on ALL regular days (controls: is it the days or the signal?)
all_days=sorted(by_day)
obs2=oos["eod"].mean()
nulls2=[]
for _ in range(5000):
    days=rng.choice(all_days, size=len(oos["date"]), replace=False)
    vals=[]
    for d in days:
        db=by_day[d]
        e=float(db["close"].iloc[3]) if len(db)>4 else float(db["close"].iloc[0])
        path=(e-db["close"].iloc[-1])/e*100
        vals.append(path)
    nulls2.append(np.mean(vals))
nulls2=np.array(nulls2)
print(f"NULL-B (short ~09:33 on random days): obs={obs2:+.3f} null mean={nulls2.mean():+.3f} "
      f"p(null>=obs)={(nulls2>=obs2).mean():.3f}")

# ---- Cost sensitivity ----
for cps in (0.05,0.10,0.15):  # % round-trip (1-2bps + half spread per side ~ 5-15bps rt)
    net=oos["eod"].values-cps
    t,p=stats.ttest_1samp(net,0)
    print(f"cost {cps:.2f}%/rt -> net eod mean={net.mean():+.3f} win={(net>0).mean():.0%} p={p:.3f}")

# concentration
print("\ntop-2 |eod| contribution to sum:",
      round(oos.reindex(oos['eod'].abs().sort_values(ascending=False).index)['eod'].head(2).sum(),2),
      "of total", round(oos['eod'].sum(),2))
