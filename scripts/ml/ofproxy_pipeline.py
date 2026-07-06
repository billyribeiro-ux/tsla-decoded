"""ofproxy TRACK 2 — tradable meta-label model with Databento-calibrated
absorption OHLCV proxies.

Primary rule = shipped FlowForensics v1.1 (UNCHANGED) -> event set E.
Secondary meta-label classifier decides TAKE/SKIP per fired event using a small,
strongly-regularized model on <=5 OHLCV-derivable absorption-family features:

    absorption_ratio      : rolling volume z / |per-bar displacement|  (inverse Amihud)
    kyle_lambda_proxy     : rolling slope of ret on tick-signed volume  (passive supply)
    clv_wick_asymmetry    : close-location-value + wick asymmetry        (book-imb proxy)
    tick_delta_momentum   : existing rolling tick-signed imbalance (renamed honestly)
    day_imb_ctx           : cumulative session signed-volume imbalance   (regime control)

Triple-barrier meta-labels net of cost; purged + embargoed walk-forward CV;
shuffled-label null; take-all (raw-rule) baseline; post-2020 regime split.

Reuses the audited CV machinery in metalabel_pipeline (triple_barrier,
walk_forward, summarize_pooled, shuffled_null, sample_weights) — only the
FEATURE SET differs, which is the whole point of this approach.

Run:  python scripts/ml/ofproxy_pipeline.py
Out:  output/ml/ofproxy/ofproxy_result.json + ofproxy_report.md
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

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "ml"))
load_dotenv(REPO / ".env")
os.environ.setdefault("FMP_API_KEY", "cache-only")

from tsla_decoded.fmp_client import FMPClient          # noqa: E402
from tsla_decoded import data_loader as dl             # noqa: E402
from tsla_decoded import signal_backtest as sb         # noqa: E402
import metalabel_pipeline as mlp                       # noqa: E402

OUT = REPO / "output" / "ml" / "ofproxy"
OUT.mkdir(parents=True, exist_ok=True)

START = "2010-06-29"
END = "2026-07-02"

# THE approach's feature set (<=5), swapped into the shared CV machinery.
OFPROXY_FEATURES = [
    "absorption_ratio", "kyle_lambda_proxy", "clv_wick_asymmetry",
    "tick_delta_momentum", "day_imb_ctx",
]
mlp.FEATURES = OFPROXY_FEATURES     # walk_forward / summarize read this global


# --------------------------------------------------------------------------
# absorption-family features, vectorized on the FlowForensics feature frame.
# All strictly backward-looking; sampled as-of the signal bar t0.
# --------------------------------------------------------------------------
def add_absorption_features(feat: pd.DataFrame):
    f = feat
    day = pd.Series(f.index.date, index=f.index)
    new_day = day.ne(day.shift()).to_numpy()
    ret = f["close"].pct_change()
    ret[new_day] = np.nan
    logret = np.log(f["close"]).diff()
    logret[new_day] = np.nan

    W = 30
    volm = f["volume"].rolling(W).mean()
    vols = f["volume"].rolling(W).std().replace(0, np.nan)
    volz = (f["volume"] - volm) / vols
    absd = ret.abs()
    absorption = volz.rolling(5).mean() / (absd.rolling(5).mean() * 100 + 0.02)

    sv = f["signed_vol"]
    cov = ret.rolling(W).cov(sv)
    var = sv.rolling(W).var().replace(0, np.nan)
    kyle = (cov / var) * sv.abs().rolling(W).mean()

    rng = (f["high"] - f["low"]).replace(0, np.nan)
    upper = f["high"] - f[["open", "close"]].max(axis=1)
    lower = f[["open", "close"]].min(axis=1) - f["low"]
    wick_asym = (upper - lower) / rng
    clv = (((f["close"] - f["low"]) - (f["high"] - f["close"])) / rng).fillna(0)
    clv_wick = (clv + wick_asym).rolling(10).mean()

    feats = pd.DataFrame(index=f.index)
    feats["absorption_ratio"] = absorption.replace([np.inf, -np.inf], np.nan)
    feats["kyle_lambda_proxy"] = kyle.replace([np.inf, -np.inf], np.nan)
    feats["clv_wick_asymmetry"] = clv_wick
    feats["tick_delta_momentum"] = f["imb"]
    feats["day_imb_ctx"] = f["day_imb"]
    realized = logret.rolling(30).std()
    return feats, realized


def build_events(feat, signals, feats, realized) -> pd.DataFrame:
    idx = feat.index
    pos_of = {ts: i for i, ts in enumerate(idx)}
    fv = feats.to_numpy()
    rv = realized.to_numpy()
    cols = list(feats.columns)
    rows = []
    for _, s in signals.iterrows():
        ts = s["ts"]
        pos = pos_of.get(ts)
        if pos is None or pos + 1 >= len(idx):
            continue
        if idx[pos + 1].date() != ts.date():        # need same-day entry bar
            continue
        row = {"t0": ts, "side": s["signal"], "trigger": s["trigger"],
               "entry_pos": pos + 1,
               "realized_vol": float(rv[pos]) if np.isfinite(rv[pos]) else np.nan}
        for j, c in enumerate(cols):
            v = fv[pos, j]
            row[c] = float(v) if np.isfinite(v) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    client = FMPClient(api_key=os.environ["FMP_API_KEY"], cache_dir=REPO / "data" / "raw")
    print("loading full 1-min history from cache ...", flush=True)
    bars = dl.intraday(client, "TSLA", "1min", START, END)
    daily = dl.daily(client, "TSLA", START, END)
    print(f"  bars={len(bars):,}  days={bars.index.normalize().nunique()}", flush=True)
    feat = sb.compute_features(bars, sb.DEFAULTS, daily["close"])
    signals = sb.generate_signals(feat, sb.DEFAULTS)
    print(f"  primary FlowForensics signals: {len(signals)}", flush=True)

    feats, realized = add_absorption_features(feat)
    events = build_events(feat, signals, feats, realized)
    lab = mlp.triple_barrier(feat, events)
    lab = lab.dropna(subset=["meta_label"]).reset_index(drop=True)
    lab["meta_label"] = lab["meta_label"].astype(int)
    lab["year"] = pd.to_datetime(lab["t0"]).dt.year

    # de-clustering counts (honest effective-N reporting)
    n_raw = len(signals)
    n_side_day = signals.groupby([signals["ts"].dt.date, signals["signal"]]).ngroups
    n_day = signals["ts"].dt.date.nunique()
    w = mlp.sample_weights(lab)
    eff_n = float(w.sum() / w.max()) if len(w) else 0.0   # rough independent-N proxy
    print(f"labeled events: {len(lab)}  base_rate={lab['meta_label'].mean():.3f}  "
          f"take-all net={lab['net_ret'].mean()*100:+.3f}%  eff_n~{eff_n:.0f}", flush=True)
    lab.drop(columns=[c for c in ["barrier_w"] if c in lab.columns]).to_parquet(
        OUT / "ofproxy_events.parquet")

    result = {
        "approach": "ofproxy",
        "config": {"start": START, "end": END, "k_barrier": mlp.K_BARRIER,
                   "H_max": mlp.H_MAX, "cost_rt_pct": round(mlp.COST_RT * 100, 4),
                   "cost_rt_stress_pct": round(mlp.COST_RT_STRESS * 100, 4),
                   "features": OFPROXY_FEATURES,
                   "model": "HistGradientBoosting depth3/15-leaf, l2=1.0 (low-capacity)"},
        "event_counts": {"raw": n_raw, "one_per_side_per_day": n_side_day,
                         "distinct_days": n_day, "labeled": len(lab),
                         "approx_effective_n": round(eff_n, 1)},
        "label_base_rate": round(float(lab["meta_label"].mean()), 4),
        "take_all_net_pct": round(float(lab["net_ret"].mean() * 100), 4),
        "take_all_gross_pct": round(float(lab["gross_ret"].mean() * 100), 4),
        "take_all_net_stress_pct": round(
            float((lab["gross_ret"] - mlp.COST_RT_STRESS).mean() * 100), 4),
        "hit_dist": lab["hit"].value_counts().to_dict(),
        "per_year_counts": {int(k): int(v) for k, v in
                            lab.groupby("year").size().to_dict().items()},
    }

    print("walk-forward CV (full history 2010-2026) ...", flush=True)
    res_all = mlp.walk_forward(lab, n_folds=8, tag="all")
    sum_all = mlp.summarize_pooled(res_all)
    result["walk_forward_all"] = {"summary": sum_all, "folds": res_all["folds"]}
    print(f"  OOS taken={sum_all['n_taken_oos']} model_net={sum_all['oos_model_net_pct']}% "
          f"take_all={sum_all['take_all_net_pct']}% lift={sum_all['oos_lift_net_pct']}%",
          flush=True)

    # post-2020 regime split (non-stationarity: $1.5-14 TSLA of 2010 != $400 of 2026)
    lab_pv = lab[lab["year"] >= 2020].reset_index(drop=True)
    result["post2020_counts"] = {"labeled": len(lab_pv)}
    if len(lab_pv) >= 80:
        print(f"walk-forward CV (post-2020, n={len(lab_pv)}) ...", flush=True)
        res_pv = mlp.walk_forward(lab_pv, n_folds=5, tag="post2020")
        result["walk_forward_post2020"] = {"summary": mlp.summarize_pooled(res_pv),
                                           "folds": res_pv["folds"]}
        print(f"  OOS post2020 net={result['walk_forward_post2020']['summary']['oos_model_net_pct']}%",
              flush=True)
    else:
        result["walk_forward_post2020"] = {"note": "insufficient post-2020 events"}

    # shuffled-label null (permute labels, refit, compare OOS expectancy)
    obs = sum_all["oos_model_net_pct"]
    if obs is not None:
        print("shuffled-label null (200 permutations) ...", flush=True)
        result["shuffled_null_all"] = mlp.shuffled_null(lab, obs, n_iter=200, n_folds=8)
        print(f"  null p={result['shuffled_null_all']['p_value']}", flush=True)

    # binomial p on OOS hit rate vs 0.5
    from scipy import stats
    tn = np.array(res_all["pooled"]["take_net"])
    if len(tn) > 2:
        k = int((tn > 0).sum())
        result["oos_binomial"] = {
            "n": int(len(tn)), "hits": k, "hit_rate": round(k / len(tn), 3),
            "p_two_sided": round(float(stats.binomtest(k, len(tn), 0.5).pvalue), 4)}

    # attach calibration summary if present
    cal_path = OUT / "ofproxy_calibration.json"
    if cal_path.exists():
        result["calibration_spotcheck"] = json.loads(cal_path.read_text())

    result["_verdict"] = build_verdict(result)
    (OUT / "ofproxy_result.json").write_text(json.dumps(result, indent=2, default=str))
    write_report(result)
    print("saved:", OUT / "ofproxy_result.json", flush=True)
    return result


def build_verdict(r: dict) -> str:
    wa = r["walk_forward_all"]["summary"]
    ec = r["event_counts"]
    sn = r.get("shuffled_null_all", {})
    lift = wa.get("oos_lift_net_pct")
    oos = wa.get("oos_model_net_pct")
    ta = r["take_all_net_pct"]
    pval = sn.get("p_value")
    parts = [
        f"Primary rule fires {ec['raw']} signals over {ec['distinct_days']} days "
        f"({ec['raw']/max(ec['distinct_days'],1):.2f}/signal-day; ~{ec['approx_effective_n']} "
        "approx-independent), lifting the sample ceiling far above the shipped rule's "
        "~3-4 independent events.",
        f"Take-all (raw-rule) net expectancy is {ta:+.3f}%/signal "
        f"(gross {r['take_all_gross_pct']:+.3f}%, stress-cost {r['take_all_net_stress_pct']:+.3f}%) "
        "— the economic floor the absorption filter must beat OOS.",
    ]
    if lift is not None and pval is not None:
        clears = pval < 0.05 and lift > 0 and oos is not None and oos > 0
        parts.append(
            f"OOS the secondary filter takes {wa['n_taken_oos']}/{wa['n_test_events']} "
            f"signals at net {oos}%/signal vs take-all {wa['take_all_net_pct']}%/signal "
            f"(lift {lift}%); IS model net {wa['is_model_net_pct']}%. Against the "
            f"shuffled-label null (p={pval}) the gain {'CLEARS' if clears else 'does NOT clear'} "
            "p<0.05.")
    return " ".join(parts)


def write_report(r: dict):
    L = []
    a = L.append
    ec = r["event_counts"]
    wa = r["walk_forward_all"]["summary"]
    a("# Order-Flow-Informed OHLCV Proxies (ofproxy) — results\n")
    a("Databento-calibrated absorption features as a meta-label secondary filter on the "
      "shipped FlowForensics v1.1 rule (UNCHANGED). Full FMP 1-min backfill "
      f"{r['config']['start']} -> {r['config']['end']}. Purged + embargoed walk-forward CV. "
      "Model: " + r["config"]["model"] + ".\n")

    a("## Track 1 — proxy calibration vs Databento ground truth (n=2 days, DESCRIPTIVE)\n")
    cal = r.get("calibration_spotcheck")
    if cal:
        a("Per-bar OHLCV proxy vs Databento-verified truth. **n=2 days, NOT "
          "cross-validatable** — gates sign-plausibility only.\n")
        a("| proxy vs ground truth | 2026-06-29 | 2026-07-02 |")
        a("|---|---|---|")
        pairs = [("kyle_lambda_proxy vs true Kyle lambda", "kyle_proxy_vs_true_kyle"),
                 ("tick_delta_momentum vs true aggressor imb", "tick_delta_vs_true_agg_imb"),
                 ("tick bar-sign vs true aggressor sign", "tick_bar_sign_vs_true_agg_sign"),
                 ("clv_wick_asymmetry vs displayed book imb", "clv_wick_vs_book_imb"),
                 ("absorption_ratio vs inverse-Amihud", "absorption_ratio_vs_true_absorption")]
        d0 = cal["days"].get("2026-06-29", {})
        d1 = cal["days"].get("2026-07-02", {})
        for name, k in pairs:
            def fmt(d):
                x = d.get(k, {})
                pc = x.get("pearson")
                sa = x.get("sign_agreement")
                return (f"r={pc}, agree={sa}" if pc is not None
                        else f"agree={sa}" if sa is not None else "-")
            a(f"| {name} | {fmt(d0)} | {fmt(d1)} |")
        a("\n**Calibration read (honest):** `kyle_lambda_proxy` is the one proxy that "
          "genuinely tracks its ground truth (r~0.84-0.90, sign-agreement 0.95-0.99) — the "
          "OHLCV slope of return on tick-signed volume recovers the true Kyle lambda well, "
          "supporting the 'passive/hidden supply' thesis. The tick rule agrees with the true "
          "aggressor SIGN ~70-76% of the time but its magnitude correlation is weak (r~0.15-0.18) "
          "— confirming the project audit that it is a momentum proxy, not aggressor flow. "
          "`clv_wick_asymmetry` and the flagship `absorption_ratio` do NOT validate at the "
          "per-bar level (near-zero / sign-inconsistent correlation across the 2 days); they "
          "enter the model only as weak candidate features, and the meta-label CV is the real "
          "arbiter. Two days cannot cross-validate any of this.\n")
    else:
        a("_calibration file missing — run ofproxy_calibration.py first._\n")

    a("## Track 2 — tradable meta-label model\n")
    a("### Event set (sample size)\n")
    a(f"- raw primary signals: **{ec['raw']}** over {ec['distinct_days']} distinct days")
    a(f"- one-per-side-per-day: {ec['one_per_side_per_day']}")
    a(f"- labeled (valid triple-barrier): **{ec['labeled']}**  "
      f"(approx effective-N ~{ec['approx_effective_n']})")
    a(f"- post-2020 labeled: {r['post2020_counts']['labeled']}\n")
    a("### Labels & economics\n")
    a(f"- triple-barrier k={r['config']['k_barrier']}, H<= {r['config']['H_max']} bars, "
      f"vol-scaled; entry t0+1 open; round-trip cost {r['config']['cost_rt_pct']}% baked in.")
    a(f"- label base rate (net-profitable): **{r['label_base_rate']}**")
    a(f"- take-all net expectancy: **{r['take_all_net_pct']:+.3f}%/signal** "
      f"(gross {r['take_all_gross_pct']:+.3f}%, stress-cost {r['take_all_net_stress_pct']:+.3f}%)")
    a(f"- barrier hits: {r['hit_dist']}\n")
    a("### Walk-forward OOS (full history)\n")
    a(f"- OOS events scored: {wa['n_test_events']}, model TAKE: {wa['n_taken_oos']}")
    a(f"- **IN-SAMPLE** model net: {wa['is_model_net_pct']}%/signal (prec {wa['is_model_prec']})")
    a(f"- **OUT-OF-SAMPLE** model net: **{wa['oos_model_net_pct']}%/signal** "
      f"(prec {wa['oos_model_prec']})")
    a(f"- take-all OOS baseline: {wa['take_all_net_pct']}%/signal (prec {wa['take_all_prec']})")
    a(f"- OOS lift over take-all: **{wa['oos_lift_net_pct']}%/signal** "
      f"(t={wa.get('oos_net_t')}, p={wa.get('oos_net_p')})\n")
    if r.get("shuffled_null_all"):
        sn = r["shuffled_null_all"]
        a("### Shuffled-label null (200 permutations)\n")
        a(f"- observed OOS model net: {sn['observed_ev_pct']}%; null mean "
          f"{sn['null_ev_mean_pct']}%, null p95 {sn['null_ev_p95_pct']}%")
        a(f"- **empirical p-value: {sn['p_value']}**\n")
    if r.get("oos_binomial"):
        b = r["oos_binomial"]
        a(f"### OOS hit-rate binomial\n- {b['hits']}/{b['n']} profitable "
          f"({b['hit_rate']}), two-sided p={b['p_two_sided']}\n")
    if "summary" in r.get("walk_forward_post2020", {}):
        pv = r["walk_forward_post2020"]["summary"]
        a("### Post-2020 regime variant\n")
        a(f"- OOS model net {pv['oos_model_net_pct']}%/signal (taken {pv['n_taken_oos']}), "
          f"take-all {pv['take_all_net_pct']}%, lift {pv['oos_lift_net_pct']}%\n")
    a("### Baseline (shipped FlowForensics rule)\n")
    a("- Hand-tuned ~8-threshold conjunction, ~0.2 signals/day on the quiet baseline, "
      "mean +0.31%/signal managed, p=0.45 (statistically dead, ~3-4 independent events).\n")
    a("### Per-fold OOS\n")
    a("| fold | test window | n_tr | n_te | thr | taken | take-all net% | model net% | prec |")
    a("|---|---|---|---|---|---|---|---|---|")
    for f in r["walk_forward_all"]["folds"]:
        a(f"| {f['fold']} | {f['test_start']}..{f['test_end']} | {f['n_train']} | "
          f"{f['n_test']} | {f['threshold']} | {f['n_taken']} | {f['take_all_net_pct']} | "
          f"{f['model_take_net_pct']} | {f['model_take_prec']} |")
    a("\n## Honest verdict\n")
    a(r.get("_verdict", ""))
    a("\n**Limits:** effective-independent events are still a few hundred; proxy calibration "
      "rests on n=2 non-cross-validatable days; 16-year TSLA non-stationarity is real (hence "
      "the post-2020 split). Judge on purged OOS expectancy vs the shuffled-label null with "
      "full cost sensitivity. Not investment advice.")
    (OUT / "ofproxy_report.md").write_text("\n".join(str(x) for x in L))


if __name__ == "__main__":
    main()
