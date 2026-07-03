"""Final markdown report with per-event attribution table and verdicts."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from tabulate import tabulate

log = logging.getLogger(__name__)


def _fmt_idio(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{v:.0%}"


def write_report(state: dict, settings, out: Path):
    events = state["events"]
    att = state["attributions"]
    thr = settings.loop["confidence_threshold"]
    lines: list[str] = []
    add = lines.append

    add(f"# TSLA decoded: {settings.target_start} → {settings.target_end}\n")
    add("Forensic attribution of the week's price action from FMP intraday/news data: "
        "seasonality-adjusted event detection, SPY/QQQ beta decomposition, catalyst "
        "time-alignment, order-flow proxies, and an iterative escalation loop.\n")

    # week summary from daily data
    add("## The week at a glance\n")
    d = state["daily_week"]
    rows = [[ts.date(), f"{r['open']:.2f}", f"{r['high']:.2f}", f"{r['low']:.2f}",
             f"{r['close']:.2f}", f"{r['changePercent']:+.2f}%", f"{r['volume']/1e6:.1f}M"]
            for ts, r in d.iterrows()]
    add(tabulate(rows, headers=["date", "open", "high", "low", "close", "chg", "volume"],
                 tablefmt="github"))
    add("")

    # deliveries hypothesis
    dc = state.get("deliveries_check")
    add("## Q2 deliveries hypothesis\n")
    if dc and dc.get("found"):
        add(f"**Release found:** “{dc['headline']}”")
        add(f"- timestamp: {dc['ts'] or 'not provided by source'}"
            f"{'' if dc['timing_precise'] else ' (date-only precision)'}")
        if dc.get("figures"):
            add(f"- extracted figures: {dc['figures']}")
        if dc.get("reaction_headlines"):
            add("- reaction coverage: " + "; ".join(f"“{h[:80]}”" for h in dc["reaction_headlines"][:4]))
    else:
        add("No Q2 production/deliveries release found in press-release or news data "
            "for the window — hypothesis unconfirmed by available sources.")
    add("")

    # market model
    mm = state["market_model"]
    add("## Market decomposition model\n")
    add(f"OLS of TSLA 5-min returns on {', '.join(settings.benchmarks)} over the baseline "
        f"({settings.baseline_start} → {settings.baseline_end}): "
        f"R² = {mm['r_squared']}, betas = "
        + ", ".join(f"{k}={v}" for k, v in mm["params"].items() if k != "const") + ".")
    add("An event's *idio share* is the fraction of its move not explained by this model — "
        "high idio share means TSLA-specific cause, low means the market moved TSLA.\n")

    # per-event table
    add("## Detected events and attribution\n")
    rows = []
    for ev in events:
        a = att[ev.event_id]
        cands = a["candidates"]
        top = cands[0] if cands else None
        rows.append([
            ev.event_id,
            f"{ev.start:%a %m-%d %H:%M}" + (f"–{ev.end:%H:%M}" if ev.end != ev.start else ""),
            ev.kind,
            f"{ev.magnitude_pct:+.2f}%",
            f"{ev.peak_z:.1f}",
            _fmt_idio(a["idio"].get("idio_share")),
            (top["catalyst"].headline[:70] + ("…" if len(top["catalyst"].headline) > 70 else "")) if top else "—",
            f"{top['delta_minutes']:+.0f}m" if top and top["delta_minutes"] is not None else "—",
            f"{a['confidence']:.2f}",
            "✓" if a["confidence"] >= thr else "○",
        ])
    add(tabulate(rows, headers=["event", "window (ET)", "kind", "move", "peak z",
                                "idio", "top catalyst", "lead", "conf", ""],
                 tablefmt="github"))
    add("\n`lead` = minutes the catalyst preceded the event start (negative ⇒ published after "
        "the move began). `idio` = share of the move not explained by SPY/QQQ. "
        f"✓ = attributed at confidence ≥ {thr}.\n")

    # per-event detail
    add("## Event detail\n")
    for ev in events:
        a = att[ev.event_id]
        add(f"### {ev.event_id} — {ev.kind} {ev.magnitude_pct:+.2f}% "
            f"({ev.start:%A %b %d %H:%M} ET)\n")
        add(f"- peak |return z| {ev.peak_z:.1f}, volume z {ev.peak_vol_z:.1f}, "
            f"idio share {_fmt_idio(a['idio'].get('idio_share'))} "
            f"(actual {a['idio'].get('actual_pct', float('nan')):+.2f}% vs market-implied "
            f"{a['idio'].get('market_pct', float('nan')):+.2f}%)")
        flow = a.get("flow")
        if flow:
            add(f"- order flow: {flow['character']} (imbalance {flow['volume_imbalance']:+.2f}, "
                f"CLV {flow['mean_clv']:+.2f}, {flow['total_volume']/1e6:.1f}M shares)")
        for n in ev.notes:
            add(f"- {n}")
        if a["candidates"]:
            add(f"- confidence **{a['confidence']:.2f}** "
                f"(alignment {a['components']['alignment']:.2f}, "
                f"idio-consistency {a['components']['idio_consistency']:.2f}, "
                f"timing {a['components']['timing_precision']:.2f}, "
                f"uniqueness {a['components']['uniqueness']:.2f})")
            add("- candidate catalysts:")
            for c in a["candidates"][:3]:
                cat = c["catalyst"]
                when = f"{cat.ts:%m-%d %H:%M}" if cat.ts is not None else "no timestamp"
                add(f"  1. [{c['score']:.2f}] ({cat.source_type}, {when}) {cat.headline[:110]}")
        else:
            add(f"- confidence **{a['confidence']:.2f}** — no catalyst matched the window; "
                "candidates below threshold or outside search scope")
        add("")

    # iterations
    add("## Investigation loop\n")
    for it in state["iterations"]:
        add(f"- iteration {it['iteration']} [{it['stage']}] — events {it['events']}, "
            f"confidences {it['confidences']} (HTTP so far: {it['http_requests_so_far']})")
    if state.get("early_stop"):
        add(f"- early stop: {state['early_stop']}")
    add("")

    # feature importance
    fi = state.get("feature_importance") or {}
    if fi:
        add("## What explains abnormal moves (permutation importance)\n")
        add(tabulate([[k, f"{v:.6f}"] for k, v in list(fi.items())[:8]],
                     headers=["feature", "importance"], tablefmt="github"))
        add("")

    # capabilities
    add("## Data sources / capabilities\n")
    add(tabulate(sorted(state["capabilities"].items()),
                 headers=["endpoint", "status"], tablefmt="github"))
    add("")

    # certainty statement
    add("## Certainty statement\n")
    unresolved = state["unresolved"]
    if unresolved:
        add(f"{len(unresolved)} event(s) remain below the {thr} confidence threshold: "
            f"{', '.join(unresolved)}. For these, the ranked candidates above are hypotheses, "
            "not verdicts; the missing evidence is noted per event.")
    else:
        add(f"All major events reached confidence ≥ {thr}.")
    add("\nCausal attribution in markets is probabilistic: timestamps, news coverage and "
        "decomposition narrow the field of explanations, but order-level intent is not "
        "observable from public OHLCV data. The confidences above quantify exactly how far "
        "the evidence goes — nothing here should be read as certainty or as investment advice.")

    out.write_text("\n".join(lines))
    log.info("report written to %s", out)
