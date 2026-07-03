"""Annotated charts (matplotlib PNGs) and a self-contained plotly dashboard."""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

log = logging.getLogger(__name__)

UP, DOWN = "#2e7d32", "#c62828"


def weekly_overview(daily: pd.DataFrame, events, out: Path):
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    d = daily.tail(45)
    colors = [UP if c >= o else DOWN for o, c in zip(d["open"], d["close"])]
    ax.vlines(d.index, d["low"], d["high"], color=colors, lw=1)
    ax.vlines(d.index, np.minimum(d["open"], d["close"]),
              np.maximum(d["open"], d["close"]), color=colors, lw=5)
    for ev in events:
        if ev.kind == "gap":
            ax.axvline(pd.Timestamp(ev.start.date()), color="#f9a825", ls="--", lw=1, alpha=0.8)
    ax.set_title("TSLA daily — context and target week")
    ax.grid(alpha=0.25)
    axv.bar(d.index, d["volume"] / 1e6, color=colors, alpha=0.7)
    axv.set_ylabel("Vol (M)")
    axv.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def intraday_day(z: pd.DataFrame, events, attributions, day, regimes, out: Path):
    dz = z[z.index.date == day]
    if dz.empty:
        return
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    ax.plot(dz.index, dz["close"], color="#1565c0", lw=1.3, label="close (5-min)")
    ax.plot(dz.index, dz["vwap"], color="#6a1b9a", lw=1.1, ls="--", label="anchored VWAP")

    if regimes is not None and len(regimes):
        rday = regimes[regimes.index.date == day]
        ylim0 = dz["close"].min() * 0.998
        for ts, reg in rday.items():
            ax.axvspan(ts, ts + pd.Timedelta(minutes=30), ymin=0, ymax=0.03,
                       color=plt.cm.YlOrRd(0.25 + 0.25 * reg), alpha=0.9)
        ax.set_ylim(bottom=ylim0)

    for ev in events:
        if ev.start.date() != day or ev.kind == "gap":
            continue
        color = UP if ev.direction == "up" else DOWN
        ax.axvspan(ev.start, max(ev.end, ev.start + pd.Timedelta(minutes=5)),
                   color=color, alpha=0.15)
        att = attributions.get(ev.event_id, {})
        cands = att.get("candidates", [])
        label = f"{ev.event_id} {ev.magnitude_pct:+.1f}% (conf {att.get('confidence', 0):.2f})"
        if cands:
            label += f"\n{cands[0]['catalyst'].headline[:60]}"
        ax.annotate(label, xy=(ev.start, dz.loc[dz.index >= ev.start, 'close'].iloc[0]),
                    xytext=(0, 30 if ev.direction == "up" else -45),
                    textcoords="offset points", fontsize=7.5,
                    arrowprops=dict(arrowstyle="->", color=color, lw=1),
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=color, alpha=0.9))
    ax.set_title(f"TSLA {day} — 5-min close, VWAP, events (regime strip along bottom)")
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.25)
    axv.bar(dz.index, dz["volume"] / 1e6, width=0.0025,
            color=np.where(dz["ret"].fillna(0) >= 0, UP, DOWN), alpha=0.8)
    axv.set_ylabel("Vol (M)")
    axv.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=dz.index.tz))
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def decomposition_chart(z: pd.DataFrame, bench_week: dict, market_model, out: Path):
    import statsmodels.api as sm
    from .features import log_returns
    rets = {"TSLA": z["ret"]}
    for sym, df in bench_week.items():
        reg = df[df["session"] == "regular"]
        rets[sym] = log_returns(reg["close"]).reindex(z.index)
    r = pd.DataFrame(rets).dropna()
    X = sm.add_constant(r[list(bench_week.keys())], has_constant="add")
    pred = market_model.result.predict(X)
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(r.index, r["TSLA"].cumsum() * 100, color="#1565c0", lw=1.4, label="TSLA actual")
    ax.plot(r.index, pred.cumsum() * 100, color="#9e9e9e", lw=1.2,
            label="market-implied (SPY+QQQ beta)")
    ax.fill_between(r.index, pred.cumsum() * 100, r["TSLA"].cumsum() * 100,
                    alpha=0.2, color="#1565c0", label="idiosyncratic component")
    ax.set_title("Cumulative 5-min return: actual vs market-implied — the gap is TSLA-specific")
    ax.set_ylabel("%")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def dashboard(z: pd.DataFrame, week_5m: pd.DataFrame, events, attributions,
              daily: pd.DataFrame, deliveries, out: Path):
    days = sorted({ts.date() for ts in z.index})
    fig = make_subplots(
        rows=2, cols=len(days), shared_xaxes=True, vertical_spacing=0.06,
        horizontal_spacing=0.02, row_heights=[0.72, 0.28],
        subplot_titles=[str(d) for d in days] + [""] * len(days))
    for col, day in enumerate(days, start=1):
        dz = z[z.index.date == day]
        raw = week_5m[(week_5m.index.date == day) & (week_5m["session"] == "regular")]
        fig.add_trace(go.Candlestick(
            x=raw.index, open=raw["open"], high=raw["high"], low=raw["low"], close=raw["close"],
            increasing_line_color=UP, decreasing_line_color=DOWN,
            name=str(day), showlegend=False), row=1, col=col)
        fig.add_trace(go.Scatter(x=dz.index, y=dz["vwap"], mode="lines",
                                 line=dict(color="#6a1b9a", width=1, dash="dot"),
                                 name="VWAP", showlegend=(col == 1)), row=1, col=col)
        fig.add_trace(go.Bar(x=dz.index, y=dz["volume"], marker_color="#78909c",
                             name="volume", showlegend=False), row=2, col=col)
        for ev in events:
            if ev.start.date() != day or ev.kind == "gap":
                continue
            att = attributions.get(ev.event_id, {})
            cands = att.get("candidates", [])
            top = cands[0]["catalyst"].headline if cands else "no catalyst matched"
            flow = att.get("flow", {})
            hover = (f"<b>{ev.event_id}</b> {ev.kind} {ev.magnitude_pct:+.2f}%<br>"
                     f"peak |z|={ev.peak_z:.1f}, vol z={ev.peak_vol_z:.1f}<br>"
                     f"confidence={att.get('confidence', 0):.2f}<br>"
                     f"idio share={att.get('idio', {}).get('idio_share', float('nan')):.2f}<br>"
                     f"flow: {flow.get('character', 'n/a')}<br>"
                     f"top catalyst: {top[:90]}")
            ymark = dz.loc[dz.index >= ev.start, "close"]
            fig.add_trace(go.Scatter(
                x=[ev.start], y=[ymark.iloc[0] if len(ymark) else dz["close"].iloc[-1]],
                mode="markers+text",
                marker=dict(size=13, symbol="triangle-up" if ev.direction == "up" else "triangle-down",
                            color=UP if ev.direction == "up" else DOWN,
                            line=dict(width=1, color="black")),
                text=[ev.event_id], textposition="top center", textfont=dict(size=8),
                hovertext=hover, hoverinfo="text", showlegend=False), row=1, col=col)
    title = "TSLA decoded — 2026-06-29 → 2026-07-02"
    if deliveries and deliveries.get("found"):
        title += f" | Q2 deliveries release: {deliveries['headline'][:70]}"
    fig.update_layout(
        title=title, height=750, template="plotly_white",
        margin=dict(l=40, r=20, t=80, b=30), hovermode="closest",
    )
    fig.update_xaxes(rangeslider_visible=False)
    fig.write_html(out, include_plotlyjs=True, full_html=True)
    log.info("dashboard written to %s", out)
