"""Event detection: z-score triggers, PELT changepoints, VWAP drift, overnight gaps."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import ruptures as rpt

from .features import log_returns, seasonal_zscores

log = logging.getLogger(__name__)


@dataclass
class Event:
    event_id: str
    start: pd.Timestamp
    end: pd.Timestamp
    direction: str            # "up" | "down"
    magnitude_pct: float      # cumulative return over the window, %
    peak_z: float
    peak_vol_z: float
    kind: str                 # "spike" | "drift" | "gap"
    resolution: str           # "5min" | "1min" | "daily"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "direction": self.direction,
            "magnitude_pct": round(self.magnitude_pct, 3),
            "peak_z": round(self.peak_z, 2),
            "peak_vol_z": round(self.peak_vol_z, 2),
            "kind": self.kind,
            "resolution": self.resolution,
            "notes": self.notes,
        }


def _merge_triggers(z: pd.DataFrame, trigger: pd.Series, gap_minutes: int) -> list[tuple]:
    """Collapse consecutive triggered bars (within gap_minutes) into (start, end) windows."""
    idx = z.index[trigger]
    if len(idx) == 0:
        return []
    windows, w_start, w_prev = [], idx[0], idx[0]
    for ts in idx[1:]:
        if (ts - w_prev).total_seconds() / 60 <= gap_minutes and ts.date() == w_prev.date():
            w_prev = ts
        else:
            windows.append((w_start, w_prev))
            w_start = w_prev = ts
    windows.append((w_start, w_prev))
    return windows


def _pelt_changepoints(series: pd.Series, min_size: int = 6) -> list[pd.Timestamp]:
    vals = series.dropna()
    if len(vals) < min_size * 3:
        return []
    algo = rpt.Pelt(model="rbf", min_size=min_size).fit(vals.to_numpy().reshape(-1, 1))
    # BIC-flavored penalty; rbf model is scale-free so a log(n) penalty works well
    pen = 2.0 * np.log(len(vals))
    breaks = algo.predict(pen=pen)
    return [vals.index[i - 1] for i in breaks[:-1]]


def detect_events(
    target_df: pd.DataFrame,
    baseline_stats: pd.DataFrame,
    daily_df: pd.DataFrame,
    cfg: dict,
    resolution: str = "5min",
    restrict_to: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> tuple[list[Event], pd.DataFrame]:
    """Detect abnormal events in the target week. Returns (events, scored bar frame)."""
    z = seasonal_zscores(target_df, baseline_stats)
    if restrict_to is not None:
        z = z.loc[restrict_to[0]: restrict_to[1]]

    ret_thr = cfg["ret_z_threshold"]
    vol_thr = cfg["vol_z_threshold"]

    trigger = (z["z_ret"] >= ret_thr) | (
        (z["z_vol"] >= vol_thr) & (z["z_ret"] >= cfg["vol_z_ret_min"])
    )

    # changepoints corroborate/extend z-score windows
    cps: set[pd.Timestamp] = set()
    for day, day_z in z.groupby(z.index.date):
        cps.update(_pelt_changepoints(day_z["ret"]))
        rv = day_z["ret"].rolling(6).std()
        cps.update(_pelt_changepoints(rv, min_size=6))

    events: list[Event] = []
    for i, (w_start, w_end) in enumerate(_merge_triggers(z, trigger, cfg["merge_gap_minutes"])):
        win = z.loc[w_start:w_end]
        cum_ret = float(win["ret"].sum()) * 100
        direction = "up" if cum_ret >= 0 else "down"
        notes = []
        near_cp = [c for c in cps if abs((c - w_start).total_seconds()) <= 1800
                   or abs((c - w_end).total_seconds()) <= 1800]
        if near_cp:
            notes.append(f"corroborated by {len(near_cp)} changepoint(s)")
        events.append(Event(
            event_id=f"E{w_start:%m%d-%H%M}",
            start=w_start, end=w_end, direction=direction,
            magnitude_pct=cum_ret,
            peak_z=float(win["z_ret"].max()),
            peak_vol_z=float(win["z_vol"].max()),
            kind="spike", resolution=resolution, notes=notes,
        ))

    # VWAP drift: sustained deviation without a single-bar spike (grinding moves)
    daily_sigma = float(log_returns(daily_df["close"]).std())
    for day, day_z in z.groupby(z.index.date):
        dev = day_z["vwap_dev"]
        max_dev = dev.abs().max()
        if pd.isna(max_dev) or max_dev < cfg["vwap_dev_sigma"] * daily_sigma:
            continue
        peak_ts = dev.abs().idxmax()
        covered = any(e.start.date() == day and e.start <= peak_ts <= e.end for e in events)
        if covered:
            continue
        drift = dev.loc[dev.abs() >= max_dev * 0.5]
        cum_ret = float(day_z.loc[drift.index[0]: drift.index[-1], "ret"].sum()) * 100
        events.append(Event(
            event_id=f"D{drift.index[0]:%m%d-%H%M}",
            start=drift.index[0], end=drift.index[-1],
            direction="up" if dev.loc[peak_ts] > 0 else "down",
            magnitude_pct=cum_ret,
            peak_z=float(day_z.loc[drift.index[0]: drift.index[-1], "z_ret"].max()),
            peak_vol_z=float(day_z.loc[drift.index[0]: drift.index[-1], "z_vol"].max()),
            kind="drift", resolution=resolution,
            notes=[f"anchored-VWAP deviation {dev.loc[peak_ts]*100:.2f}% (>{cfg['vwap_dev_sigma']}σ daily)"],
        ))

    # overnight gaps at daily level
    if restrict_to is None:
        d = daily_df.copy()
        d["gap"] = np.log(d["open"] / d["close"].shift())
        gap_sigma = float(d["gap"].std())
        target_days = {ts.date() for ts in z.index}
        for ts, row in d.iterrows():
            if ts.date() not in target_days or pd.isna(row["gap"]):
                continue
            gz = abs(row["gap"]) / max(gap_sigma, 1e-9)
            if gz >= cfg["gap_z_threshold"]:
                open_ts = pd.Timestamp(f"{ts.date()} 09:30").tz_localize("America/New_York")
                events.append(Event(
                    event_id=f"G{ts:%m%d}",
                    start=open_ts, end=open_ts,
                    direction="up" if row["gap"] > 0 else "down",
                    magnitude_pct=float(row["gap"]) * 100,
                    peak_z=float(gz), peak_vol_z=np.nan,
                    kind="gap", resolution="daily",
                    notes=["overnight gap vs prior close — catalyst window spans after-hours/pre-market"],
                ))

    events.sort(key=lambda e: e.start)
    log.info("detected %d events at %s", len(events), resolution)
    return events, z
