"""Bar-for-bar Python mirror of the FlowForensics thinkScript rules.

Validates the indicator against the cached 1-minute data (the hard evidence):
the shipped .ts defaults must catch the Jun 29 accumulation and the Jul 2
opening liquidation while staying sparse on the 2-week baseline.
"""
from __future__ import annotations

import itertools
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tabulate import tabulate

from . import data_loader as dl
from .features import anchored_vwap
from .fmp_client import FMPClient
from .plots import DOWN, UP

log = logging.getLogger(__name__)

ET = "America/New_York"

DEFAULTS = {
    "imb_window": 30,        # bars — rolling flow-imbalance window
    "buy_thresh": 0.20,      # imbalance >= for accumulation
    "sell_thresh": -0.20,    # imbalance <= for distribution
    "relvol_fast": 10,
    "relvol_slow": 50,
    "relvol_thresh": 1.25,
    "clv_smooth": 10,
    "open_window_min": 75,   # Jul 2 damage was front-loaded in the first 75 min
    "open_high_min": 15,     # HOD set within first 15 min = rejection setup
    "below_vwap_bars": 15,   # consecutive bars below VWAP for distribution trigger
    "cooldown_min": 30,
    # v1.1 gates (from the per-signal audit)
    "buy_cutoff_min": 330,   # no new BUY after 15:00 — late entries have no runway
    "runup_gate": 0.10,      # no BUY when the 3-day run-up exceeds this (exhaustion)
    "prior_vwap_gate": True, # opening-rejection SELL needs price < prior session VWAP
    "target_pct": 1.25,      # managed-exit profit target (strategy/report)
}

V10_OVERRIDES = {"buy_cutoff_min": 390, "runup_gate": None, "prior_vwap_gate": False}


