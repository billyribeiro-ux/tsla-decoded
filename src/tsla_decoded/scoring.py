"""Evidence-weighted per-event confidence scoring."""
from __future__ import annotations

import re

import numpy as np

WEIGHTS = {
    "alignment": 0.45,
    "idio_consistency": 0.20,
    "timing_precision": 0.20,
    "uniqueness": 0.15,
}

_STOP = {"the", "and", "for", "with", "its", "has", "are", "was", "will", "this", "that"}


def _story_tokens(headline: str) -> set[str]:
    # crude 6-char stems so "delivery"/"deliveries" and "quarter"/"quarterly" match
    return {w[:6] for w in re.findall(r"[a-z0-9]+", headline.lower())
            if len(w) > 2 and w not in _STOP}


def same_story(h1: str, h2: str) -> bool:
    t1, t2 = _story_tokens(h1), _story_tokens(h2)
    if not t1 or not t2:
        return False
    return len(t1 & t2) / min(len(t1), len(t2)) >= 0.5


def confidence(candidates: list[dict], idio: dict, event) -> dict:
    """Combine alignment, decomposition consistency, timing and uniqueness into [0,1].

    candidates: scored catalyst dicts from catalysts.align (sorted desc).
    idio: output of MarketModel.idio_share for the event window.
    """
    if not candidates:
        best_alignment = 0.0
        timing = 0.0
        uniqueness = 0.0
    else:
        best = candidates[0]
        cat = best["catalyst"]
        # duplicates/rewrites of the same story corroborate the top catalyst;
        # only a genuinely different story competes with it
        corroborators = [c for c in candidates[1:]
                         if same_story(cat.headline, c["catalyst"].headline)]
        competitors = [c for c in candidates[1:]
                       if not same_story(cat.headline, c["catalyst"].headline)]
        best_alignment = min(1.0, best["score"] + 0.05 * len(corroborators))
        if cat.ts is not None and best["delta_minutes"] is not None:
            dt = best["delta_minutes"]  # minutes catalyst preceded event start
            if 0 <= dt <= 30 and cat.timing_precise:
                timing = 1.0
            elif 0 <= dt <= 120:
                timing = 0.7
            elif dt < 0:            # published after the move started
                timing = 0.4
            else:
                timing = 0.5
            if not cat.timing_precise:
                timing = min(timing, 0.5)
        else:
            timing = 0.0
        if not competitors:
            uniqueness = 1.0
        else:
            second = competitors[0]["score"]
            uniqueness = 1.0 - (second / best["score"] if best["score"] > 0 else 1.0)

    idio_share = idio.get("idio_share")
    if idio_share is None or (isinstance(idio_share, float) and np.isnan(idio_share)):
        idio_consistency = 0.5   # unknown — neutral
    else:
        top_is_macro = bool(candidates) and candidates[0]["catalyst"].source_type == "economic"
        # macro catalysts should explain market-wide moves, TSLA catalysts idiosyncratic ones
        idio_consistency = (1 - idio_share) if top_is_macro else idio_share

    comps = {
        "alignment": min(1.0, best_alignment),
        "idio_consistency": float(idio_consistency),
        "timing_precision": timing,
        "uniqueness": float(np.clip(uniqueness, 0.0, 1.0)),
    }
    total = sum(WEIGHTS[k] * v for k, v in comps.items())
    return {"confidence": round(float(total), 3),
            "components": {k: round(v, 3) for k, v in comps.items()}}
