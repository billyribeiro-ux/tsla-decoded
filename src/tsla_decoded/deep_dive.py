"""Per-session forensic deep dive: 1-minute phase segmentation and narration.

For each target-week day: PELT phase boundaries on 1-min returns, per-phase
return/volume/flow/VWAP/market-implied stats, extreme minutes, news timeline,
and volume-at-price — rendered as a markdown chapter plus a dense 1-min chart.
"""
from __future__ import annotations

import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import ruptures as rpt
from tabulate import tabulate

from . import data_loader as dl
from .catalysts import collect, relevance
from .decompose import MarketModel
from .features import anchored_vwap, log_returns, seasonality_baseline, seasonal_zscores
from .fmp_client import FMPClient
from .ml_attrib import order_flow_features
from .plots import DOWN, UP

log = logging.getLogger(__name__)

ET = "America/New_York"


# --------------------------------------------------------------------------
# phase segmentation
# --------------------------------------------------------------------------

def segment_day(day_1m: pd.DataFrame, min_size: int = 20, max_phases: int = 8) -> list[tuple]:
    """PELT changepoints on the 1-min log-price path -> [(start_ts, end_ts), ...].

    Segmenting price levels (not returns) captures trend phases: returns are
    noise-like minute to minute, while the price path shows the regime steps.
    """
    price = np.log(day_1m["close"].astype(float)).dropna()
    if len(price) < min_size * 2 or price.std() < 1e-9:
        return [(day_1m.index[0], day_1m.index[-1])]
    sig = ((price - price.mean()) / price.std()).to_numpy().reshape(-1, 1)
    algo = rpt.Pelt(model="rbf", min_size=min_size).fit(sig)
    pen = 5.0
    breaks = algo.predict(pen=pen)
    while len(breaks) > max_phases:
        pen *= 1.5
        breaks = algo.predict(pen=pen)
    bounds = [price.index[0]] + [price.index[i - 1] for i in breaks[:-1]] + [price.index[-1]]
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]


def phase_stats(day_1m: pd.DataFrame, flow: pd.DataFrame, vwap: pd.Series,
                market_model: MarketModel, week_frames: dict,
                start: pd.Timestamp, end: pd.Timestamp) -> dict:
    win = day_1m.loc[start:end]
    fwin = flow.loc[start:end]
    ret = float(np.log(win["close"].iloc[-1] / win["close"].iloc[0])) * 100
    vol = int(win["volume"].sum())
    imb = float(fwin["signed_volume"].sum() / max(vol, 1)) if not fwin.empty else np.nan
    above = float((win["close"] > vwap.loc[start:end]).mean())
    idio = market_model.idio_share(week_frames, start, end)
    hi_ts, lo_ts = win["high"].idxmax(), win["low"].idxmin()
    return {
        "start": start, "end": end, "minutes": len(win),
        "ret_pct": ret, "volume": vol, "imbalance": imb,
        "share_above_vwap": above,
        "idio_share": idio.get("idio_share"),
        "market_pct": idio.get("market_pct"),
        "hi": float(win["high"].max()), "hi_ts": hi_ts,
        "lo": float(win["low"].min()), "lo_ts": lo_ts,
    }


def phase_label(p: dict) -> str:
    r, imb = p["ret_pct"], p["imbalance"]
    if r >= 1.0:
        drive = "upside drive"
    elif r >= 0.35:
        drive = "grind higher"
    elif r <= -1.0:
        drive = "liquidation wave"
    elif r <= -0.35:
        drive = "controlled selling"
    else:
        drive = "consolidation"
    if not np.isnan(imb):
        if imb <= -0.30:
            drive += ", one-sided sell flow"
        elif imb >= 0.30:
            drive += ", one-sided buy flow"
    return drive