def compute_features(bars_1m: pd.DataFrame, p: dict,
                     daily_closes: pd.Series | None = None) -> pd.DataFrame:
    """Exactly the series the thinkScript computes, same formulas.

    daily_closes: optional date-indexed EOD closes extending before the intraday
    frame, used for the 3-day run-up gate (thinkScript: close(period=DAY)[1..4]).
    """
    df = bars_1m[bars_1m["session"] == "regular"].copy()
    day = pd.Series(df.index.date, index=df.index)
    new_day = day.ne(day.shift())

    ret_sign = np.sign(df["close"].diff())
    ret_sign[new_day] = 0
    df["signed_vol"] = ret_sign * df["volume"]
    df["imb"] = (df["signed_vol"].rolling(p["imb_window"]).sum()
                 / df["volume"].rolling(p["imb_window"]).sum())
    df["relvol"] = (df["volume"].rolling(p["relvol_fast"]).mean()
                    / df["volume"].rolling(p["relvol_slow"]).mean())
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    clv = (((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng).fillna(0)
    df["clv_s"] = clv.rolling(p["clv_smooth"]).mean()
    df["vwap"] = anchored_vwap(df)
    df["above_vwap"] = df["close"] > df["vwap"]
    df["cum_signed"] = df["signed_vol"].groupby(day.values).cumsum()
    df["cum_signed_hi"] = df.groupby(day.values)["cum_signed"].cummax()
    day_vol = df["volume"].groupby(day.values).cumsum()
    df["day_imb"] = df["cum_signed"] / day_vol.replace(0, np.nan)
    df["day_high"] = df.groupby(day.values)["high"].cummax()
    mins = ((df.index - df.index.normalize()) - pd.Timedelta(hours=9, minutes=30))
    df["min_of_day"] = (mins.total_seconds() / 60).astype(int)
    # minute at which the current running day-high was set
    is_new_high = df["high"] >= df["day_high"]
    hod_min = df["min_of_day"].where(is_new_high).groupby(day.values).ffill()
    df["hod_min"] = hod_min
    below = (~df["above_vwap"]).astype(int)
    df["below_streak"] = below.groupby(day.values).apply(
        lambda s: s * (s.groupby((s != s.shift()).cumsum()).cumcount() + 1)
    ).reset_index(level=0, drop=True)
    # failed reclaim: some bar in the last 10 touched VWAP from below and closed under it
    touched = (df["high"] >= df["vwap"]) & (~df["above_vwap"])
    df["failed_reclaim"] = touched.rolling(10).max().astype(bool)
    # gap-up context: session opened at/above the prior session's close
    # (thinkScript equivalent: open(period=DAY) >= close(period=DAY)[1])
    day_open = df.groupby(day.values)["open"].transform("first")
    prev_close_by_day = df["close"].groupby(day.values).last().shift()
    df["gap_up"] = day_open >= pd.Series(day.values, index=df.index).map(prev_close_by_day)

    # prior session's final anchored VWAP (thinkScript: cumPV[1]/cumV[1] at newSession)
    prev_vwap_by_day = df["vwap"].groupby(day.values).last().shift()
    df["prior_vwap"] = pd.Series(day.values, index=df.index).map(prev_vwap_by_day)

    # 3-day run-up ending at the prior close (thinkScript: closeD[1]/closeD[4] - 1)
    if daily_closes is not None and len(daily_closes) >= 4:
        dc = daily_closes.sort_index()
        runup = {}
        for d in pd.unique(day.values):
            prior = dc[dc.index < pd.Timestamp(d)]
            runup[d] = (prior.iloc[-1] / prior.iloc[-4] - 1) if len(prior) >= 4 else np.nan
        df["runup_3d"] = pd.Series(day.values, index=df.index).map(runup)
    else:
        df["runup_3d"] = np.nan
    return df


def generate_signals(feat: pd.DataFrame, p: dict) -> pd.DataFrame:
    # v1.1: exhaustion gate — a NaN run-up (not enough history) passes the gate
    if p.get("runup_gate") is not None:
        not_exhausted = ~(feat["runup_3d"] > p["runup_gate"])
    else:
        not_exhausted = pd.Series(True, index=feat.index)
    # warm-up gate: the rolling imbalance window must be same-day bars only;
    # v1.1: no fresh BUY after the cutoff (late entries have no runway)
    buy_raw = ((feat["min_of_day"] >= p["imb_window"])
               & (feat["min_of_day"] <= p.get("buy_cutoff_min", 390))
               & not_exhausted
               & feat["above_vwap"]
               & (feat["imb"] >= p["buy_thresh"])
               & (feat["relvol"] >= p["relvol_thresh"])
               & (feat["clv_s"] > 0)
               & (feat["cum_signed"] >= feat["cum_signed_hi"]))
    # opening rejection uses the day-anchored imbalance (resets at 09:30) so the
    # signal reflects today's tape only; needs a few bars to be meaningful.
    # v1.1: requires price below the prior session's VWAP — distribution context —
    # which separates the Jul-2 liquidation from the Jul-1 opening shakeout.
    if p.get("prior_vwap_gate"):
        distrib_ctx = (feat["close"] < feat["prior_vwap"]) | feat["prior_vwap"].isna()
    else:
        distrib_ctx = pd.Series(True, index=feat.index)
    sell_open = ((feat["min_of_day"] >= 5)
                 & (feat["min_of_day"] <= p["open_window_min"])
                 & (feat["hod_min"] <= p["open_high_min"])
                 & feat["gap_up"]           # the Jul-2 context: a gap-up open, rejected
                 & distrib_ctx
                 & (~feat["above_vwap"])
                 & (feat["day_imb"] <= p["sell_thresh"])
                 & (feat["relvol"] >= p["relvol_thresh"]))
    sell_dist = ((feat["below_streak"] >= p["below_vwap_bars"])
                 & (feat["imb"] <= p["sell_thresh"])
                 & (feat["failed_reclaim"])
                 & (feat["clv_s"] < 0))

    rows = []
    last_fire = {"BUY": None, "SELL": None}
    day = pd.Series(feat.index.date, index=feat.index)
    for kind, raw, trig in (("BUY", buy_raw, "accumulation"),
                            ("SELL", sell_open, "opening-rejection"),
                            ("SELL", sell_dist, "distribution")):
        edges = raw & ~raw.shift(fill_value=False)
        for ts in feat.index[edges]:
            prev = last_fire[kind]
            if prev is not None and prev[1] == day.loc[ts] and \
                    (ts - prev[0]).total_seconds() < p["cooldown_min"] * 60:
                continue
            last_fire[kind] = (ts, day.loc[ts])
            rows.append({"ts": ts, "signal": kind, "trigger": trig,
                         "price": float(feat.loc[ts, "close"]),
                         "imb": round(float(feat.loc[ts, "imb"]), 3)})
    empty = pd.DataFrame({"ts": pd.Series(dtype="datetime64[ns, America/New_York]"),
                          "signal": pd.Series(dtype=str), "trigger": pd.Series(dtype=str),
                          "price": pd.Series(dtype=float), "imb": pd.Series(dtype=float)})
    out = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True) if rows else empty
    # cooldown applied per kind in chronological order (re-sweep after sort)
    keep, last = [], {}
    for _, r in out.iterrows():
        k = r["signal"]
        if k in last and r["ts"].date() == last[k].date() and \
                (r["ts"] - last[k]).total_seconds() < p["cooldown_min"] * 60:
            continue
        last[k] = r["ts"]
        keep.append(r)
    return pd.DataFrame(keep).reset_index(drop=True) if keep else out


def audit_signals(feat: pd.DataFrame, signals: pd.DataFrame,
                  target_pct: float = 1.25) -> pd.DataFrame:
    """Rest-of-day outcome per signal: MFE, MAE, to-close, and a managed exit
    (profit target, VWAP-cross stop against the position, else 15:59)."""
    rows = []
    for _, r in signals.iterrows():
        sgn = 1 if r["signal"] == "BUY" else -1
        bars = feat[(feat.index.date == r["ts"].date()) & (feat.index > r["ts"])]
        if bars.empty:
            continue
        path = (bars["close"] / r["price"] - 1) * 100 * sgn
        managed, exit_reason = float(path.iloc[-1]), "close"
        for ts, v in path.items():
            if v >= target_pct:
                managed, exit_reason = target_pct, "target"
                break
            crossed = (bars.loc[ts, "close"] < bars.loc[ts, "vwap"]) if sgn == 1 \
                else (bars.loc[ts, "close"] > bars.loc[ts, "vwap"])
            if crossed:
                managed, exit_reason = float(v), "vwap-stop"
                break
        rows.append({"ts": r["ts"], "signal": r["signal"], "trigger": r["trigger"],
                     "price": r["price"], "mfe": round(float(path.max()), 2),
                     "mae": round(float(path.min()), 2),
                     "to_close": round(float(path.iloc[-1]), 2),
                     "managed": round(managed, 2), "exit": exit_reason})
    return pd.DataFrame(rows)


def chart_compare(feat: pd.DataFrame, sig_old: pd.DataFrame, sig_new: pd.DataFrame,
                  out, title: str) -> None:
    """Snapshot: v1.0 signals (hollow, X = removed) vs v1.1 (solid)."""
    days = sorted({ts.date() for ts in feat.index})
    fig, axes = plt.subplots(1, len(days), figsize=(4.4 * len(days), 5.2), squeeze=False)
    new_keys = {(r["ts"], r["signal"]) for _, r in sig_new.iterrows()}
    for ax, d in zip(axes[0], days):
        bars = feat[feat.index.date == d]
        ax.plot(bars.index, bars["close"], color="#1565c0", lw=0.8)
        ax.plot(bars.index, bars["vwap"], color="#6a1b9a", lw=0.9, ls="--")
        for _, r in sig_old[sig_old["ts"].dt.date == d].iterrows():
            kept = (r["ts"], r["signal"]) in new_keys
            up = r["signal"] == "BUY"
            color = UP if up else DOWN
            if kept:
                ax.scatter([r["ts"]], [r["price"]], marker="^" if up else "v", s=110,
                           color=color, edgecolors="black", linewidths=0.7, zorder=6)
                ax.annotate(f"{r['signal']} {r['ts']:%H:%M}", xy=(r["ts"], r["price"]),
                            xytext=(0, 16 if up else -26), textcoords="offset points",
                            ha="center", fontsize=7.5, color=color, fontweight="bold")
            else:
                ax.scatter([r["ts"]], [r["price"]], marker="^" if up else "v", s=90,
                           facecolors="none", edgecolors=color, linewidths=1.2, zorder=5)
                ax.scatter([r["ts"]], [r["price"]], marker="x", s=120, color="#212121",
                           linewidths=1.6, zorder=7)
                ax.annotate(f"removed {r['ts']:%H:%M}", xy=(r["ts"], r["price"]),
                            xytext=(0, 16 if up else -26), textcoords="offset points",
                            ha="center", fontsize=7, color="#616161", style="italic")
        # v1.1-only signals (new ones that v1.0 didn't have)
        old_keys = {(r["ts"], r["signal"]) for _, r in sig_old.iterrows()}
        for _, r in sig_new[sig_new["ts"].dt.date == d].iterrows():
            if (r["ts"], r["signal"]) in old_keys:
                continue
            up = r["signal"] == "BUY"
            ax.scatter([r["ts"]], [r["price"]], marker="^" if up else "v", s=110,
                       color=UP if up else DOWN, edgecolors="blue", linewidths=1.4, zorder=6)
        ax.set_title(str(d), fontsize=9)
        ax.grid(alpha=0.25)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=bars.index.tz))
        ax.tick_params(labelsize=7)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def forward_returns(feat: pd.DataFrame, signals: pd.DataFrame,
                    horizons=(15, 30, 60)) -> pd.DataFrame:
    closes = feat["close"]
    rows = []
    for _, r in signals.iterrows():
        entry = r["price"]
        row = dict(r)
        for h in horizons:
            target = r["ts"] + pd.Timedelta(minutes=h)
            day_bars = closes[(closes.index.date == r["ts"].date()) & (closes.index <= target)]
            exitp = float(day_bars.iloc[-1]) if len(day_bars) else np.nan
            fwd = (exitp / entry - 1) * 100
            row[f"fwd_{h}m"] = round(fwd if r["signal"] == "BUY" else -fwd, 3)
        rows.append(row)
    return pd.DataFrame(rows)


