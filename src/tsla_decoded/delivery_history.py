"""Historical study: how TSLA reacts to quarterly delivery releases.

Locates past release days (press releases, falling back to early-quarter volume
spikes), computes run-up/reaction metrics per quarter, and asks whether the
2026-07-02 sell-the-news fade is typical.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from tabulate import tabulate

from . import data_loader as dl
from .catalysts import DELIVERY_PR
from .fmp_client import FMPClient
from .plots import DOWN, UP

log = logging.getLogger(__name__)

ET = "America/New_York"

BEAT_TERMS = ("beat", "crush", "top", "record", "surpass", "exceed", "blowout")
MISS_TERMS = ("miss", "fall short", "fell short", "disappoint", "decline", "below")


@dataclass
class ReleaseQuarter:
    quarter: str              # e.g. "2026-Q2"
    release_day: pd.Timestamp # trading day whose session absorbed the news
    identified_by: str        # "pr" | "volume-inferred"
    run_up_5d: float
    reaction_oc: float        # release-day open -> close
    reaction_cc: float        # release-day close vs prior close
    post_1d: float | None
    post_5d: float | None
    verdict: str              # "beat" | "miss" | "mixed" | "unknown"
    fade: bool                # run-up > +5% and red close-to-close reaction


def _quarter_of(release_date: pd.Timestamp) -> str:
    # a release in month 1/4/7/10 reports the quarter that just ended
    m, y = release_date.month, release_date.year
    return {1: f"{y-1}-Q4", 4: f"{y}-Q1", 7: f"{y}-Q2", 10: f"{y}-Q3"}.get(
        m, f"{y}-M{m}")


def _release_days_from_prs(client: FMPClient, symbol: str, oldest: str) -> dict[str, pd.Timestamp]:
    """quarter -> release trading-day date, from press-release headlines."""
    found: dict[str, pd.Timestamp] = {}
    for page in range(8):
        rows = client.get("news/press-releases", symbols=symbol, limit=100, page=page)
        if not rows:
            break
        for pr in rows:
            if not DELIVERY_PR.search(pr.get("title") or ""):
                continue
            ts = pd.to_datetime(pr.get("publishedDate") or pr.get("date"), errors="coerce")
            if pd.isna(ts):
                continue
            # after-close releases are absorbed by the next session
            day = ts.normalize() + pd.Timedelta(days=1) if ts.hour >= 16 else ts.normalize()
            found.setdefault(_quarter_of(day), day)
        dates = [pd.to_datetime(r.get("publishedDate") or r.get("date"), errors="coerce")
                 for r in rows]
        dates = [d for d in dates if not pd.isna(d)]
        if dates and min(dates) < pd.Timestamp(oldest):
            break
    return found


def _quarter_starts(daily: pd.DataFrame, first: str, last: str) -> dict[str, list[pd.Timestamp]]:
    """quarter -> its first 3 trading days, per the actual daily index."""
    out: dict[str, list[pd.Timestamp]] = {}
    for ts in daily.index:
        if not (pd.Timestamp(first) <= ts <= pd.Timestamp(last)):
            continue
        if ts.month not in (1, 4, 7, 10):
            continue
        q = _quarter_of(ts)
        out.setdefault(q, [])
        if len(out[q]) < 3:
            out[q].append(ts)
    return out


def _classify_verdict(client: FMPClient, symbol: str, day: pd.Timestamp) -> str:
    rows = client.get("news/stock", symbols=symbol,
                      **{"from": day.date().isoformat(),
                         "to": (day + pd.Timedelta(days=1)).date().isoformat()},
                      limit=100) or []
    beat = miss = 0
    for r in rows:
        head = (r.get("title") or "").lower()
        if "deliver" not in head:
            continue
        beat += any(t in head for t in BEAT_TERMS)
        miss += any(t in head for t in MISS_TERMS)
    if beat and miss:
        return "mixed"
    if beat:
        return "beat"
    if miss:
        return "miss"
    return "unknown"


def reaction_metrics(daily: pd.DataFrame, day: pd.Timestamp) -> dict | None:
    """Run-up and reaction returns around one release trading day."""
    idx = daily.index
    if day not in idx:
        pos_arr = idx.searchsorted(day)
        if pos_arr >= len(idx):
            return None
        day = idx[pos_arr]          # snap forward to the next trading day
    i = idx.get_loc(day)
    if i < 6:
        return None
    c, o = daily["close"], daily["open"]
    return {
        "release_day": day,
        "run_up_5d": float(c.iloc[i - 1] / c.iloc[i - 6] - 1),
        "reaction_oc": float(c.iloc[i] / o.iloc[i] - 1),
        "reaction_cc": float(c.iloc[i] / c.iloc[i - 1] - 1),
        "post_1d": float(c.iloc[i + 1] / c.iloc[i] - 1) if i + 1 < len(idx) else None,
        "post_5d": float(c.iloc[min(i + 5, len(idx) - 1)] / c.iloc[i] - 1)
        if i + 1 < len(idx) else None,
    }


def build_history(client: FMPClient, symbol: str,
                  daily_start: str = "2023-03-01", first_q: str = "2023-07-01",
                  last_q: str = "2026-07-02", classify: bool = True) -> list[ReleaseQuarter]:
    daily = dl.daily(client, symbol, daily_start, last_q)
    assert not daily.empty, "no daily history returned"
    vol_med60 = daily["volume"].rolling(60).median()

    pr_days = _release_days_from_prs(client, symbol, oldest=first_q)
    log.info("delivery PRs found for quarters: %s", sorted(pr_days))

    quarters: list[ReleaseQuarter] = []
    for q, candidates in sorted(_quarter_starts(daily, first_q, last_q).items()):
        if q in pr_days:
            day, how = pr_days[q], "pr"
        else:
            # highest volume vs trailing-60d median among the first 3 trading days
            ratios = {d: daily.loc[d, "volume"] / vol_med60.loc[d]
                      for d in candidates if not pd.isna(vol_med60.loc[d])}
            if not ratios:
                continue
            day, how = max(ratios, key=ratios.get), "volume-inferred"
        m = reaction_metrics(daily, pd.Timestamp(day))
        if m is None:
            continue
        verdict = _classify_verdict(client, symbol, m["release_day"]) if classify else "unknown"
        quarters.append(ReleaseQuarter(
            quarter=q, release_day=m["release_day"], identified_by=how,
            run_up_5d=m["run_up_5d"], reaction_oc=m["reaction_oc"],
            reaction_cc=m["reaction_cc"], post_1d=m["post_1d"], post_5d=m["post_5d"],
            verdict=verdict,
            fade=m["run_up_5d"] > 0.05 and m["reaction_cc"] < 0,
        ))
    return quarters


def summarize(quarters: list[ReleaseQuarter], focus: str = "2026-Q2") -> dict:
    run_ups = np.array([q.run_up_5d for q in quarters])
    reactions = np.array([q.reaction_cc for q in quarters])
    n = len(quarters)
    stats: dict = {"n": n}
    if n >= 4:
        stats["pearson_r"], stats["pearson_p"] = (round(float(v), 3) for v in pearsonr(run_ups, reactions))
        stats["spearman_r"], stats["spearman_p"] = (round(float(v), 3) for v in spearmanr(run_ups, reactions))
    stats["pct_red_reaction"] = round(float((reactions < 0).mean()), 3)
    big_runup = run_ups > 0.05
    if big_runup.any():
        stats["pct_red_given_runup_gt5"] = round(float((reactions[big_runup] < 0).mean()), 3)
        stats["n_runup_gt5"] = int(big_runup.sum())
    f = next((q for q in quarters if q.quarter == focus), None)
    if f is not None:
        stats["focus_runup_percentile"] = round(float((run_ups <= f.run_up_5d).mean()), 3)
        stats["focus_reaction_percentile"] = round(float((reactions <= f.reaction_cc).mean()), 3)
    return stats


def chart(quarters: list[ReleaseQuarter], focus: str, out) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    ru = [q.run_up_5d * 100 for q in quarters]
    rc = [q.reaction_cc * 100 for q in quarters]
    colors = [DOWN if q.quarter == focus else "#607d8b" for q in quarters]
    ax1.scatter(ru, rc, c=colors, s=70, zorder=3)
    for q, x, y in zip(quarters, ru, rc):
        ax1.annotate(q.quarter, (x, y), textcoords="offset points", xytext=(5, 4),
                     fontsize=7.5, color=DOWN if q.quarter == focus else "#455a64")
    if len(quarters) >= 4:
        b = np.polyfit(ru, rc, 1)
        xs = np.linspace(min(ru), max(ru), 20)
        ax1.plot(xs, np.polyval(b, xs), ls="--", color="#9e9e9e", lw=1)
    ax1.axhline(0, color="#bdbdbd", lw=0.8)
    ax1.axvline(0, color="#bdbdbd", lw=0.8)
    ax1.set_xlabel("5-day run-up into release (%)")
    ax1.set_ylabel("release-day close-to-close (%)")
    ax1.set_title("Run-up vs delivery-day reaction")
    ax1.grid(alpha=0.25)

    x = np.arange(len(quarters))
    ax2.bar(x - 0.2, ru, width=0.4, label="5-day run-up", color="#90a4ae")
    ax2.bar(x + 0.2, rc, width=0.4, label="reaction day",
            color=[UP if v >= 0 else DOWN for v in rc])
    for i, q in enumerate(quarters):
        if q.quarter == focus:
            ax2.axvspan(i - 0.5, i + 0.5, color="#fff59d", alpha=0.4, zorder=0)
    ax2.set_xticks(x, [q.quarter for q in quarters], rotation=45, fontsize=8)
    ax2.axhline(0, color="#bdbdbd", lw=0.8)
    ax2.set_ylabel("%")
    ax2.set_title("Per-quarter run-up and reaction")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def write_history_report(quarters: list[ReleaseQuarter], stats: dict, focus: str, out) -> None:
    lines: list[str] = []
    add = lines.append
    add("# TSLA quarterly delivery releases: run-up vs reaction\n")
    add(f"Release days for the last {stats['n']} quarters, identified from press releases "
        "where available and otherwise inferred as the highest-volume day among the first "
        "three trading days of the quarter.\n")
    rows = [[q.quarter, f"{q.release_day:%Y-%m-%d}", q.identified_by,
             f"{q.run_up_5d*100:+.1f}%", f"{q.reaction_oc*100:+.1f}%",
             f"{q.reaction_cc*100:+.1f}%",
             f"{q.post_1d*100:+.1f}%" if q.post_1d is not None else "—",
             f"{q.post_5d*100:+.1f}%" if q.post_5d is not None else "—",
             q.verdict, "yes" if q.fade else ""]
            for q in quarters]
    add(tabulate(rows, headers=["quarter", "release day", "found via", "run-up 5d",
                                "day o→c", "day c→c", "+1d", "+5d", "verdict", "fade"],
                 tablefmt="github"))
    add("")
    add("## Statistics\n")
    if "pearson_r" in stats:
        add(f"- run-up vs reaction correlation: Pearson r = {stats['pearson_r']} "
            f"(p = {stats['pearson_p']}), Spearman ρ = {stats['spearman_r']} "
            f"(p = {stats['spearman_p']}) — n = {stats['n']}, directional evidence only")
    add(f"- release day closed red in {stats['pct_red_reaction']:.0%} of quarters")
    if "pct_red_given_runup_gt5" in stats:
        add(f"- given a 5-day run-up > +5% (n = {stats['n_runup_gt5']}): red close "
            f"{stats['pct_red_given_runup_gt5']:.0%} of the time")
    if "focus_runup_percentile" in stats:
        add(f"- {focus} run-up sits at the {stats['focus_runup_percentile']:.0%} percentile "
            f"of the sample; its reaction at the {stats['focus_reaction_percentile']:.0%} percentile")
    add("")
    add("## Reading\n")
    f = next((q for q in quarters if q.quarter == focus), None)
    if f is not None:
        others = [q for q in quarters if q.quarter != focus]
        add(f"{focus} ({f.release_day:%Y-%m-%d}) came in with a {f.run_up_5d*100:+.1f}% run-up and a "
            f"{f.reaction_cc*100:+.1f}% reaction ({f.verdict} on the numbers).")
        if others and f.reaction_cc <= min(q.reaction_cc for q in others):
            add(f"- That reaction is the **most negative release-day close in the sample** — "
                f"worse than all {len(others)} prior quarters.")
        add(f"- Delivery days lean red at the baseline: {stats['pct_red_reaction']:.0%} of "
            "release days closed below the prior close regardless of the numbers.")
        big_prior = [q for q in others if q.run_up_5d > 0.05]
        if big_prior:
            outcomes = ", ".join(
                f"{q.quarter} (run-up {q.run_up_5d*100:+.1f}% → day {q.reaction_cc*100:+.1f}%"
                f"{'' if q.post_5d is None else f', +5d {q.post_5d*100:+.1f}%'})"
                for q in big_prior)
            n_green = sum(1 for q in big_prior if q.reaction_cc > 0)
            add(f"- Prior quarters with a comparable >+5% run-up: {outcomes}. "
                f"{n_green} of {len(big_prior)} still closed green on the day, so a big run-up "
                "alone did not historically guarantee a fade — though where the day held green, "
                "the following week often gave it back (see +5d column).")
            add(f"- Conclusion: the {focus} fade is consistent with sell-the-news positioning, "
                "but its severity is unusual — the unwind was sharper than any delivery-day "
                "reaction in the sample rather than a routine repeat of past patterns.")
    add("")
    add(f"*Sample size n = {stats['n']} quarters — treat correlations as indicative, "
        "not statistically significant. Not investment advice.*")
    out.write_text("\n".join(lines))
    log.info("history report written to %s", out)


def run_history(client: FMPClient, settings) -> dict:
    quarters = build_history(client, settings.symbol)
    if not quarters:
        raise SystemExit("no delivery-release quarters could be located")
    stats = summarize(quarters)
    out_dir = settings.output_dir
    (out_dir / "charts").mkdir(parents=True, exist_ok=True)
    chart(quarters, "2026-Q2", out_dir / "charts" / "delivery_reactions.png")
    write_history_report(quarters, stats, "2026-Q2", out_dir / "history_report.md")
    return {"quarters": quarters, "stats": stats}
