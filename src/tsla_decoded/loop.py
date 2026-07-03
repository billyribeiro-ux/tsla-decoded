"""Orchestrator: detect → decompose → attribute → score, escalating until converged."""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from . import catalysts as cat_mod
from . import data_loader as dl
from .config import Settings
from .decompose import MarketModel
from .detect import detect_events
from .features import seasonality_baseline
from .fmp_client import FMPClient
from .ml_attrib import event_flow_profile, feature_importance, order_flow_features, regime_map
from .scoring import confidence

log = logging.getLogger(__name__)


class Investigation:
    def __init__(self, settings: Settings, client: FMPClient):
        self.s = settings
        self.client = client
        self.state: dict = {"iterations": []}

    # -- data ---------------------------------------------------------------
    def load_core_data(self):
        s = self.s
        log.info("loading core market data")
        self.tsla_base_5m = dl.intraday(self.client, s.symbol, "5min", s.baseline_start, s.baseline_end)
        self.tsla_week_5m = dl.intraday(self.client, s.symbol, "5min", s.target_start, s.target_end)
        self.tsla_week_1m = dl.intraday(self.client, s.symbol, "1min", s.target_start, s.target_end)
        self.daily = dl.daily(self.client, s.symbol, s.daily_start, s.daily_end)
        self.bench_base = {b: dl.intraday(self.client, b, "5min", s.baseline_start, s.baseline_end)
                           for b in s.benchmarks}
        self.bench_week = {b: dl.intraday(self.client, b, "5min", s.target_start, s.target_end)
                           for b in s.benchmarks}
        assert not self.tsla_week_5m.empty, "no target-week intraday data"
        bars_per_day = self.tsla_week_5m[self.tsla_week_5m.session == "regular"].groupby(
            self.tsla_week_5m[self.tsla_week_5m.session == "regular"].index.date).size()
        log.info("target week RTH 5-min bars/day: %s", dict(bars_per_day))

        self.baseline_stats = seasonality_baseline(self.tsla_base_5m)
        self.baseline_stats_1m = None  # built lazily on P1

        self.market_model = MarketModel(s.symbol, s.benchmarks).fit(
            {s.symbol: self.tsla_base_5m, **self.bench_base})

    def load_catalysts_p0(self) -> list:
        s = self.s
        sources = {
            "press_release": dl.press_releases(self.client, s.symbol),
            "stock_news": dl.stock_news(self.client, s.symbol, s.news_start, s.news_end),
            "analyst": (dl.grades_news(self.client, s.symbol)
                        + dl.price_target_news(self.client, s.symbol)),
        }
        return cat_mod.collect(sources, s.symbol)

    def load_catalysts_p2(self) -> list:
        s = self.s
        sources = {
            "economic": dl.economic_calendar(self.client, s.news_start, s.news_end),
            "general_news": dl.general_news(self.client, s.news_start, s.news_end),
        }
        return cat_mod.collect(sources, s.symbol)

    def load_catalysts_p4(self) -> list:
        return cat_mod.collect({"insider": dl.insider_trades(self.client, self.s.symbol)}, self.s.symbol)

    # -- helpers -------------------------------------------------------------
    def _attribute(self, events, catalysts, pre_minutes: float):
        aligned = cat_mod.align(events, catalysts, pre_minutes=pre_minutes)
        out = {}
        for ev in events:
            idio = self.market_model.idio_share(
                {self.s.symbol: self.tsla_week_5m, **self.bench_week}, ev.start, ev.end)
            score = confidence(aligned[ev.event_id], idio, ev)
            out[ev.event_id] = {
                "candidates": aligned[ev.event_id],
                "idio": idio,
                **score,
            }
        return out

    def _unresolved(self, events, attributions) -> list:
        thr = self.s.loop["confidence_threshold"]
        major = self.s.detection["major_event_z"]
        return [ev for ev in events
                if (ev.peak_z >= major or ev.kind == "gap" or abs(ev.magnitude_pct) >= 2.0)
                and attributions[ev.event_id]["confidence"] < thr]

    # -- main loop -----------------------------------------------------------
    def run(self) -> dict:
        s = self.s
        self.load_core_data()

        events, z5 = detect_events(self.tsla_week_5m, self.baseline_stats, self.daily,
                                   s.detection, resolution="5min")
        self.z5 = z5
        catalysts = self.load_catalysts_p0()
        pre_minutes = 45.0
        attributions = self._attribute(events, catalysts, pre_minutes)
        self._log_iteration(0, "P0: 5-min detection, TSLA news/PR/analyst", events, attributions)

        loaded_p2 = loaded_p4 = False
        prev_conf = {e.event_id: attributions[e.event_id]["confidence"] for e in events}

        for it in range(1, s.loop["max_iters"] + 1):
            unresolved = self._unresolved(events, attributions)
            if not unresolved:
                log.info("converged after iteration %d", it - 1)
                break

            if it == 1:
                # P1: sharpen timing at 1-min around unresolved events
                if self.baseline_stats_1m is None and not self.tsla_week_1m.empty:
                    base_1m = dl.intraday(self.client, s.symbol, "1min",
                                          self._recent_baseline_start(), s.baseline_end)
                    self.baseline_stats_1m = seasonality_baseline(base_1m)
                for ev in unresolved:
                    if ev.kind == "gap" or self.baseline_stats_1m is None:
                        continue
                    fine, _ = detect_events(
                        self.tsla_week_1m, self.baseline_stats_1m, self.daily,
                        {**s.detection, "ret_z_threshold": s.detection["ret_z_threshold"] + 1},
                        resolution="1min",
                        restrict_to=(ev.start - pd.Timedelta(minutes=30),
                                     ev.end + pd.Timedelta(minutes=30)))
                    if fine:
                        onset = min(f.start for f in fine)
                        ev.notes.append(f"1-min onset refined to {onset:%H:%M}")
                        ev.start = min(ev.start, onset)
                stage = "P1: 1-min onset refinement"
            elif it == 2:
                catalysts += self.load_catalysts_p2()
                pre_minutes = 360.0
                loaded_p2 = True
                stage = "P2: widened windows + economic calendar + general news"
            elif it == 3:
                self._cross_asset_check(unresolved)
                stage = "P3: cross-asset (peers vs market) check"
            else:
                if not loaded_p4:
                    catalysts += self.load_catalysts_p4()
                    loaded_p4 = True
                stage = f"P4 (iter {it}): insider trades + carryover"

            attributions = self._attribute(events, catalysts, pre_minutes)
            self._log_iteration(it, stage, events, attributions)

            new_conf = {e.event_id: attributions[e.event_id]["confidence"] for e in events}
            delta = max(abs(new_conf[k] - prev_conf.get(k, 0)) for k in new_conf)
            prev_conf = new_conf
            if delta < s.loop["min_confidence_delta"] and it >= 2:
                log.info("early stop: no confidence improving (max delta %.3f)", delta)
                self.state["early_stop"] = f"iteration {it}: max confidence delta {delta:.3f}"
                break

        # ML layer (once, on final events)
        flow = order_flow_features(self.tsla_week_1m) if not self.tsla_week_1m.empty else pd.DataFrame()
        for ev in events:
            if not flow.empty and ev.kind != "gap":
                attributions[ev.event_id]["flow"] = event_flow_profile(flow, ev.start, ev.end)
        self.state["feature_importance"] = feature_importance(z5, self.bench_week, catalysts)
        self.state["regimes"] = regime_map(z5)
        self.state["deliveries_check"] = cat_mod.deliveries_check(catalysts)

        self.state.update({
            "events": events,
            "attributions": attributions,
            "catalysts": catalysts,
            "market_model": self.market_model.summary(),
            "capabilities": dict(self.client.capabilities),
            "unresolved": [e.event_id for e in self._unresolved(events, attributions)],
            "z5": z5,
        })
        return self.state

    def _recent_baseline_start(self) -> str:
        # 1-min baseline: last ~2 weeks only (payload-heavy)
        end = pd.Timestamp(self.s.baseline_end)
        return (end - pd.Timedelta(days=13)).date().isoformat()

    def _cross_asset_check(self, unresolved):
        s = self.s
        peers = {p: dl.intraday(self.client, p, "5min", s.target_start, s.target_end)
                 for p in s.peers}
        for ev in unresolved:
            moves = {}
            for p, df in peers.items():
                if df.empty:
                    continue
                reg = df[df.session == "regular"]
                win = reg.loc[ev.start - pd.Timedelta(minutes=5): ev.end]
                if len(win) >= 1:
                    moves[p] = float(np.log(win["close"].iloc[-1] / win["open"].iloc[0])) * 100
            if moves:
                same_dir = sum(1 for v in moves.values()
                               if (v < 0) == (ev.direction == "down") and abs(v) > 0.3)
                tag = ("sector-wide move (peers moved together)" if same_dir >= 2
                       else "TSLA-specific vs peers")
                ev.notes.append(f"cross-asset: {tag} {({k: round(v, 2) for k, v in moves.items()})}")

    def _log_iteration(self, it, stage, events, attributions):
        entry = {
            "iteration": it,
            "stage": stage,
            "events": len(events),
            "confidences": {e.event_id: attributions[e.event_id]["confidence"] for e in events},
            "http_requests_so_far": self.client.http_requests,
        }
        self.state["iterations"].append(entry)
        log.info("iter %d [%s] confidences=%s", it, stage, entry["confidences"])


def save_events_json(state: dict, path):
    payload = {
        "events": [e.to_dict() for e in state["events"]],
        "attributions": {
            eid: {
                "confidence": a["confidence"],
                "components": a["components"],
                "idio": {k: (None if isinstance(v, float) and np.isnan(v) else round(v, 4))
                         for k, v in a["idio"].items()},
                "flow": a.get("flow", {}),
                "candidates": [
                    {"score": round(c["score"], 4),
                     "delta_minutes": c["delta_minutes"],
                     **c["catalyst"].to_dict()}
                    for c in a["candidates"]
                ],
            }
            for eid, a in state["attributions"].items()
        },
        "iterations": state["iterations"],
        "unresolved": state["unresolved"],
        "capabilities": state["capabilities"],
        "market_model": state["market_model"],
        "feature_importance": state["feature_importance"],
        "deliveries_check": state["deliveries_check"],
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