def evaluate(week_sig: pd.DataFrame, base_sig: pd.DataFrame, base_days: int) -> dict:
    jul2 = week_sig[(week_sig["signal"] == "SELL")
                    & (week_sig["ts"].dt.date == pd.Timestamp("2026-07-02").date())]
    jun29 = week_sig[(week_sig["signal"] == "BUY")
                     & (week_sig["ts"].dt.date == pd.Timestamp("2026-06-29").date())]
    first_sell = jul2["ts"].min() if len(jul2) else None
    first_buy = jun29["ts"].min() if len(jun29) else None
    return {
        "sell_fired_jul2": None if first_sell is None else str(first_sell),
        "sell_by_1005": bool(first_sell is not None
                             and first_sell.time() <= pd.Timestamp("10:05").time()),
        "buy_fired_jun29": None if first_buy is None else str(first_buy),
        "buy_in_morning_drive": bool(first_buy is not None
                                     and first_buy.time() <= pd.Timestamp("11:00").time()),
        "baseline_signals_per_day": round(len(base_sig) / max(base_days, 1), 2),
    }


def tune(week_feat, base_feat, base_days) -> tuple[dict, list[dict]]:
    trials = []
    for bt, st in itertools.product((0.15, 0.20, 0.25, 0.30), repeat=2):
        p = {**DEFAULTS, "buy_thresh": bt, "sell_thresh": -st}
        wk, bs = generate_signals(week_feat, p), generate_signals(base_feat, p)
        ev = evaluate(wk, bs, base_days)
        score = (2 * ev["sell_by_1005"] + 2 * ev["buy_in_morning_drive"]
                 - min(ev["baseline_signals_per_day"], 4) * 0.5)
        trials.append({"buy_thresh": bt, "sell_thresh": -st, "score": round(score, 2), **ev})
    # tie-break toward the thresholds actually measured during the week
    # (imbalance +0.20 accumulation / -0.30 within the liquidation window)
    best = max(trials, key=lambda t: (t["score"], t["buy_thresh"] == 0.20,
                                      t["sell_thresh"] == -0.30))
    chosen = {**DEFAULTS, "buy_thresh": best["buy_thresh"], "sell_thresh": best["sell_thresh"]}
    return chosen, trials


