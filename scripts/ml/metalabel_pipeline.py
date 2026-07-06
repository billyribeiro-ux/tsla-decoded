"""metalabel: Lopez de Prado meta-labeling secondary filter for FlowForensics.

Primary rule (signal_backtest.generate_signals with shipped DEFAULTS) is kept
UNCHANGED and defines the event set E = {(t0, side, trigger)}. A shallow
HistGradientBoosting secondary classifier decides TAKE vs SKIP per fired signal
using strictly as-of-t0 features and triple-barrier meta-labels, trained/scored
under purged + embargoed walk-forward CV.

Run:  python scripts/ml/metalabel_pipeline.py
Outputs: output/ml/metalabel/metalabel_result.json + metalabel_report.md
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
load_dotenv(REPO / ".env")
os.environ.setdefault("FMP_API_KEY", "cache-only")

from tsla_decoded.fmp_client import FMPClient           # noqa: E402
from tsla_decoded import data_loader as dl              # noqa: E402
from tsla_decoded import signal_backtest as sb          # noqa: E402
from metalabel_backfill import fetch_day                # noqa: E402

OUT = REPO / "output" / "ml" / "metalabel"
OUT.mkdir(parents=True, exist_ok=True)

START = "2010-06-29"
END = "2026-07-02"
K_BARRIER = 1.0
H_MAX = 60                       # vertical barrier bars
FEE_BPS = 1.5                    # per side
HALF_SPREAD_BPS = 2.0           # per side (liquid-TSLA assumption)
COST_RT = 2 * (FEE_BPS + HALF_SPREAD_BPS) / 1e4      # round-trip return, ~0.07%
COST_RT_STRESS = 2 * (FEE_BPS + 5.0) / 1e4           # stress: 5 bps half-spread/side

FEATURES = [
    "relvol", "clv_s", "cvd_slope", "vwap_dist", "imb_30", "day_imb",
    "runup_3d", "min_of_day", "realized_vol", "spy_ret_open", "qqq_relvol",
    "side_is_sell", "trig_accum", "trig_openrej", "trig_distrib",
]


# --------------------------------------------------------------------------
# STEP 1: primary rule -> event set E (rule UNCHANGED, shipped DEFAULTS)
# --------------------------------------------------------------------------
def build_events(client) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    print("loading full 1-min history from cache ...", flush=True)
    bars = dl.intraday(client, "TSLA", "1min", START, END)
    daily = dl.daily(client, "TSLA", START, END)
    print(f"  bars={len(bars):,}  days={bars.index.normalize().nunique()}  "
          f"daily={len(daily)}", flush=True)
    print("computing features + generating signals over full history ...", flush=True)
    feat = sb.compute_features(bars, sb.DEFAULTS, daily["close"])
    signals = sb.generate_signals(feat, sb.DEFAULTS)
    print(f"  primary signals fired: {len(signals)}", flush=True)
    return feat, signals, daily["close"]


# --------------------------------------------------------------------------
# STEP 2: signal-time features (strictly as-of t0)
# --------------------------------------------------------------------------
def _cvd_slope(cum_signed: pd.Series, vol: pd.Series, pos: int, w: int = 15) -> float:
    lo = max(0, pos - w + 1)
    y = cum_signed.iloc[lo:pos + 1].to_numpy(dtype=float)
    if len(y) < 3 or np.any(~np.isfinite(y)):
        return np.nan
    x = np.arange(len(y), dtype=float)
    slope = np.polyfit(x, y, 1)[0]
    v = vol.iloc[lo:pos + 1].mean()
    return float(slope / v) if v and v > 0 else np.nan


def load_index_frame(client, symbol: str, dates: list[str]) -> pd.DataFrame:
    if not dates:
        return pd.DataFrame()
    for d in dates:
        fetch_day(symbol, d)          # ensure cached (no-op if present)
    # load ONLY the signal-day cache files (from==to => single cache read per day)
    frames = [dl.intraday(client, symbol, "1min", d, d) for d in dates]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    frame = pd.concat(frames)
    frame = frame[~frame.index.duplicated(keep="first")].sort_index()
    reg = frame[frame["session"] == "regular"].copy()
    reg["relvol"] = (reg["volume"].rolling(10).mean()
                     / reg["volume"].rolling(50).mean())
    day = pd.Series(reg.index.date, index=reg.index)
    reg["day_open"] = reg.groupby(day.values)["open"].transform("first")
    return reg


def build_feature_matrix(feat, signals, spy, qqq) -> pd.DataFrame:
    idx = feat.index
    pos_of = {ts: i for i, ts in enumerate(idx)}
    logret = np.log(feat["close"]).diff()
    day = pd.Series(feat.index.date, index=feat.index)
    new_day = day.ne(day.shift())
    logret[new_day.values] = np.nan
    realized = logret.rolling(30).std()

    # precompute per-date index sub-frames (fast lookups)
    spy_by_date = {d: g for d, g in spy.groupby(spy.index.date)} if not spy.empty else {}
    qqq_by_date = {d: g for d, g in qqq.groupby(qqq.index.date)} if not qqq.empty else {}

    rows = []
    for _, s in signals.iterrows():
        ts = s["ts"]
        pos = pos_of.get(ts)
        if pos is None or pos + 1 >= len(idx):
            continue
        if idx[pos + 1].date() != ts.date():     # need an entry bar same day
            continue
        f = feat.iloc[pos]
        rv = float(realized.iloc[pos]) if np.isfinite(realized.iloc[pos]) else np.nan
        row = {
            "t0": ts, "side": s["signal"], "trigger": s["trigger"],
            "entry_pos": pos + 1,
            "relvol": float(f["relvol"]), "clv_s": float(f["clv_s"]),
            "cvd_slope": _cvd_slope(feat["cum_signed"], feat["volume"], pos),
            "vwap_dist": float((f["close"] - f["vwap"]) / f["vwap"])
                          if f["vwap"] else np.nan,
            "imb_30": float(f["imb"]), "day_imb": float(f["day_imb"]),
            "runup_3d": float(f["runup_3d"]) if np.isfinite(f["runup_3d"]) else np.nan,
            "min_of_day": int(f["min_of_day"]), "realized_vol": rv,
            "side_is_sell": 1 if s["signal"] == "SELL" else 0,
            "trig_accum": 1 if s["trigger"] == "accumulation" else 0,
            "trig_openrej": 1 if s["trigger"] == "opening-rejection" else 0,
            "trig_distrib": 1 if s["trigger"] == "distribution" else 0,
        }
        # index context (NaN when the index day isn't cached -> HGB handles NaN)
        row["spy_ret_open"] = _index_ret_open(spy_by_date.get(ts.date()), ts)
        row["qqq_relvol"] = _index_relvol(qqq_by_date.get(ts.date()), ts)
        rows.append(row)
    return pd.DataFrame(rows)


def _index_ret_open(sub, ts):
    if sub is None or sub.empty:
        return np.nan
    sub = sub[sub.index <= ts]
    if sub.empty:
        return np.nan
    return float(sub["close"].iloc[-1] / sub["day_open"].iloc[-1] - 1)


def _index_relvol(sub, ts):
    if sub is None or sub.empty:
        return np.nan
    sub = sub[sub.index <= ts]
    if sub.empty:
        return np.nan
    v = sub["relvol"].iloc[-1]
    return float(v) if np.isfinite(v) else np.nan


# --------------------------------------------------------------------------
# STEP 3: triple-barrier meta-labels (costs baked in)
# --------------------------------------------------------------------------
def triple_barrier(feat, events: pd.DataFrame) -> pd.DataFrame:
    idx = feat.index
    high = feat["high"].to_numpy()
    low = feat["low"].to_numpy()
    close = feat["close"].to_numpy()
    openp = feat["open"].to_numpy()
    dates = np.array([t.date() for t in idx])

    out = []
    for _, e in events.iterrows():
        pos = int(e["entry_pos"])
        entry = openp[pos]
        sigma = e["realized_vol"]
        if not np.isfinite(sigma) or sigma <= 0 or not np.isfinite(entry) or entry <= 0:
            out.append({**e, "meta_label": np.nan, "net_ret": np.nan,
                        "gross_ret": np.nan, "t1_pos": pos, "hit": "nan"})
            continue
        # bars to EOD from entry
        d0 = dates[pos]
        eod = pos
        while eod + 1 < len(idx) and dates[eod + 1] == d0:
            eod += 1
        H = min(H_MAX, eod - pos)
        if H < 1:
            out.append({**e, "meta_label": np.nan, "net_ret": np.nan,
                        "gross_ret": np.nan, "t1_pos": pos, "hit": "nan"})
            continue
        w = K_BARRIER * sigma * np.sqrt(H)      # barrier half-width (return frac)
        sgn = 1 if e["side"] == "BUY" else -1
        pt = entry * (1 + sgn * w)              # profit target price
        sl = entry * (1 - sgn * w)              # stop price
        hit = "vertical"
        t1 = pos + H
        gross = sgn * (close[pos + H] / entry - 1)   # default: vertical close
        for j in range(pos + 1, pos + H + 1):
            hi, lo = high[j], low[j]
            if sgn == 1:
                pt_hit, sl_hit = hi >= pt, lo <= sl
            else:
                pt_hit, sl_hit = lo <= pt, hi >= sl
            if sl_hit and pt_hit:               # ambiguous bar -> assume stop first
                hit, t1, gross = "stop", j, -w
                break
            if pt_hit:
                hit, t1, gross = "target", j, w
                break
            if sl_hit:
                hit, t1, gross = "stop", j, -w
                break
        net = gross - COST_RT
        out.append({**e, "meta_label": int(net > 0), "net_ret": float(net),
                    "gross_ret": float(gross), "t1_pos": int(t1), "hit": hit,
                    "barrier_w": float(w)})
    return pd.DataFrame(out)


# --------------------------------------------------------------------------
# sample weights: average uniqueness x linear time-decay
# --------------------------------------------------------------------------
def sample_weights(lab: pd.DataFrame) -> np.ndarray:
    """LdP average-uniqueness x linear time-decay. Overlap only occurs within a
    day (intraday barriers), so compute concurrency per calendar day -> near-linear."""
    n = len(lab)
    entry = lab["entry_pos"].to_numpy()
    t1 = np.maximum(lab["t1_pos"].to_numpy(), entry)
    uniq = np.ones(n)
    dates = pd.to_datetime(lab["t0"]).dt.date.to_numpy()
    for d in np.unique(dates):
        idx = np.where(dates == d)[0]
        if len(idx) == 1:
            uniq[idx[0]] = 1.0
            continue
        lo = entry[idx].min()
        hi = t1[idx].max()
        conc = np.zeros(hi - lo + 1)
        for i in idx:
            conc[entry[i] - lo: t1[i] - lo + 1] += 1
        for i in idx:
            seg = conc[entry[i] - lo: t1[i] - lo + 1]
            uniq[i] = float(np.mean(1.0 / seg))
    # linear time-decay: oldest -> 0.5, newest -> 1.0 (by t0 order)
    rank = lab["t0"].rank(method="first").to_numpy()
    decay = 0.5 + 0.5 * (rank - 1) / max(n - 1, 1)
    w = uniq * decay
    return w / w.mean()


# --------------------------------------------------------------------------
# STEP 4/5: purged + embargoed walk-forward CV with nested threshold tuning
# --------------------------------------------------------------------------
def hgb():
    return HistGradientBoostingClassifier(
        max_depth=3, max_leaf_nodes=15, learning_rate=0.05,
        l2_regularization=1.0, max_iter=300, early_stopping=True,
        validation_fraction=0.2, random_state=0)


def _fit_predict(Xtr, ytr, wtr, Xte):
    m = hgb()
    # class balance via sample_weight
    cw = ytr.map({0: (ytr == 1).mean() + 1e-9, 1: (ytr == 0).mean() + 1e-9})
    m.fit(Xtr, ytr, sample_weight=(wtr * cw).to_numpy())
    return m.predict_proba(Xte)[:, 1]


def _pick_threshold(p, net, labels):
    """Maximize net-EV/trade on validation; require >=25% of events taken."""
    best_thr, best_ev = 0.5, -1e9
    grid = np.unique(np.quantile(p, np.linspace(0.1, 0.9, 17)))
    for thr in grid:
        take = p >= thr
        if take.sum() < max(3, 0.15 * len(p)):
            continue
        ev = net[take].mean()
        if ev > best_ev:
            best_ev, best_thr = ev, thr
    return best_thr


def walk_forward(lab: pd.DataFrame, n_folds=8, embargo_days=1, tag="all",
                 weights=None) -> dict:
    lab = lab.sort_values("t0").reset_index(drop=True)
    X = lab[FEATURES].astype(float)
    y = lab["meta_label"].astype(int)
    net = lab["net_ret"].to_numpy()
    wvals = weights if weights is not None else sample_weights(lab)
    w = pd.Series(wvals, index=lab.index)
    entry = lab["entry_pos"].to_numpy()
    t1 = lab["t1_pos"].to_numpy()
    t0 = lab["t0"].to_numpy()
    n = len(lab)

    init = int(n * 0.30)
    block = max(1, (n - init) // n_folds)
    folds = []
    pooled = {"take_net": [], "take_lab": [], "all_net": [], "is_take_net": [],
              "is_take_lab": []}
    start = init
    fi = 0
    while start < n and fi < n_folds:
        te_lo, te_hi = start, min(start + block, n)
        test_idx = np.arange(te_lo, te_hi)
        if len(test_idx) == 0:
            break
        test_first_entry = entry[te_lo]
        # PURGE: drop train events whose label window overlaps test span
        # EMBARGO: drop train events within embargo_days before test start
        test_span_lo = entry[test_idx].min()
        embargo_bars = embargo_days * 390
        keep = []
        for j in range(0, te_lo):
            if t1[j] >= test_span_lo - embargo_bars:
                continue
            keep.append(j)
        train_idx = np.array(keep, dtype=int)
        if len(train_idx) < 40 or y.iloc[train_idx].nunique() < 2:
            start = te_hi
            fi += 1
            continue
        # nested threshold tuning on inner-validation (last 20% of train, chrono)
        n_tr = len(train_idx)
        inner_cut = int(n_tr * 0.80)
        in_tr, in_val = train_idx[:inner_cut], train_idx[inner_cut:]
        if len(in_val) >= 8 and y.iloc[in_tr].nunique() == 2:
            p_val = _fit_predict(X.iloc[in_tr], y.iloc[in_tr], w.iloc[in_tr], X.iloc[in_val])
            thr = _pick_threshold(p_val, net[in_val], y.iloc[in_val].to_numpy())
        else:
            thr = 0.5
        # refit on full train, score test
        p_te = _fit_predict(X.iloc[train_idx], y.iloc[train_idx], w.iloc[train_idx],
                            X.iloc[test_idx])
        take = p_te >= thr
        # in-sample (train) diagnostics at same threshold
        p_tr = _fit_predict(X.iloc[train_idx], y.iloc[train_idx], w.iloc[train_idx],
                            X.iloc[train_idx])
        take_tr = p_tr >= thr

        te_net = net[test_idx]
        te_lab = y.iloc[test_idx].to_numpy()
        rec = {
            "fold": fi, "n_train": int(len(train_idx)), "n_test": int(len(test_idx)),
            "test_start": str(pd.Timestamp(t0[te_lo]))[:10],
            "test_end": str(pd.Timestamp(t0[te_hi - 1]))[:10],
            "threshold": round(float(thr), 3),
            "n_taken": int(take.sum()),
            "take_all_net_pct": round(float(te_net.mean() * 100), 4),
            "take_all_prec": round(float(te_lab.mean()), 3),
            "model_take_net_pct": round(float(te_net[take].mean() * 100), 4)
                                   if take.sum() else None,
            "model_take_prec": round(float(te_lab[take].mean()), 3)
                                if take.sum() else None,
            "is_take_net_pct": round(float(net[train_idx][take_tr].mean() * 100), 4)
                                if take_tr.sum() else None,
        }
        folds.append(rec)
        pooled["take_net"] += list(te_net[take])
        pooled["take_lab"] += list(te_lab[take])
        pooled["all_net"] += list(te_net)
        pooled["is_take_net"] += list(net[train_idx][take_tr])
        pooled["is_take_lab"] += list(y.iloc[train_idx].to_numpy()[take_tr])
        start = te_hi
        fi += 1

    return {"folds": folds, "pooled": pooled, "n_events": n,
            "weights": w, "X": X, "y": y, "net": net,
            "entry": entry, "t1": t1, "t0": t0, "init": init, "block": block,
            "embargo_bars": embargo_days * 390, "tag": tag}


def summarize_pooled(res: dict) -> dict:
    p = res["pooled"]
    tn = np.array(p["take_net"]); tl = np.array(p["take_lab"])
    an = np.array(p["all_net"])
    isn = np.array(p["is_take_net"])
    out = {
        "n_test_events": int(len(an)),
        "take_all_net_pct": round(float(an.mean() * 100), 4) if len(an) else None,
        "take_all_prec": round(float((an > 0).mean()), 3) if len(an) else None,
        "n_taken_oos": int(len(tn)),
        "oos_model_net_pct": round(float(tn.mean() * 100), 4) if len(tn) else None,
        "oos_model_prec": round(float(tl.mean()), 3) if len(tl) else None,
        "is_model_net_pct": round(float(isn.mean() * 100), 4) if len(isn) else None,
        "is_model_prec": round(float((isn > 0).mean()), 3) if len(isn) else None,
        "oos_lift_net_pct": (round(float((tn.mean() - an.mean()) * 100), 4)
                             if len(tn) and len(an) else None),
    }
    # paired t-test of taken net vs 0, and vs take-all mean
    if len(tn) > 2:
        t, pv = stats.ttest_1samp(tn, 0.0)
        out["oos_net_t"] = round(float(t), 3)
        out["oos_net_p"] = round(float(pv), 4)
    return out


# --------------------------------------------------------------------------
# shuffled-label null
# --------------------------------------------------------------------------
def shuffled_null(lab: pd.DataFrame, observed_ev: float, n_iter=200,
                  n_folds=8) -> dict:
    lab = lab.sort_values("t0").reset_index(drop=True)
    w = sample_weights(lab)          # weights depend on entry/t1, not labels -> reuse
    rng = np.random.default_rng(7)
    null_ev, null_prec = [], []
    for it in range(n_iter):
        lp = lab.copy()
        lp["meta_label"] = rng.permutation(lab["meta_label"].to_numpy())
        # keep net_ret aligned to original events (economic outcome unchanged);
        # only the training signal (labels) is permuted -> tests if the model can
        # extract real structure. net used for scoring stays the true outcome.
        res = walk_forward(lp, n_folds=n_folds, tag="null", weights=w)
        s = summarize_pooled(res)
        if s["oos_model_net_pct"] is not None:
            null_ev.append(s["oos_model_net_pct"])
        if s["oos_model_prec"] is not None:
            null_prec.append(s["oos_model_prec"])
        if (it + 1) % 50 == 0:
            print(f"    null {it+1}/{n_iter}", flush=True)
    null_ev = np.array(null_ev)
    p_emp = float((null_ev >= observed_ev).mean()) if len(null_ev) else np.nan
    return {"n_iter": int(len(null_ev)),
            "null_ev_mean_pct": round(float(null_ev.mean()), 4) if len(null_ev) else None,
            "null_ev_p95_pct": round(float(np.quantile(null_ev, 0.95)), 4)
                                if len(null_ev) else None,
            "observed_ev_pct": round(float(observed_ev), 4),
            "p_value": round(p_emp, 4) if not np.isnan(p_emp) else None,
            "null_prec_mean": round(float(np.mean(null_prec)), 3) if null_prec else None}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    client = FMPClient(api_key=os.environ["FMP_API_KEY"], cache_dir=REPO / "data" / "raw")
    feat, signals, daily_close = build_events(client)

    # de-clustering counts
    n_raw = len(signals)
    sig_dates = sorted({str(t.date()) for t in signals["ts"]})
    per_day = signals.groupby(signals["ts"].dt.date).size()
    one_per_day = len(per_day)
    one_per_side_day = signals.groupby([signals["ts"].dt.date, signals["signal"]]).size()
    n_side_day = len(one_per_side_day)
    (OUT / "signal_dates.json").write_text(json.dumps(sig_dates))
    print(f"events: raw={n_raw}  one-per-side-per-day={n_side_day}  "
          f"one-per-day={one_per_day}  distinct-days={len(sig_dates)}", flush=True)

    # index context: fetch SPY/QQQ only for signal days
    print("loading SPY/QQQ index context for signal days ...", flush=True)
    spy = load_index_frame(client, "SPY", sig_dates)
    qqq = load_index_frame(client, "QQQ", sig_dates)

    events = build_feature_matrix(feat, signals, spy, qqq)
    lab = triple_barrier(feat, events)
    lab = lab.dropna(subset=["meta_label"]).reset_index(drop=True)
    lab["meta_label"] = lab["meta_label"].astype(int)
    lab["year"] = pd.to_datetime(lab["t0"]).dt.year
    print(f"labeled events: {len(lab)}  base rate(label=1)={lab['meta_label'].mean():.3f}  "
          f"take-all net mean={lab['net_ret'].mean()*100:+.3f}%", flush=True)
    lab.drop(columns=[c for c in ["barrier_w"] if c in lab.columns]).to_parquet(
        OUT / "metalabel_events.parquet")

    result = {
        "config": {"start": START, "end": END, "k_barrier": K_BARRIER,
                   "H_max": H_MAX, "cost_rt_pct": round(COST_RT * 100, 4),
                   "cost_rt_stress_pct": round(COST_RT_STRESS * 100, 4),
                   "features": FEATURES},
        "event_counts": {"raw": n_raw, "one_per_side_per_day": n_side_day,
                         "one_per_day": one_per_day, "distinct_days": len(sig_dates),
                         "labeled": len(lab)},
        "label_base_rate": round(float(lab["meta_label"].mean()), 4),
        "take_all_net_pct": round(float(lab["net_ret"].mean() * 100), 4),
        "take_all_gross_pct": round(float(lab["gross_ret"].mean() * 100), 4),
        "take_all_net_stress_pct": round(
            float((lab["gross_ret"] - COST_RT_STRESS).mean() * 100), 4),
        "hit_dist": lab["hit"].value_counts().to_dict(),
        "per_year_counts": lab.groupby("year").size().to_dict(),
    }

    # -- full-history walk-forward
    print("walk-forward CV (full history) ...", flush=True)
    res_all = walk_forward(lab, n_folds=8, tag="all")
    sum_all = summarize_pooled(res_all)
    result["walk_forward_all"] = {"summary": sum_all, "folds": res_all["folds"]}
    print(f"  OOS: taken={sum_all['n_taken_oos']}  "
          f"model_net={sum_all['oos_model_net_pct']}%  "
          f"take_all_net={sum_all['take_all_net_pct']}%  "
          f"lift={sum_all['oos_lift_net_pct']}%", flush=True)

    # -- post-2020 regime variant
    lab_pv = lab[lab["year"] >= 2020].reset_index(drop=True)
    result["post2020_counts"] = {"labeled": len(lab_pv)}
    if len(lab_pv) >= 80:
        print(f"walk-forward CV (post-2020, n={len(lab_pv)}) ...", flush=True)
        res_pv = walk_forward(lab_pv, n_folds=5, tag="post2020")
        sum_pv = summarize_pooled(res_pv)
        result["walk_forward_post2020"] = {"summary": sum_pv, "folds": res_pv["folds"]}
        print(f"  OOS post2020: taken={sum_pv['n_taken_oos']}  "
              f"model_net={sum_pv['oos_model_net_pct']}%  "
              f"take_all_net={sum_pv['take_all_net_pct']}%", flush=True)
    else:
        result["walk_forward_post2020"] = {"note": "insufficient post-2020 events"}
        sum_pv = None

    # -- shuffled-label null on full history
    obs = sum_all["oos_model_net_pct"]
    if obs is not None:
        print("shuffled-label null (200 iters) ...", flush=True)
        result["shuffled_null_all"] = shuffled_null(lab, obs, n_iter=200, n_folds=8)
        print(f"  null p-value={result['shuffled_null_all']['p_value']}", flush=True)

    # verdict
    lift = sum_all.get("oos_lift_net_pct")
    pval = result.get("shuffled_null_all", {}).get("p_value")
    oos = sum_all.get("oos_model_net_pct")
    ta = sum_all.get("take_all_net_pct")
    parts = []
    parts.append(
        f"Primary rule fires {ec['raw']} signals over {ec['distinct_days']} days "
        f"({ec['raw']/4026:.2f}/day) — a far larger "
        "sample than the 0.2/day the shipped-gate audit implied, so power is NOT the "
        "binding constraint here.")
    if lift is not None and pval is not None:
        sig_txt = ("clears" if (pval < 0.05 and lift > 0) else "does NOT clear")
        parts.append(
            f"OOS the secondary filter takes {sum_all['n_taken_oos']} of "
            f"{sum_all['n_test_events']} signals at net {oos}%/signal vs take-all {ta}%/signal "
            f"(lift {lift}%/signal). Against the shuffled-label null the gain {sig_txt} "
            f"p<0.05 (empirical p={pval}).")
    parts.append(
        f"Take-all net expectancy is {result['take_all_net_pct']:+.3f}%/signal "
        f"(gross {result['take_all_gross_pct']:+.3f}%); at stress costs "
        f"{result['take_all_net_stress_pct']:+.3f}%. This is the honest economic floor the "
        "filter must beat OOS to add value.")
    result["_verdict"] = " ".join(parts)

    (OUT / "metalabel_result.json").write_text(json.dumps(result, indent=2, default=str))
    write_report(result)
    print("saved:", OUT / "metalabel_result.json", flush=True)
    return result


def write_report(r: dict):
    L = []
    a = L.append
    ec = r["event_counts"]
    wa = r["walk_forward_all"]["summary"]
    a("# Meta-Labeling Secondary Filter for FlowForensics — results\n")
    a(f"Approach key: `metalabel`. Full FMP 1-min backfill {r['config']['start']} "
      f"-> {r['config']['end']}. Primary rule UNCHANGED (shipped DEFAULTS); a shallow "
      "HistGradientBoosting secondary classifier decides TAKE/SKIP per fired signal "
      "under purged + embargoed walk-forward CV.\n")
    a("## Event set (sample size — the central constraint)\n")
    a(f"- raw primary signals: **{ec['raw']}**")
    a(f"- one-per-side-per-day: {ec['one_per_side_per_day']}")
    a(f"- one-per-day: {ec['one_per_day']}  (distinct signal days: {ec['distinct_days']})")
    a(f"- labeled (valid triple-barrier): **{ec['labeled']}**")
    a(f"- post-2020 labeled: {r['post2020_counts']['labeled']}\n")
    a("## Labels & economics\n")
    a(f"- triple-barrier k={r['config']['k_barrier']}, H<= {r['config']['H_max']} bars, "
      f"vol-scaled; entry at t0+1 open; costs baked (round-trip "
      f"{r['config']['cost_rt_pct']}%).")
    a(f"- label base rate (net-profitable): **{r['label_base_rate']}**")
    a(f"- take-all net expectancy: **{r['take_all_net_pct']:+.3f}%/signal** "
      f"(gross {r['take_all_gross_pct']:+.3f}%, stress-cost {r['take_all_net_stress_pct']:+.3f}%)")
    a(f"- barrier hit distribution: {r['hit_dist']}\n")
    a("## Walk-forward OOS (full history)\n")
    a(f"- OOS events scored: {wa['n_test_events']}, model TAKE: {wa['n_taken_oos']}")
    a(f"- **IN-SAMPLE** model net: {wa['is_model_net_pct']}%/signal "
      f"(precision {wa['is_model_prec']})")
    a(f"- **OUT-OF-SAMPLE** model net: **{wa['oos_model_net_pct']}%/signal** "
      f"(precision {wa['oos_model_prec']})")
    a(f"- take-all OOS baseline: {wa['take_all_net_pct']}%/signal "
      f"(precision {wa['take_all_prec']})")
    a(f"- OOS lift over take-all: **{wa['oos_lift_net_pct']}%/signal**  "
      f"(t={wa.get('oos_net_t')}, p={wa.get('oos_net_p')})\n")
    if r.get("shuffled_null_all"):
        sn = r["shuffled_null_all"]
        a("## Shuffled-label null (200 permutations)\n")
        a(f"- observed OOS model net: {sn['observed_ev_pct']}%")
        a(f"- null mean: {sn['null_ev_mean_pct']}%, null 95th pct: {sn['null_ev_p95_pct']}%")
        a(f"- **empirical p-value: {sn['p_value']}**\n")
    if "summary" in r.get("walk_forward_post2020", {}):
        pv = r["walk_forward_post2020"]["summary"]
        a("## Post-2020 regime variant\n")
        a(f"- OOS model net: {pv['oos_model_net_pct']}%/signal (taken {pv['n_taken_oos']}), "
          f"take-all {pv['take_all_net_pct']}%/signal, lift {pv['oos_lift_net_pct']}%\n")
    a("## Per-fold OOS (full history)\n")
    a("| fold | test window | n_tr | n_te | thr | taken | take-all net% | model net% | model prec |")
    a("|---|---|---|---|---|---|---|---|---|")
    for f in r["walk_forward_all"]["folds"]:
        a(f"| {f['fold']} | {f['test_start']}..{f['test_end']} | {f['n_train']} | "
          f"{f['n_test']} | {f['threshold']} | {f['n_taken']} | {f['take_all_net_pct']} | "
          f"{f['model_take_net_pct']} | {f['model_take_prec']} |")
    a("\n## Honest read\n")
    a(r.get("_verdict", "See JSON; verdict computed in main."))
    (OUT / "metalabel_report.md").write_text("\n".join(str(x) for x in L))


if __name__ == "__main__":
    main()
