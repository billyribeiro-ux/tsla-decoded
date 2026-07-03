"""Catalyst normalization and event↔catalyst alignment scoring."""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

import pandas as pd

log = logging.getLogger(__name__)

ET = "America/New_York"

SOURCE_WEIGHTS = {
    "press_release": 1.00,
    "economic": 0.90,
    "analyst": 0.80,
    "stock_news": 0.60,
    "general_news": 0.40,
    "insider": 0.30,
}

# hypothesis lexicon: term -> (weight, direction) direction: +1 bullish, -1 bearish, 0 neutral
LEXICON = {
    "deliveries": (1.0, 0), "delivery": (1.0, 0), "deliver": (0.8, 0),
    "production": (0.8, 0), "q2": (0.6, 0), "quarterly": (0.5, 0), "vehicle": (0.4, 0),
    "record": (0.5, 1), "beat": (0.8, 1), "crush": (0.8, 1), "surge": (0.5, 1),
    "miss": (0.8, -1), "fall short": (0.8, -1), "decline": (0.5, -1), "drop": (0.4, -1),
    "recall": (0.9, -1), "nhtsa": (0.8, -1), "investigation": (0.7, -1),
    "probe": (0.6, -1), "lawsuit": (0.6, -1), "crash": (0.6, -1), "death": (0.6, -1),
    "downgrade": (1.0, -1), "upgrade": (1.0, 1), "price target": (0.9, 0),
    "overweight": (0.6, 1), "underweight": (0.6, -1), "sell rating": (0.8, -1),
    "musk": (0.5, 0), "robotaxi": (0.7, 0), "fsd": (0.6, 0), "full self": (0.6, 0),
    "autopilot": (0.5, 0), "optimus": (0.5, 0), "energy storage": (0.6, 0),
    "guidance": (0.7, 0), "margin": (0.6, 0), "demand": (0.5, 0),
    "tariff": (0.7, -1), "subsidy": (0.6, 0), "tax credit": (0.7, 0), "ev credit": (0.7, 0),
    "profit-taking": (0.6, -1), "sell the news": (0.8, -1), "valuation": (0.4, -1),
    "jobs report": (0.8, 0), "payrolls": (0.8, 0), "nonfarm": (0.8, 0),
    "unemployment": (0.7, 0), "fed": (0.6, 0), "cpi": (0.7, 0), "inflation": (0.6, 0),
}

HIGH_IMPACT_ECON = re.compile(
    r"non.?farm|payroll|unemployment|cpi|pce|fomc|fed funds|ism|gdp|jobless",
    re.IGNORECASE,
)


@dataclass
class Catalyst:
    ts: pd.Timestamp | None      # tz-aware ET; None if source gave no usable timestamp
    source_type: str             # key of SOURCE_WEIGHTS
    headline: str
    text: str = ""
    url: str = ""
    timing_precise: bool = True  # False -> lower timing confidence, wider windows
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ts": self.ts.isoformat() if self.ts is not None else None,
            "source_type": self.source_type,
            "headline": self.headline,
            "url": self.url,
            "timing_precise": self.timing_precise,
        }


def _parse_ts(value) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        ts = pd.to_datetime(value)
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize(ET)   # FMP news timestamps are US/Eastern
    else:
        ts = ts.tz_convert(ET)
    return ts


def normalize(raw: dict, source_type: str) -> Catalyst:
    ts = _parse_ts(raw.get("publishedDate") or raw.get("date") or raw.get("filingDate"))
    headline = raw.get("title") or raw.get("newsTitle") or raw.get("event") or ""
    text = raw.get("text") or raw.get("content") or ""
    precise = ts is not None and (ts.hour, ts.minute) != (0, 0)
    if source_type == "analyst" and not headline:
        headline = (
            f"{raw.get('gradingCompany') or raw.get('analystCompany') or 'Analyst'}: "
            f"{raw.get('previousGrade') or ''} -> {raw.get('newGrade') or ''} "
            f"{('PT ' + str(raw.get('priceTarget'))) if raw.get('priceTarget') else ''}"
        ).strip()
    if source_type == "economic":
        headline = f"{raw.get('event', '')} ({raw.get('country', '')})"
        text = (
            f"actual={raw.get('actual')} estimate={raw.get('estimate')} "
            f"previous={raw.get('previous')} impact={raw.get('impact')}"
        )
        precise = ts is not None
    if source_type == "insider":
        headline = (
            f"Insider {raw.get('transactionType', '')}: "
            f"{raw.get('reportingName', '')} {raw.get('securitiesTransacted', '')} shares"
        )
        precise = False  # filings lag the trade
    return Catalyst(ts=ts, source_type=source_type, headline=headline,
                    text=text, url=raw.get("url") or raw.get("link") or "", timing_precise=precise,
                    extra=raw)


def collect(sources: dict[str, list[dict]], symbol: str = "TSLA") -> list[Catalyst]:
    """sources: {source_type: raw_rows}. Economic rows filtered to high-impact US."""
    out: list[Catalyst] = []
    for stype, rows in sources.items():
        for raw in rows or []:
            if stype == "economic":
                if (raw.get("country") or "").upper() not in ("US", "USA", "UNITED STATES"):
                    continue
                impact = (raw.get("impact") or "").lower()
                if impact not in ("high", "medium") and not HIGH_IMPACT_ECON.search(raw.get("event") or ""):
                    continue
            c = normalize(raw, stype)
            if c.headline:
                out.append(c)
    log.info("collected %d catalysts across %d sources", len(out), len(sources))
    return out