def chart_signals(feat: pd.DataFrame, signals: pd.DataFrame, out) -> None:
    days = sorted({ts.date() for ts in feat.index})
    fig, axes = plt.subplots(1, len(days), figsize=(4.2 * len(days), 5), squeeze=False)
    for ax, d in zip(axes[0], days):
        bars = feat[feat.index.date == d]
        ax.plot(bars.index, bars["close"], color="#1565c0", lw=0.8)
        ax.plot(bars.index, bars["vwap"], color="#6a1b9a", lw=0.9, ls="--")
        s = signals[signals["ts"].dt.date == d]
        for _, r in s.iterrows():
            up = r["signal"] == "BUY"
            ax.scatter([r["ts"]], [r["price"]], marker="^" if up else "v",
                       color=UP if up else DOWN, s=90, zorder=5,
                       edgecolors="black", linewidths=0.6)
            ax.annotate(f"{r['signal']}\n{r['ts']:%H:%M}", xy=(r["ts"], r["price"]),
                        xytext=(0, 14 if up else -26), textcoords="offset points",
                        ha="center", fontsize=7, color=UP if up else DOWN)
        ax.set_title(str(d), fontsize=9)
        ax.grid(alpha=0.25)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=bars.index.tz))
        ax.tick_params(labelsize=7)
    fig.suptitle("FlowForensics signals on the target week (Python mirror of the thinkScript rules)")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def run_signals(client: FMPClient, settings) -> dict:
    s = settings
    week_1m = dl.intraday(client, s.symbol, "1min", s.target_start, s.target_end)
    base_start = (pd.Timestamp(s.baseline_end) - pd.Timedelta(days=13)).date().isoformat()
    base_1m = dl.intraday(client, s.symbol, "1min", base_start, s.baseline_end)
    daily = dl.daily(client, s.symbol, s.daily_start, s.target_end)
    daily_closes = daily["close"]

    week_feat = compute_features(week_1m, DEFAULTS, daily_closes)
    base_feat = compute_features(base_1m, DEFAULTS, daily_closes)
    base_days = len({ts.date() for ts in base_feat.index})

    chosen, trials = tune(week_feat, base_feat, base_days)
    week_sig = generate_signals(week_feat, chosen)
    base_sig = generate_signals(base_feat, chosen)
    ev = evaluate(week_sig, base_sig, base_days)
    week_fwd = forward_returns(week_feat, week_sig)
    base_fwd = forward_returns(base_feat, base_sig)

    # v1.0 (pre-audit rules) for the before/after comparison
    v10 = {**chosen, **V10_OVERRIDES}
    week_sig_v10 = generate_signals(week_feat, v10)
    base_sig_v10 = generate_signals(base_feat, v10)
    audits = {
        "week_v10": audit_signals(week_feat, week_sig_v10, chosen["target_pct"]),
        "week_v11": audit_signals(week_feat, week_sig, chosen["target_pct"]),
        "base_v10": audit_signals(base_feat, base_sig_v10, chosen["target_pct"]),
        "base_v11": audit_signals(base_feat, base_sig, chosen["target_pct"]),
    }

    out_dir = s.output_dir
    (out_dir / "charts").mkdir(parents=True, exist_ok=True)
    chart_signals(week_feat, week_sig, out_dir / "charts" / "signal_validation.png")
    chart_compare(week_feat, week_sig_v10, week_sig,
                  out_dir / "charts" / "signals_before_after_week.png",
                  "FlowForensics v1.0 → v1.1 — target week (X = removed by audit gates)")
    chart_compare(base_feat, base_sig_v10, base_sig,
                  out_dir / "charts" / "signals_before_after_baseline.png",
                  "FlowForensics v1.0 → v1.1 — baseline (X = removed by audit gates)")
    _write_report(chosen, trials, ev, week_fwd, base_fwd, base_days,
                  out_dir / "signal_validation.md", audits)
    return {"chosen": chosen, "eval": ev, "week_signals": week_fwd,
            "baseline_signals": base_fwd, "audits": audits}