def _fmt_share(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{v:.0%}"


# --------------------------------------------------------------------------
# per-day chapter
# --------------------------------------------------------------------------

def day_chapter(day, day_1m: pd.DataFrame, z1: pd.DataFrame, flow: pd.DataFrame,
                daily: pd.DataFrame, market_model: MarketModel, week_frames: dict,
                catalysts: list, vol20_med: float) -> tuple[list[str], list[dict]]:
    lines: list[str] = []
    add = lines.append
    vwap = anchored_vwap(day_1m)
    o, c = float(day_1m["open"].iloc[0]), float(day_1m["close"].iloc[-1])
    hi, lo = float(day_1m["high"].max()), float(day_1m["low"].min())
    hi_ts, lo_ts = day_1m["high"].idxmax(), day_1m["low"].idxmin()
    vol = int(day_1m["volume"].sum())
    eod_prev = daily["close"].shift().loc[daily.index.date == day]
    prev_close = float(eod_prev.iloc[0]) if not eod_prev.empty else np.nan
    gap = (o / prev_close - 1) * 100 if prev_close == prev_close else np.nan
    day_ret = (c / prev_close - 1) * 100 if prev_close == prev_close else np.nan
    oc_ret = (c / o - 1) * 100
    crosses = int(((day_1m["close"] > vwap) != (day_1m["close"] > vwap).shift()).sum())
    above_share = float((day_1m["close"] > vwap).mean())
    clv_day = (c - lo) / max(hi - lo, 1e-9)

    add(f"\n---\n\n## {day:%A, %B %d, %Y} — {day_ret:+.2f}% close-to-close\n")
    add(tabulate([[
        f"{o:.2f}", f"{hi:.2f} @ {hi_ts:%H:%M}", f"{lo:.2f} @ {lo_ts:%H:%M}", f"{c:.2f}",
        f"{gap:+.2f}%", f"{oc_ret:+.2f}%", f"{vol/1e6:.1f}M ({vol/max(vol20_med,1):.1f}× 20d median)",
        f"{clv_day:.0%}",
    ]], headers=["open", "high", "low", "close", "overnight gap", "open→close",
                 "volume", "close location in range"], tablefmt="github"))
    add("")
    add(f"VWAP: price spent **{above_share:.0%}** of the session above the anchored VWAP, "
        f"crossing it {crosses} time(s) — "
        + ("buyers controlled the auction." if above_share > 0.65 else
           "sellers controlled the auction." if above_share < 0.35 else
           "a genuine two-sided fight.") + "\n")

    # phases
    phases = []
    add("### Session phases (1-minute changepoint segmentation)\n")
    rows = []
    for i, (s, e) in enumerate(segment_day(day_1m), 1):
        p = phase_stats(day_1m, flow, vwap, market_model, week_frames, s, e)
        p["label"] = phase_label(p)
        p["n"] = i
        phases.append(p)
        rows.append([
            f"P{i}", f"{s:%H:%M}–{e:%H:%M}", p["label"], f"{p['ret_pct']:+.2f}%",
            f"{p['volume']/1e6:.1f}M",
            f"{p['imbalance']:+.2f}" if not np.isnan(p["imbalance"]) else "n/a",
            f"{p['share_above_vwap']:.0%}", _fmt_share(p["idio_share"]),
        ])
    add(tabulate(rows, headers=["phase", "window (ET)", "character", "return", "volume",
                                "flow imb", "above VWAP", "idio"], tablefmt="github"))
    add("")

    # narrative
    add("### Play-by-play\n")
    for p in phases:
        bits = [f"**{p['start']:%H:%M}–{p['end']:%H:%M} — {p['label']}**: "
                f"{p['ret_pct']:+.2f}% in {p['minutes']} min on {p['volume']/1e6:.1f}M shares"]
        if not np.isnan(p["imbalance"]):
            side = ("sellers hitting bids" if p["imbalance"] < -0.15
                    else "buyers lifting offers" if p["imbalance"] > 0.15 else "balanced tape")
            bits.append(f"flow imbalance {p['imbalance']:+.2f} ({side})")
        if p["idio_share"] is not None and p["idio_share"] == p["idio_share"]:
            bits.append(f"{p['idio_share']:.0%} TSLA-specific vs SPY/QQQ "
                        f"(market-implied {p['market_pct']:+.2f}%)")
        bits.append(f"range {p['lo']:.2f} ({p['lo_ts']:%H:%M}) → {p['hi']:.2f} ({p['hi_ts']:%H:%M})")
        add("- " + "; ".join(bits) + ".")
    add("")

    # extreme minutes
    add("### The minutes that mattered\n")
    dz = z1[z1.index.date == day]
    ret1 = dz["ret"] * 100
    extremes = pd.concat([ret1.abs().nlargest(5), dz["z_vol"].nlargest(3)]).index.unique()
    rows = []
    for ts in sorted(extremes):
        f_row = flow.loc[ts] if ts in flow.index else None
        rows.append([
            f"{ts:%H:%M}", f"{ret1.loc[ts]:+.2f}%", f"{dz.loc[ts, 'z_ret']:.1f}",
            f"{int(dz.loc[ts, 'volume'])/1e3:.0f}k", f"{dz.loc[ts, 'z_vol']:.1f}",
            f"{f_row['clv']:+.2f}" if f_row is not None else "n/a",
            f"{dz.loc[ts, 'close']:.2f}",
        ])
    add(tabulate(rows, headers=["minute", "return", "|ret| z", "volume", "vol z",
                                "CLV", "close"], tablefmt="github"))
    add("\nCLV = close-location value within the bar (−1 = closed on the low, +1 = on the high).\n")

    # volume at price
    add("### Where the volume traded\n")
    buckets = (day_1m["close"] / 2).round() * 2
    vap = day_1m.groupby(buckets)["volume"].sum().nlargest(3)
    add("Top price shelves: " + "; ".join(
        f"**${lvl:.0f}** ({v/1e6:.1f}M)" for lvl, v in vap.items()) + ".\n")

    # news timeline
    add("### News timeline (session-relevant TSLA catalysts)\n")
    day_start = pd.Timestamp(f"{day} 04:00").tz_localize(ET)
    day_end = pd.Timestamp(f"{day} 16:30").tz_localize(ET)
    todays = [cat for cat in catalysts
              if cat.ts is not None and day_start <= cat.ts <= day_end
              and max(relevance(cat, "down"), relevance(cat, "up")) >= 0.25
              and cat.source_type in ("press_release", "analyst", "stock_news", "economic")]
    todays.sort(key=lambda cat: cat.ts)
    if todays:
        rows = [[f"{cat.ts:%H:%M}", cat.source_type, cat.headline[:100]] for cat in todays[:14]]
        add(tabulate(rows, headers=["ET", "source", "headline"], tablefmt="github"))
    else:
        add("_No high-relevance TSLA catalysts timestamped inside this session._")
    add("")
    return lines, phases


def day_chart(day, day_1m: pd.DataFrame, flow: pd.DataFrame, phases: list[dict],
              catalysts: list, out) -> None:
    vwap = anchored_vwap(day_1m)
    fig, (ax, axv, axf) = plt.subplots(
        3, 1, figsize=(14, 9.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1]})
    for i, p in enumerate(phases):
        ax.axvspan(p["start"], p["end"],
                   color=(UP if p["ret_pct"] > 0.1 else DOWN if p["ret_pct"] < -0.1
                          else "#90a4ae"), alpha=0.07)
        ymid = day_1m["close"].loc[p["start"]:p["end"]].max()
        ax.annotate(f"P{p['n']} {p['ret_pct']:+.1f}%",
                    xy=(p["start"], ymid), xytext=(2, 6), textcoords="offset points",
                    fontsize=7.5, color="#37474f")
    ax.plot(day_1m.index, day_1m["close"], color="#1565c0", lw=0.9, label="close (1-min)")
    ax.plot(vwap.index, vwap, color="#6a1b9a", lw=1.1, ls="--", label="anchored VWAP")
    hi_ts, lo_ts = day_1m["high"].idxmax(), day_1m["low"].idxmin()
    ax.scatter([hi_ts, lo_ts], [day_1m['high'].max(), day_1m['low'].min()],
               color=[UP, DOWN], zorder=5, s=30)
    ax.annotate(f"HOD {day_1m['high'].max():.2f}\n{hi_ts:%H:%M}", xy=(hi_ts, day_1m['high'].max()),
                xytext=(4, 8), textcoords="offset points", fontsize=7.5, color=UP)
    ax.annotate(f"LOD {day_1m['low'].min():.2f}\n{lo_ts:%H:%M}", xy=(lo_ts, day_1m['low'].min()),
                xytext=(4, -18), textcoords="offset points", fontsize=7.5, color=DOWN)
    day_start = day_1m.index[0].normalize() + pd.Timedelta(hours=9, minutes=30)
    day_close = day_1m.index[0].normalize() + pd.Timedelta(hours=16)
    for cat in catalysts:
        if cat.ts is None or not (day_start - pd.Timedelta(hours=5) <= cat.ts <= day_close):
            continue
        if cat.source_type == "press_release" or (
                cat.source_type == "analyst"
                and max(relevance(cat, "down"), relevance(cat, "up")) >= 0.4):
            xpos = max(cat.ts, day_start)
            ax.axvline(xpos, color="#f9a825", ls=":", lw=1.2)
            ax.annotate(cat.headline[:38], xy=(xpos, day_1m["close"].min()),
                        rotation=90, fontsize=6.5, color="#8d6e63",
                        xytext=(3, 4), textcoords="offset points", va="bottom")
    ax.set_title(f"TSLA {day} — 1-minute forensics: phases, VWAP, catalysts")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.25)

    ret1 = log_returns(day_1m["close"]).fillna(0)
    axv.bar(day_1m.index, day_1m["volume"] / 1e3, width=0.0007,
            color=np.where(ret1 >= 0, UP, DOWN), alpha=0.8)
    axv.set_ylabel("Vol (k)")
    axv.grid(alpha=0.25)

    fday = flow[flow.index.date == day]
    cum_signed = fday["signed_volume"].cumsum() / 1e6
    axf.plot(cum_signed.index, cum_signed, color="#37474f", lw=1.1)
    axf.axhline(0, color="#bdbdbd", lw=0.8)
    axf.fill_between(cum_signed.index, 0, cum_signed,
                     where=cum_signed >= 0, color=UP, alpha=0.25)
    axf.fill_between(cum_signed.index, 0, cum_signed,
                     where=cum_signed < 0, color=DOWN, alpha=0.25)
    axf.set_ylabel("Cum signed vol (M)")
    axf.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=day_1m.index.tz))
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------
# entrypoint
# --------------------------------------------------------------------------

