"""Evidence-weighted per-event confidence scoring."""
from __future__ import annotations

import numpy as np

WEIGHTS = {
    "alignment": 0.45,
    "idio_consistency": 0.20,
    "timing_precision": 0.20,
    "uniqueness": 0.15,
}


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
        best_alignment = best["score"]
        cat = best["catalyst"]
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
        if len(candidates) == 1:
            uniqueness = 1.0
        else:
            second = candidates[1]["score"]
            uniqueness = 1.0 - (second / best_alignment if best_alignment > 0 else 1.0)

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
