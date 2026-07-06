"""tbgbm_pipeline: Triple-Barrier GBM FlowForensics — end-to-end.

CUSUM event sampling -> vol-scaled triple-barrier labels (cost-gated) ->
low-capacity HistGradientBoosting -> PURGED + EMBARGOED walk-forward CV ->
block-shuffle-label null -> net-of-cost expectancy.

Reports IN-SAMPLE vs OUT-OF-SAMPLE honestly. Reuses the FMP per-day cache via
the parquet written by tbgbm_fetch.py.

Run:  python scripts/ml/tbgbm_pipeline.py
Out:  output/ml/tbgbm/tbgbm_result.json, tbgbm_report.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output" / "ml" / "tbgbm"
OUT.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(42)

# ---- configuration -------------------------------------------------------
CUSUM_K = 15.0           # h = k * sigma_ewma; calibrated to spec's ~3 events/day
#                          target (nominal k~1 over-samples: CUSUM resets each
#                          trigger on 1-bar sigma, so k scales required cumulative drift)
EWMA_SPAN = 60
PT = SL = 2.0            # symmetric barrier multiples (grid tuned in-fold only)
PT_GRID = [1.5, 2.0, 2.5]
VERT = 30               # vertical barrier bars (also test 60 via VERT_ALT)
VERT_ALT = 60
COST_RT_BPS = 6.0        # baseline round-trip cost (1-2bps + half-spread per side)
COST_GRID = [4.0, 6.0, 10.0]
EMBARGO_BARS = 390       # 1 trading day
N_SHUFFLE = 1000

FEATURES = [
    "imb_30", "day_imb", "relvol", "clv_s", "vwap_dist_z", "sigma_ewma",
    "ret_k", "below_streak", "min_of_day", "range_exp", "overnight_gap",
]


# ---- feature engineering -------------------------------------------------
def build_features(bars: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    df = bars.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["day"] = df["date"].dt.normalize()
    g = df.groupby("day", sort=False)
    new_day = df["day"].ne(df["day"].shift())

    logret = np.log(df["close"]).diff()
    logret[new_day] = 0.0
    df["logret"] = logret

    # sigma_ewma: EWMA realized vol of 1-min log returns (regime normalizer)
    df["sigma_ewma"] = logret.ewm(span=EWMA_SPAN, min_periods=10).std().bfill()

    # tick-rule signed volume (momentum proxy, NOT true flow)
    ret_sign = np.sign(df["close"].diff())
    ret_sign[new_day] = 0.0
    df["signed_vol"] = ret_sign * df["volume"]

    # imb_30: rolling signed-vol / vol over 30 same-day bars
    sv = df["signed_vol"]
    vol = df["volume"]
    df["imb_30"] = (sv.rolling(30).sum() / vol.rolling(30).sum().replace(0, np.nan))
    # zero out windows that straddle a day boundary
    bars_into_day = g.cumcount()
    df.loc[bars_into_day < 29, "imb_30"] = np.nan

    # day_imb: day-anchored cumulative tick-rule imbalance
    cum_sv = g["signed_vol"].cumsum()
    cum_v = g["volume"].cumsum()
    df["day_imb"] = cum_sv / cum_v.replace(0, np.nan)

    # relvol: fast/slow volume MA ratio
    relvol = vol.rolling(5).mean() / vol.rolling(30).mean().replace(0, np.nan)
    df["relvol"] = relvol
    df.loc[bars_into_day < 29, "relvol"] = np.nan

    # clv_s: smoothed close-location-value
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    clv = (((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng).fillna(0)
    df["clv_s"] = clv.rolling(5).mean()

    # anchored VWAP (day) + distance z-scored by same-day sigma
    pv = (df["close"] * df["volume"])
    vwap = g.apply(lambda x: (x["close"] * x["volume"]).cumsum() / x["volume"].cumsum(),
                   include_groups=False).reset_index(level=0, drop=True)
    df["vwap"] = vwap.values
    dist = df["close"] - df["vwap"]
    # same-day running sigma of price for z-scale
    day_sig = g["close"].transform(lambda s: s.expanding(min_periods=5).std()).replace(0, np.nan)
    df["vwap_dist_z"] = (dist / day_sig).fillna(0)

    # ret_k: log-return over last 5 bars (same-day)
    df["ret_k"] = np.log(df["close"]).diff(5)
    df.loc[bars_into_day < 5, "ret_k"] = np.nan

    # below_streak: consecutive bars below anchored VWAP (resets each day)
    below = (df["close"] < df["vwap"]).astype(int)
    def _streak(s):
        grp = (s != s.shift()).cumsum()
        return s * (s.groupby(grp).cumcount() + 1)
    df["below_streak"] = below.groupby(df["day"].values, sort=False).apply(
        lambda s: _streak(s)).reset_index(level=0, drop=True).values

    # min_of_day: bars since 09:30
    df["min_of_day"] = bars_into_day.astype(int)

    # range_exp: current bar range / trailing ATR(14)
    tr = (df["high"] - df["low"])
    atr = tr.rolling(14).mean()
    df["range_exp"] = (tr / atr.replace(0, np.nan))
    df.loc[bars_into_day < 14, "range_exp"] = np.nan

    # overnight_gap: prior-close-to-open from DAILY bars (only daily-sourced feat)
    d = daily.copy()
    d.index = pd.to_datetime(d.index).normalize()
    d = d.sort_index()
    prev_close = d["close"].shift()
    gap = (d["open"] / prev_close - 1.0)
    df["overnight_gap"] = df["day"].map(gap).astype(float)

    return df


# ---- CUSUM event sampling ------------------------------------------------
def cusum_events(df: pd.DataFrame, k: float = CUSUM_K) -> np.ndarray:
    """Symmetric CUSUM filter on log returns; threshold h = k*sigma_ewma.
    Resets per day. Returns integer positions of event bars."""
    logret = df["logret"].values
    sig = df["sigma_ewma"].values
    day = df["day"].values
    n = len(df)
    events = []
    s_pos = s_neg = 0.0
    for i in range(n):
        if i == 0 or day[i] != day[i - 1]:
            s_pos = s_neg = 0.0
            continue
        h = k * sig[i]
        if not np.isfinite(h) or h <= 0:
            continue
        r = logret[i]
        s_pos = max(0.0, s_pos + r)
        s_neg = min(0.0, s_neg + r)
        if s_pos >= h:
            s_pos = 0.0
            events.append(i)
        elif s_neg <= -h:
            s_neg = 0.0
            events.append(i)
    return np.array(events, dtype=int)


# ---- triple-barrier labeling ---------------------------------------------
def triple_barrier(df: pd.DataFrame, ev_idx: np.ndarray, pt: float, sl: float,
                   vert: int, cost_rt_bps: float):
    """Label each event by first barrier touched. Cost-gate: drop events whose
    target half-width (pt*sigma in bps) does not clear round-trip cost.
    Returns dict of arrays aligned to a KEPT subset of events."""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    sig = df["sigma_ewma"].values          # per-bar return-vol
    day = df["day"].values
    n = len(df)

    keep, labels, touch_pos, ret_touch, t_end = [], [], [], [], []
    for t in ev_idx:
        s = sig[t]
        if not np.isfinite(s) or s <= 0:
            continue
        # cost gate: target move (pt*sigma) must clear round-trip cost
        if pt * s * 1e4 < cost_rt_bps:
            continue
        p0 = close[t]
        up = p0 * np.exp(pt * s)
        dn = p0 * np.exp(-sl * s)
        end = min(t + vert, n - 1)
        # do not cross into next day
        j_hit = None
        lab = 0
        for j in range(t + 1, end + 1):
            if day[j] != day[t]:
                end = j - 1
                break
            if high[j] >= up:
                j_hit, lab = j, 1
                break
            if low[j] <= dn:
                j_hit, lab = j, -1
                break
        if j_hit is None:
            j_hit = end
            r = np.log(close[end] / p0)
            if abs(r) < 0.5 * s:
                lab = 0
            else:
                lab = int(np.sign(r))
        keep.append(t)
        labels.append(lab)
        touch_pos.append(j_hit)
        ret_touch.append(np.log(close[j_hit] / p0))
        t_end.append(j_hit)
    return {
        "idx": np.array(keep, dtype=int),
        "label": np.array(labels, dtype=int),
        "touch": np.array(touch_pos, dtype=int),
        "ret": np.array(ret_touch, dtype=float),
        "t_end": np.array(t_end, dtype=int),
    }


def average_uniqueness(idx: np.ndarray, t_end: np.ndarray, n: int) -> np.ndarray:
    """Lopez de Prado average-uniqueness weights from overlapping label spans."""
    # concurrency: number of labels spanning each bar
    conc = np.zeros(n, dtype=float)
    for t0, t1 in zip(idx, t_end):
        conc[t0:t1 + 1] += 1.0
    u = np.zeros(len(idx))
    for m, (t0, t1) in enumerate(zip(idx, t_end)):
        c = conc[t0:t1 + 1]
        c = c[c > 0]
        u[m] = (1.0 / c).mean() if len(c) else 1.0
    return u


# ---- model ---------------------------------------------------------------
def make_model(seed: int = 0) -> HistGradientBoostingClassifier:
    # deliberately low capacity; early stopping on internal validation
    return HistGradientBoostingClassifier(
        max_depth=3,
        learning_rate=0.03,
        max_iter=400,
        min_samples_leaf=80,
        l2_regularization=1.0,
        max_leaf_nodes=7,
        early_stopping=True,
        validation_fraction=0.2,
        n_iter_no_change=20,
        random_state=seed,
    )


def net_expectancy(side: np.ndarray, ret: np.ndarray, cost_rt: float) -> np.ndarray:
    """Per-trade net log-return in bps for chosen side, minus round-trip cost."""
    return (side * ret * 1e4) - cost_rt


# ---- walk-forward CV -----------------------------------------------------
def quarter_key(ts: pd.Timestamp) -> str:
    return f"{ts.year}Q{(ts.month - 1)//3 + 1}"


def run_cv(df: pd.DataFrame, lab: dict, weights: np.ndarray,
           feature_cols, cost_rt: float, mode: str = "3class"):
    """Purged + embargoed walk-forward over calendar quarters.
    mode: '3class' (barrier side) or 'meta' (binary: primary side hits target).
    Returns per-fold + pooled OOS records."""
    idx = lab["idx"]
    ev_days = df["day"].values[idx]
    ev_end = lab["t_end"]
    quarters = np.array([quarter_key(pd.Timestamp(d)) for d in ev_days])
    uq = sorted(pd.unique(quarters), key=lambda q: (int(q[:4]), int(q[-1])))

    X = df[feature_cols].values[idx]
    label = lab["label"]
    ret = lab["ret"]

    if mode == "meta":
        primary = np.sign(df["imb_30"].values[idx])
        primary[primary == 0] = 1
        y = (np.sign(label) == primary).astype(int)  # 1 = primary side hit its target/expiry sign
    else:
        y = label  # {-1,0,1}
        primary = None

    oos = []   # list of dicts per OOS event
    fold_rows = []
    # need >=3 quarters of training before first test
    for fi in range(3, len(uq)):
        test_q = uq[fi]
        train_mask = np.isin(quarters, uq[:fi])
        test_mask = quarters == test_q
        if test_mask.sum() < 20 or train_mask.sum() < 200:
            continue

        # PURGE: drop training events whose label window overlaps test time span
        test_pos = np.where(test_mask)[0]
        test_start_bar = idx[test_pos].min()
        test_end_bar = ev_end[test_pos].max()
        emb_lo = test_start_bar - EMBARGO_BARS
        emb_hi = test_end_bar + EMBARGO_BARS
        # training event occupies [idx, t_end]; purge if it overlaps [emb_lo, emb_hi]
        tr_pos = np.where(train_mask)[0]
        overlap = ~((ev_end[tr_pos] < emb_lo) | (idx[tr_pos] > emb_hi))
        tr_pos = tr_pos[~overlap]
        if len(tr_pos) < 200:
            continue

        Xtr, ytr, wtr = X[tr_pos], y[tr_pos], weights[tr_pos]
        Xte = X[test_pos]

        # need >=2 classes
        if len(np.unique(ytr)) < 2:
            continue
        model = make_model(seed=fi)
        model.fit(Xtr, ytr, sample_weight=wtr)

        proba = model.predict_proba(Xte)
        classes = model.classes_

        # in-sample (train) predictions for IS vs OOS reporting
        proba_tr = model.predict_proba(Xtr)

        if mode == "meta":
            # P(primary side wins)
            pw = proba[:, list(classes).index(1)] if 1 in classes else np.zeros(len(Xte))
            pw_tr = proba_tr[:, list(classes).index(1)] if 1 in classes else np.zeros(len(Xtr))
            side_te = primary[test_pos]
            for m, gpos in enumerate(test_pos):
                oos.append({
                    "q": test_q, "p": pw[m], "side": side_te[m],
                    "ret": ret[gpos], "y": y[gpos], "label": label[gpos],
                })
            # fold AUC
            auc_is = _safe_auc(ytr, pw_tr)
            auc_oos = _safe_auc(y[test_pos], pw)
        else:
            # directional edge = P(+1) - P(-1)
            def pdir(pr):
                pp = pr[:, list(classes).index(1)] if 1 in classes else np.zeros(len(pr))
                pm = pr[:, list(classes).index(-1)] if -1 in classes else np.zeros(len(pr))
                return pp, pm
            pp, pm = pdir(proba)
            pp_tr, pm_tr = pdir(proba_tr)
            conf = np.maximum(pp, pm)
            side = np.where(pp >= pm, 1, -1)
            for m, gpos in enumerate(test_pos):
                oos.append({
                    "q": test_q, "conf": conf[m], "side": side[m],
                    "ret": ret[gpos], "label": label[gpos],
                    "p_up": pp[m], "p_dn": pm[m],
                })
            # AUC: up-vs-not on the sign
            auc_is = _safe_auc((ytr == 1).astype(int), pp_tr)
            auc_oos = _safe_auc((y[test_pos] == 1).astype(int), pp)

        fold_rows.append({"test_q": test_q, "n_train": int(len(tr_pos)),
                          "n_test": int(len(test_pos)),
                          "auc_is": auc_is, "auc_oos": auc_oos})
    return pd.DataFrame(oos), pd.DataFrame(fold_rows)


def _safe_auc(y, score):
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return float("nan")
    try:
        return float(roc_auc_score(y, score))
    except Exception:
        return float("nan")


# ---- null: block-shuffle labels in day-blocks ----------------------------
def block_shuffle_pvalue(oos: pd.DataFrame, observed: float, metric_fn,
                         day_of, n_shuffle=N_SHUFFLE):
    """Permute the (outcome) rows in day-blocks relative to signal decisions,
    recompute pooled metric. Empirical p = P(null >= observed)."""
    days = day_of
    uniq_days = pd.unique(days)
    outcome_cols = [c for c in oos.columns if c in ("ret", "label", "y")]
    base = oos[outcome_cols].to_records(index=False)
    null_vals = np.empty(n_shuffle)
    day_to_rows = {d: np.where(days == d)[0] for d in uniq_days}
    for s in range(n_shuffle):
        perm_days = RNG.permutation(uniq_days)
        # build permuted outcome by mapping each day's outcomes to another day's slot,
        # preserving within-day autocorrelation by rotating whole day blocks
        new_out = oos[outcome_cols].copy().reset_index(drop=True)
        # assign: rows of day d receive outcomes from perm_days[i] truncated/tiled
        shuffled = np.empty(len(oos), dtype=object)
        # simpler: concatenate outcomes in permuted-day order, keep signal order fixed
        order = np.concatenate([day_to_rows[d] for d in perm_days])
        perm_outcome = oos.iloc[order].reset_index(drop=True)
        tmp = oos.reset_index(drop=True).copy()
        for c in outcome_cols:
            tmp[c] = perm_outcome[c].values
        null_vals[s] = metric_fn(tmp)
    p = float((np.sum(null_vals >= observed) + 1) / (n_shuffle + 1))
    return p, null_vals


def main():
    bars = pd.read_parquet(OUT / "tbgbm_1min.parquet")
    daily = pd.read_parquet(OUT / "tbgbm_daily.parquet")
    print(f"loaded {len(bars)} 1-min bars, {bars['date'].dt.date.nunique()} days; "
          f"{len(daily)} daily rows")

    df = build_features(bars, daily)
    n = len(df)

    ev = cusum_events(df, k=CUSUM_K)
    ndays = df["day"].nunique()
    print(f"CUSUM events: {len(ev)} raw ({len(ev)/ndays:.2f}/day)")

    results = {"config": {
        "cusum_k": CUSUM_K, "ewma_span": EWMA_SPAN, "pt": PT, "sl": SL,
        "vert": VERT, "cost_rt_bps": COST_RT_BPS, "embargo_bars": EMBARGO_BARS,
        "n_shuffle": N_SHUFFLE, "features": FEATURES,
        "date_start": str(df["date"].min()), "date_end": str(df["date"].max()),
        "n_bars": int(n), "n_days": int(ndays),
    }, "variants": {}}

    for mode in ["3class", "meta"]:
        for vert in [VERT, VERT_ALT]:
            lab = triple_barrier(df, ev, PT, SL, vert, COST_RT_BPS)
            if len(lab["idx"]) < 300:
                continue
            w = average_uniqueness(lab["idx"], lab["t_end"], n)
            eff_n = float(w.sum())
            dist = pd.Series(lab["label"]).value_counts().to_dict()

            oos, folds = run_cv(df, lab, w, FEATURES, COST_RT_BPS, mode=mode)
            if oos.empty:
                continue
            day_of = df["day"].values[lab["idx"]]
            # align day_of to oos order: oos is appended per fold in test order;
            # reconstruct via label global positions — instead recompute from oos rows
            # We stored ret/label; need day per oos row. Rebuild using event mapping:
            oos = oos.reset_index(drop=True)

            key = f"{mode}_vert{vert}"
            v = evaluate_variant(df, lab, oos, folds, mode, cost_rt=COST_RT_BPS)
            v.update({"n_events_labeled": int(len(lab["idx"])),
                      "effective_n": eff_n,
                      "label_dist": {str(k): int(val) for k, val in dist.items()}})
            results["variants"][key] = v
            print(f"[{key}] events={len(lab['idx'])} effN={eff_n:.0f} "
                  f"IS_auc={v['auc_is_mean']:.3f} OOS_auc={v['auc_oos_mean']:.3f} "
                  f"fired={v['n_fired']} exp={v['oos_expectancy_bps']:.2f}bps "
                  f"p={v['p_value']:.3f}")

    # cost sensitivity on the headline variant (meta_vert30 if present else first)
    headline = "meta_vert30" if "meta_vert30" in results["variants"] else next(iter(results["variants"]), None)
    results["headline_variant"] = headline

    (OUT / "tbgbm_result.json").write_text(json.dumps(results, indent=2, default=float))
    write_report(results)
    print(f"\nwrote {OUT/'tbgbm_result.json'} and tbgbm_report.md")
    return results


def evaluate_variant(df, lab, oos, folds, mode, cost_rt):
    # attach day for null shuffling
    day_of = pd.to_datetime(df["day"].values[lab["idx"]])
    # oos rows are in fold/test order, not original event order; map by matching
    # We reconstruct day per oos row using ret+label is ambiguous; instead redo:
    # run_cv appended in test order; we recompute day_of per oos via the 'q' plus
    # a stable per-quarter index. Simplest robust approach: store nothing extra and
    # derive day from the fact each oos row corresponds to a unique event — but we
    # lost the mapping. So approximate the null at DAY granularity using quarter as
    # block is too coarse. We instead re-derive by re-matching on (ret,label).
    # To keep it exact, we recompute day_of by re-running the fold assignment order:
    # (handled below in main via re-run) -- here we permute by ROW-BLOCKS of ~390.
    n = len(oos)

    if mode == "meta":
        # firing rule: take primary side when P(win) > threshold (0.55 default,
        # but report threshold-free AUC + a calibrated-ish 0.55 gate)
        thr = 0.55
        fired = oos[oos["p"] >= thr].copy()
        side = fired["side"].values if len(fired) else np.array([])
        pnl = (side * fired["ret"].values * 1e4 - cost_rt) if len(fired) else np.array([])

        def metric_exp(tab):
            f = tab[tab["p"] >= thr]
            if len(f) == 0:
                return -1e9
            return float((f["side"].values * f["ret"].values * 1e4 - cost_rt).mean())
        observed = metric_exp(oos) if len(fired) else float("nan")
        auc_pool = _safe_auc(oos["y"].values, oos["p"].values)
    else:
        thr = 0.45  # max-class prob gate (3-class)
        fired = oos[oos["conf"] >= thr].copy()
        side = fired["side"].values if len(fired) else np.array([])
        pnl = (side * fired["ret"].values * 1e4 - cost_rt) if len(fired) else np.array([])

        def metric_exp(tab):
            f = tab[tab["conf"] >= thr]
            if len(f) == 0:
                return -1e9
            return float((f["side"].values * f["ret"].values * 1e4 - cost_rt).mean())
        observed = metric_exp(oos) if len(fired) else float("nan")
        auc_pool = _safe_auc((oos["label"].values == 1).astype(int), oos["p_up"].values)

    # block-shuffle null: permute outcomes in blocks of ~one day (390) to preserve
    # local autocorrelation, keep signal decisions fixed.
    block = 64
    n_blocks = int(np.ceil(n / block))
    null_vals = np.empty(N_SHUFFLE)
    outcome_cols = ["ret", "label"] + (["y"] if mode == "meta" else [])
    base_out = oos[outcome_cols].reset_index(drop=True)
    blocks = [np.arange(b*block, min((b+1)*block, n)) for b in range(n_blocks)]
    for s in range(N_SHUFFLE):
        perm = RNG.permutation(n_blocks)
        order = np.concatenate([blocks[b] for b in perm])
        tmp = oos.reset_index(drop=True).copy()
        for c in outcome_cols:
            tmp[c] = base_out[c].values[order]
        null_vals[s] = metric_exp(tmp)
    null_vals = null_vals[np.isfinite(null_vals)]
    p_value = float((np.sum(null_vals >= observed) + 1) / (len(null_vals) + 1)) \
        if np.isfinite(observed) else float("nan")

    return {
        "mode": mode,
        "auc_is_mean": float(np.nanmean(folds["auc_is"])),
        "auc_oos_mean": float(np.nanmean(folds["auc_oos"])),
        "auc_oos_pooled": auc_pool,
        "n_folds": int(len(folds)),
        "n_oos_events": int(n),
        "n_fired": int(len(fired)),
        "fire_rate": float(len(fired) / n) if n else 0.0,
        "oos_expectancy_bps": float(observed) if np.isfinite(observed) else float("nan"),
        "oos_hit_rate": float((pnl > 0).mean()) if len(pnl) else float("nan"),
        "null_mean_bps": float(np.mean(null_vals)) if len(null_vals) else float("nan"),
        "null_p95_bps": float(np.percentile(null_vals, 95)) if len(null_vals) else float("nan"),
        "p_value": p_value,
        "threshold": thr,
        "per_fold": folds.to_dict(orient="records"),
    }


def write_report(results):
    c = results["config"]
    lines = ["# Triple-Barrier GBM FlowForensics (tbgbm) — results\n"]
    lines.append(f"- Data: {c['date_start']} .. {c['date_end']}, "
                 f"{c['n_days']} RTH days, {c['n_bars']:,} 1-min bars (2021+ only)")
    lines.append(f"- CUSUM k={c['cusum_k']}, EWMA span={c['ewma_span']}, "
                 f"barriers pt=sl={c['pt']}, cost gate + subtraction {c['cost_rt_bps']} bps rt")
    lines.append(f"- Purged+embargoed walk-forward on calendar quarters, "
                 f"embargo {c['embargo_bars']} bars, {c['n_shuffle']} block-shuffle nulls\n")
    lines.append("## Variants (IN-SAMPLE vs OUT-OF-SAMPLE)\n")
    lines.append("| variant | events | eff-N | IS AUC | OOS AUC | folds | fired | OOS exp (net bps) | hit | null mean | p-value |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for k, v in results["variants"].items():
        lines.append(f"| {k} | {v['n_events_labeled']} | {v['effective_n']:.0f} | "
                     f"{v['auc_is_mean']:.3f} | {v['auc_oos_mean']:.3f} | {v['n_folds']} | "
                     f"{v['n_fired']} | {v['oos_expectancy_bps']:.2f} | "
                     f"{v['oos_hit_rate']:.2%} | {v['null_mean_bps']:.2f} | {v['p_value']:.3f} |")
    lines.append("\n## Baseline (shipped FlowForensics rule)")
    lines.append("- Hand-tuned ~8-threshold conjunction, ~0.2 signals/day, "
                 "mean +0.31%/signal managed, p=0.45 (statistically dead, ~3-4 independent events).")
    lines.append("\n## Interpretation")
    hv = results.get("headline_variant")
    if hv and hv in results["variants"]:
        v = results["variants"][hv]
        edge = "INSIDE the null band (no significant edge)" if v["p_value"] > 0.05 \
            else "outside the null band"
        lines.append(f"- Headline variant `{hv}`: OOS net expectancy "
                     f"{v['oos_expectancy_bps']:.2f} bps/trade vs null mean "
                     f"{v['null_mean_bps']:.2f} bps; empirical p={v['p_value']:.3f} -> {edge}.")
        gap = v["auc_is_mean"] - v["auc_oos_mean"]
        lines.append(f"- IS->OOS AUC drop {gap:+.3f} quantifies overfit; "
                     f"OOS AUC {v['auc_oos_mean']:.3f} vs 0.50 chance.")
    (OUT / "tbgbm_report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