def run_deep_dive(client: FMPClient, settings) -> dict:
    s = settings
    log.info("deep dive: loading 1-min data (cache-backed)")
    tsla_1m = dl.intraday(client, s.symbol, "1min", s.target_start, s.target_end)
    tsla_base_5m = dl.intraday(client, s.symbol, "5min", s.baseline_start, s.baseline_end)
    tsla_week_5m = dl.intraday(client, s.symbol, "5min", s.target_start, s.target_end)
    bench_base = {b: dl.intraday(client, b, "5min", s.baseline_start, s.baseline_end)
                  for b in s.benchmarks}
    bench_week = {b: dl.intraday(client, b, "5min", s.target_start, s.target_end)
                  for b in s.benchmarks}
    daily = dl.daily(client, s.symbol, s.daily_start, s.daily_end)
    base_1m_start = (pd.Timestamp(s.baseline_end) - pd.Timedelta(days=13)).date().isoformat()
    base_1m = dl.intraday(client, s.symbol, "1min", base_1m_start, s.baseline_end)

    market_model = MarketModel(s.symbol, s.benchmarks).fit({s.symbol: tsla_base_5m, **bench_base})
    week_frames = {s.symbol: tsla_week_5m, **bench_week}
    z1 = seasonal_zscores(tsla_1m, seasonality_baseline(base_1m))
    flow = order_flow_features(tsla_1m)
    vol20_med = float(daily["volume"].tail(20).median())

    sources = {
        "press_release": dl.press_releases(client, s.symbol),
        "stock_news": dl.stock_news(client, s.symbol, s.news_start, s.news_end),
        "analyst": dl.grades_news(client, s.symbol) + dl.price_target_news(client, s.symbol),
        "economic": dl.economic_calendar(client, s.news_start, s.news_end),
    }
    catalysts = collect(sources, s.symbol)

    lines = [f"# TSLA session-by-session forensics: {s.target_start} → {s.target_end}\n",
             "Each session decoded at 1-minute resolution: changepoint phases, order-flow "
             "imbalance, VWAP control, market-implied vs TSLA-specific attribution per phase, "
             "the individual minutes that carried the day, volume-at-price shelves, and the "
             "session's news timeline.\n",
             "_Note: FMP `historical-chart` supplies regular-session bars only (09:30–16:00 ET); "
             "overnight/pre-market catalysts are attributed to the opening minutes they were "
             "absorbed in._\n"]
    out_dir = s.output_dir
    (out_dir / "charts").mkdir(parents=True, exist_ok=True)

    reg = tsla_1m[tsla_1m["session"] == "regular"]
    for day in sorted({ts.date() for ts in reg.index}):
        day_1m = reg[reg.index.date == day]
        chapter, phases = day_chapter(day, day_1m, z1, flow, daily, market_model,
                                      week_frames, catalysts, vol20_med)
        lines.extend(chapter)
        day_chart(day, day_1m, flow, phases, catalysts,
                  out_dir / "charts" / f"deep_1min_{day}.png")

    lines.append("\n---\n\n*Flow imbalance = tick-rule signed volume / total volume over the "
                 "window; idio = share of the phase's move not explained by the SPY/QQQ beta "
                 "model. All timestamps ET. Not investment advice.*")
    out_path = out_dir / "deep_dive.md"
    out_path.write_text("\n".join(lines))
    log.info("deep dive written to %s", out_path)
    return {"report": out_path}
