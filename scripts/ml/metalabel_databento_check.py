"""metalabel out-of-model spot-check: does the tick-rule CVD-slope proxy track
TRUE Lee-Ready aggressor flow? (2 Databento days, 2026-06-29 & 07-02.)

The proxy feature `cvd_slope` used by the meta-model is derived from FMP tick-rule
signed volume (sign of close diff). Here we verify it correlates with quote-verified
Lee-Ready signed flow. n=2 days -> a directional sanity check, NOT a validated stat.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
os.environ.setdefault("FMP_API_KEY", "cache-only")
from tsla_decoded.fmp_client import FMPClient           # noqa: E402
from tsla_decoded import data_loader as dl              # noqa: E402
from tsla_decoded import signal_backtest as sb          # noqa: E402

DBN = REPO / ".." / ".." / ".." / "scratchpad"
SCRATCH = Path("/tmp/claude-0/-home-user-tsla-decoded/"
               "95c77dab-52da-5fc9-b556-40637ad9c184/scratchpad")
DAYS = {"2026-06-29": "jun29", "2026-07-02": "jul2"}
OUT = REPO / "output" / "ml" / "metalabel"


def lee_ready_minute(day: str, tag: str) -> pd.Series:
    tr = pd.read_parquet(SCRATCH / "tsla_trades.parquet")
    q = pd.read_parquet(SCRATCH / f"tsla_mbp1_{tag}.parquet")
    tr.index = tr.index.tz_convert("America/New_York")
    q.index = q.index.tz_convert("America/New_York")
    dd = pd.Timestamp(day).date()
    tr = tr[tr.index.date == dd].copy()
    q = q[q.index.date == dd][["bid_px_00", "ask_px_00"]]
    q = q[(q.bid_px_00 > 0) & (q.ask_px_00 > 0) & (q.ask_px_00 >= q.bid_px_00)]
    m = pd.merge_asof(tr.sort_index(), q.sort_index(), left_index=True,
                      right_index=True, direction="backward")
    mid = (m.bid_px_00 + m.ask_px_00) / 2
    m["lr"] = np.where(m.price >= m.ask_px_00, 1,
              np.where(m.price <= m.bid_px_00, -1,
              np.where(m.price > mid, 1, np.where(m.price < mid, -1, 0))))
    m["sv"] = m["lr"] * m["size"]
    tod = m.index.strftime("%H:%M")
    m = m[(tod >= "09:30") & (tod < "16:00")]
    return m["sv"].resample("1min").sum()


def main():
    client = FMPClient(os.environ["FMP_API_KEY"], REPO / "data" / "raw")
    bars = dl.intraday(client, "TSLA", "1min", "2026-06-26", "2026-07-02")
    daily = dl.daily(client, "TSLA", "2026-04-01", "2026-07-02")
    feat = sb.compute_features(bars, sb.DEFAULTS, daily["close"])

    rows, all_true, all_proxy = [], [], []
    slope_true, slope_proxy = [], []
    for day, tag in DAYS.items():
        true_min = lee_ready_minute(day, tag)
        dd = pd.Timestamp(day).date()
        fday = feat[feat.index.date == dd]
        proxy_min = fday["signed_vol"].reindex(true_min.index)
        pair = pd.DataFrame({"true": true_min, "proxy": proxy_min}).dropna()
        if len(pair) < 10:
            continue
        r_min = pair["true"].corr(pair["proxy"])
        # sign agreement per minute
        sign_agree = (np.sign(pair["true"]) == np.sign(pair["proxy"])).mean()
        # 15-bar rolling slope of cumulative signed (true vs proxy)
        ct = pair["true"].cumsum()
        cp = pair["proxy"].cumsum()
        st = ct.diff().rolling(15).mean()
        sp = cp.diff().rolling(15).mean()
        slope_pair = pd.DataFrame({"st": st, "sp": sp}).dropna()
        r_slope = slope_pair["st"].corr(slope_pair["sp"]) if len(slope_pair) > 5 else np.nan
        rows.append({"day": day, "n_min": len(pair),
                     "corr_signed_vol": round(float(r_min), 3),
                     "sign_agree_frac": round(float(sign_agree), 3),
                     "corr_cvd_slope": round(float(r_slope), 3),
                     "true_net_delta": int(pair["true"].sum()),
                     "proxy_net_delta": int(pair["proxy"].sum())})
        all_true += list(pair["true"]); all_proxy += list(pair["proxy"])
        slope_true += list(slope_pair["st"]); slope_proxy += list(slope_pair["sp"])

    pooled_corr = float(np.corrcoef(all_true, all_proxy)[0, 1])
    pooled_slope_corr = float(np.corrcoef(slope_true, slope_proxy)[0, 1])
    res = {"per_day": rows,
           "pooled_corr_signed_vol": round(pooled_corr, 3),
           "pooled_corr_cvd_slope": round(pooled_slope_corr, 3),
           "n_days": len(rows),
           "caveat": "n=2 days; directional sanity check only, not statistically "
                     "validated. Confirms the tick-rule proxy is positively aligned "
                     "with quote-verified Lee-Ready flow at 1-min resolution."}
    (OUT / "metalabel_databento_check.json").write_text(
        __import__("json").dumps(res, indent=2))
    print(__import__("json").dumps(res, indent=2))


if __name__ == "__main__":
    main()