def relevance(cat: Catalyst, direction: str) -> float:
    """Lexicon relevance in [0,1] with direction-consistency adjustment."""
    blob = f"{cat.headline} {cat.text[:1500]}".lower()
    score, dir_score = 0.0, 0.0
    for term, (w, d) in LEXICON.items():
        if term in blob:
            score += w
            dir_score += w * d
    if score == 0:
        return 0.0
    base = min(1.0, score / 4.0)
    want = 1 if direction == "up" else -1
    if dir_score != 0:
        consistency = 1.15 if (dir_score > 0) == (want > 0) else 0.75
    else:
        consistency = 1.0
    return min(1.0, base * consistency)


def effective_lead_minutes(cat_ts: pd.Timestamp, ev_start: pd.Timestamp) -> float:
    """Minutes the catalyst preceded the event, clock starting at the session open.

    A pre-market catalyst cannot move the tape before 09:30, so its reaction lag
    is measured from the open, not from publication.
    """
    session_open = ev_start.normalize() + pd.Timedelta(hours=9, minutes=30)
    anchor = max(cat_ts, session_open) if cat_ts < session_open <= ev_start else cat_ts
    return (ev_start - anchor).total_seconds() / 60


def time_score(cat: Catalyst, ev_start: pd.Timestamp, ev_end: pd.Timestamp,
               pre_minutes: float, post_minutes: float = 10.0) -> float:
    """1.0 for catalyst just before the move, decaying exp(-dt/15min); 0 outside window."""
    if cat.ts is None:
        return 0.0
    lo = ev_start - pd.Timedelta(minutes=pre_minutes)
    hi = ev_end + pd.Timedelta(minutes=post_minutes)
    if not (lo <= cat.ts <= hi):
        return 0.0
    if cat.ts <= ev_start:
        dt_min = effective_lead_minutes(cat.ts, ev_start)
        s = math.exp(-dt_min / max(pre_minutes / 3, 15.0))
    else:
        # published after the move started — reaction coverage, weaker causal evidence
        s = 0.45
    if not cat.timing_precise:
        s *= 0.6
    return s


def align(events, catalysts: list[Catalyst], pre_minutes: float = 45.0,
          gap_lookback_hours: float = 18.0) -> dict[str, list[dict]]:
    """Score every catalyst against every event; keep top 5 per event."""
    result: dict[str, list[dict]] = {}
    for ev in events:
        pre = gap_lookback_hours * 60 if ev.kind in ("gap", "day") else pre_minutes
        scored = []
        for cat in catalysts:
            t = time_score(cat, ev.start, ev.end, pre_minutes=pre)
            if t == 0:
                continue
            r = relevance(cat, ev.direction)
            if r == 0:
                continue
            s = SOURCE_WEIGHTS[cat.source_type] * r * t
            scored.append({
                "catalyst": cat, "score": s, "relevance": r, "time_score": t,
                "delta_minutes": None if cat.ts is None
                else round(effective_lead_minutes(cat.ts, ev.start), 1),
            })
        scored.sort(key=lambda x: -x["score"])
        result[ev.event_id] = scored[:5]
    return result


# -- Q2 deliveries hypothesis -------------------------------------------------

DELIVERY_PR = re.compile(r"(second quarter|q2).{0,40}(production|deliveries)", re.IGNORECASE)
NUMBER = re.compile(r"([\d,]{5,})\s*(?:vehicles|deliveries|cars)?", re.IGNORECASE)


def deliveries_check(catalysts: list[Catalyst]) -> dict | None:
    """Find the Q2 production/deliveries release and extract headline figures."""
    hits = [c for c in catalysts
            if c.source_type in ("press_release", "stock_news")
            and DELIVERY_PR.search(c.headline)]
    if not hits:
        return None
    hits.sort(key=lambda c: (c.source_type != "press_release",
                             c.ts or pd.Timestamp.max.tz_localize(ET)))
    pr = hits[0]
    figures = {}
    text = f"{pr.headline}\n{pr.text[:3000]}"
    m_del = re.search(r"deliver(?:ed|ies)[^\d]{0,40}([\d,]{5,})", text, re.IGNORECASE)
    m_prod = re.search(r"produc(?:ed|tion)[^\d]{0,40}([\d,]{5,})", text, re.IGNORECASE)
    if m_del:
        figures["deliveries"] = int(m_del.group(1).replace(",", ""))
    if m_prod:
        figures["production"] = int(m_prod.group(1).replace(",", ""))
    # prefer an exact (comma-formatted) delivery figure from any coverage over rounded PR text
    for c in catalysts:
        m = re.search(r"([\d]{3},[\d]{3})\s+(?:vehicle\s+)?deliver",
                      f"{c.headline} {c.text[:1000]}", re.IGNORECASE)
        if m:
            figures["deliveries_exact"] = int(m.group(1).replace(",", ""))
            break
    return {
        "found": True,
        "headline": pr.headline,
        "ts": pr.ts.isoformat() if pr.ts is not None else None,
        "timing_precise": pr.timing_precise,
        "figures": figures,
        "url": pr.url,
        "reaction_headlines": [c.headline for c in catalysts
                               if "deliver" in c.headline.lower()][:8],
    }