def _audit_summary(a: pd.DataFrame) -> dict:
    if a.empty:
        return {"n": 0}
    return {"n": len(a),
            "win_close": f"{(a['to_close'] > 0).mean():.0%}",
            "mean_close": f"{a['to_close'].mean():+.2f}%",
            "win_managed": f"{(a['managed'] > 0).mean():.0%}",
            "mean_managed": f"{a['managed'].mean():+.2f}%"}


def _write_report(chosen, trials, ev, week_fwd, base_fwd, base_days, out,
                  audits=None) -> None:
    lines = ["# FlowForensics signal validation (hard evidence)\n",
             "The thinkScript rules re-implemented bar-for-bar in Python and run on the "
             "cached 1-minute data: the target week (the two measured regimes) plus a "
             f"{base_days}-day baseline for sparsity and forward-return context.\n",
             "## Chosen defaults (shipped in the .ts files)\n"]
    add = lines.append
    add(tabulate([[k, v] for k, v in chosen.items()], headers=["input", "default"],
                 tablefmt="github"))
    add("\n## Event capture\n")
    add(f"- SELL on 2026-07-02: fired at **{ev['sell_fired_jul2']}** "
        f"(within the 09:36–10:05 liquidation onset: **{ev['sell_by_1005']}**)")
    add(f"- BUY on 2026-06-29: fired at **{ev['buy_fired_jun29']}** "
        f"(within the morning accumulation drive: **{ev['buy_in_morning_drive']}**)")
    add(f"- baseline sparsity: **{ev['baseline_signals_per_day']} signals/day** over the baseline")
    add("\n## Target-week signals (signed forward returns, % in signal direction)\n")
    if len(week_fwd):
        add(week_fwd.assign(ts=week_fwd["ts"].astype(str)).to_markdown(index=False))
    add("\n## Baseline signals\n")
    if len(base_fwd):
        add(base_fwd.assign(ts=base_fwd["ts"].astype(str)).to_markdown(index=False))
        for h in (15, 30, 60):
            col = base_fwd[f"fwd_{h}m"].dropna()
            if len(col):
                add(f"- baseline +{h}m: mean {col.mean():+.2f}%, hit rate "
                    f"{(col > 0).mean():.0%} (n={len(col)})")
    else:
        add("_No baseline signals at chosen thresholds._")
    if audits:
        add("\n## v1.0 → v1.1 audit (per-signal rest-of-day outcomes)\n")
        add("Gates added after the per-signal audit: BUY cutoff 15:00, 3-day run-up "
            f"gate {chosen['runup_gate']:.0%}, prior-session-VWAP context for opening "
            "rejections. `managed` = exit at "
            f"+{chosen['target_pct']}% target, VWAP-cross stop, or session end.\n")
        for scope in ("week", "base"):
            for ver in ("v10", "v11"):
                a = audits[f"{scope}_{ver}"]
                add(f"**{scope} {ver}** — " + ", ".join(
                    f"{k}={v}" for k, v in _audit_summary(a).items()))
                if not a.empty:
                    t = a.assign(ts=a["ts"].astype(str).str[:16])
                    add(t.to_markdown(index=False))
                add("")
    add("\n## Threshold grid\n")
    add(tabulate([[t["buy_thresh"], t["sell_thresh"], t["score"], t["sell_by_1005"],
                   t["buy_in_morning_drive"], t["baseline_signals_per_day"]] for t in trials],
                 headers=["buyT", "sellT", "score", "sell≤10:05", "buy≤11:00", "base/day"],
                 tablefmt="github"))
    add("\n**Sample-size honesty:** these rules encode two measured regimes from one stock "
        "and one week plus a 2-week baseline. Run thinkorswim's own strategy report over "
        "longer history before any live use. Not investment advice.")
    out.write_text("\n".join(lines))
    log.info("signal validation written to %s", out)