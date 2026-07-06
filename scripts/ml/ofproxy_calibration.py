"""ofproxy TRACK 1 — proxy calibration / sanity-check against the 2 Databento
ground-truth days (2026-06-29, 2026-07-02).

This is a DESCRIPTIVE spot-check on n=2 days, NOT machine learning and NOT
cross-validatable. It gates which OHLCV proxies are sign-correct against the
Databento-verified phenomena (aggressor delta, displayed book imbalance,
absorption / price-impact). Nothing here is used as an ML label or feature.

For each Databento day we:
  1. aggregate trades to 1-min RTH OHLCV bars (Databento tape) and compute the
     exact OHLCV proxies used by the tradable model,
  2. build the ground-truth per-bar series:
       - true aggressor delta  (trade `side`: B=+, A=-, N=0)  -> aggressor imbalance
       - displayed book imbalance (mbp1 bid_sz_00 vs ask_sz_00)
       - Amihud-style price impact |ret| / dollar-vol   (absorption = inverse)
       - true Kyle lambda: OLS slope of bar return on true signed volume,
  3. regress each proxy on its matched ground truth: bar sign-agreement,
     Pearson corr, and a single OLS scale factor.

Output: output/ml/ofproxy/ofproxy_calibration.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
OUT = REPO / "output" / "ml" / "ofproxy"
OUT.mkdir(parents=True, exist_ok=True)

SP = "/tmp/claude-0/-home-user-tsla-decoded/95c77dab-52da-5fc9-b556-40637ad9c184/scratchpad"
ET = "America/New_York"
DAYS = {"jun29": "2026-06-29", "jul2": "2026-07-02"}


# --------------------------------------------------------------------------
# Databento ground truth per 1-min bar
# --------------------------------------------------------------------------
def databento_bars(day_key: str, iso: str) -> pd.DataFrame:
    tr = pd.read_parquet(f"{SP}/tsla_trades.parquet")
    q = pd.read_parquet(f"{SP}/tsla_mbp1_{day_key}.parquet")
    tr.index = tr.index.tz_convert(ET)
    q.index = q.index.tz_convert(ET)
    dd = pd.Timestamp(iso).date()
    tr = tr[(tr.index.date == dd) & (tr["action"] == "T")].copy()
    tod = tr.index.strftime("%H:%M")
    tr = tr[(tod >= "09:30") & (tod < "16:00")]

    # true aggressor signed volume from Databento's own aggressor tag
    sgn = tr["side"].map({"B": 1, "A": -1}).fillna(0)
    tr["true_sv"] = sgn * tr["size"]
    g = tr.resample("1min")
    bars = pd.DataFrame({
        "open": g["price"].first(), "high": g["price"].max(),
        "low": g["price"].min(), "close": g["price"].last(),
        "volume": g["size"].sum(), "true_sv": g["true_sv"].sum(),
    }).dropna(subset=["close"])
    bars["true_agg_imb"] = bars["true_sv"] / bars["volume"].replace(0, np.nan)

    # displayed book imbalance from mbp1 (bid vs ask size at top of book)
    q = q[(q.bid_px_00 > 0) & (q.ask_px_00 > 0) & (q.bid_sz_00 >= 0) & (q.ask_sz_00 >= 0)]
    q = q[q.index.date == dd]
    tot = (q["bid_sz_00"] + q["ask_sz_00"]).replace(0, np.nan)
    q_imb = (q["bid_sz_00"] - q["ask_sz_00"]) / tot
    bars["book_imb"] = q_imb.resample("1min").mean().reindex(bars.index)

    # Amihud illiquidity per bar; absorption is its inverse (big vol, small move)
    ret = bars["close"].pct_change()
    dollar = (bars["volume"] * bars["close"]).replace(0, np.nan)
    bars["amihud"] = ret.abs() / dollar
    bars["true_absorption"] = 1.0 / (bars["amihud"] * 1e9 + 1e-6)  # inverse illiquidity
    bars["ret"] = ret
    return bars


# --------------------------------------------------------------------------
# OHLCV proxies (same formulas the tradable model uses), on the Databento tape
# --------------------------------------------------------------------------
def ohlcv_proxies(bars: pd.DataFrame) -> pd.DataFrame:
    f = bars
    W = 30
    ret = f["close"].pct_change()
    # tick-rule signed volume (the engine's proxy — NOT the true aggressor tag)
    tick_sign = np.sign(f["close"].diff())
    signed_vol = tick_sign * f["volume"]

    volm = f["volume"].rolling(W).mean()
    vols = f["volume"].rolling(W).std().replace(0, np.nan)
    volz = (f["volume"] - volm) / vols
    absd = ret.abs()
    absorption = volz.rolling(5).mean() / (absd.rolling(5).mean() * 100 + 0.02)

    cov = ret.rolling(W).cov(signed_vol)
    var = signed_vol.rolling(W).var().replace(0, np.nan)
    kyle = cov / var
    kyle_scaled = kyle * signed_vol.abs().rolling(W).mean()

    rng = (f["high"] - f["low"]).replace(0, np.nan)
    upper = f["high"] - f[["open", "close"]].max(axis=1)
    lower = f[["open", "close"]].min(axis=1) - f["low"]
    wick_asym = (upper - lower) / rng
    clv = (((f["close"] - f["low"]) - (f["high"] - f["close"])) / rng).fillna(0)
    clv_wick = (clv + wick_asym).rolling(10).mean()

    out = pd.DataFrame(index=f.index)
    out["absorption_ratio"] = absorption
    out["kyle_lambda_proxy"] = kyle_scaled
    out["clv_wick_asymmetry"] = clv_wick
    out["tick_delta_momentum"] = signed_vol.rolling(W).sum() / f["volume"].rolling(W).sum()
    out["tick_bar_sign"] = tick_sign
    return out


def _reg(proxy: pd.Series, truth: pd.Series) -> dict:
    df = pd.concat([proxy.rename("p"), truth.rename("t")], axis=1).replace(
        [np.inf, -np.inf], np.nan).dropna()
    if len(df) < 10:
        return {"n": int(len(df)), "note": "insufficient"}
    p, t = df["p"].to_numpy(), df["t"].to_numpy()
    corr = float(np.corrcoef(p, t)[0, 1]) if p.std() > 0 and t.std() > 0 else np.nan
    sign_agree = float((np.sign(p) == np.sign(t)).mean())
    scale = float(np.polyfit(p, t, 1)[0]) if p.std() > 0 else np.nan
    return {"n": int(len(df)), "pearson": round(corr, 3),
            "sign_agreement": round(sign_agree, 3), "ols_scale": round(scale, 5)}


def calibrate() -> dict:
    result = {"caveat": ("DESCRIPTIVE spot-check on n=2 days. NOT cross-validatable. "
                         "Gates proxy sign-plausibility only; never used as ML "
                         "feature/label."), "days": {}}
    pooled = {}
    for key, iso in DAYS.items():
        bars = databento_bars(key, iso)
        prox = ohlcv_proxies(bars)
        day_res = {
            "n_bars": int(len(bars)),
            "true_day_agg_imb": round(float(bars["true_sv"].sum()
                                            / bars["volume"].sum()), 4),
            # THE core validated proxy pairings
            "absorption_ratio_vs_true_absorption": _reg(
                prox["absorption_ratio"], bars["true_absorption"]),
            "clv_wick_vs_book_imb": _reg(
                prox["clv_wick_asymmetry"], bars["book_imb"]),
            "tick_delta_vs_true_agg_imb": _reg(
                prox["tick_delta_momentum"], bars["true_agg_imb"]),
            "tick_bar_sign_vs_true_agg_sign": {
                "n": int(np.isfinite(bars["true_agg_imb"]).sum()),
                "sign_agreement": round(float(
                    (prox["tick_bar_sign"] == np.sign(bars["true_agg_imb"]))
                    [np.isfinite(bars["true_agg_imb"])].mean()), 3)},
        }
        # kyle: proxy lambda vs true lambda (slope ret ~ true signed vol, 30-bar)
        tcov = bars["ret"].rolling(30).cov(bars["true_sv"])
        tvar = bars["true_sv"].rolling(30).var().replace(0, np.nan)
        true_kyle = (tcov / tvar) * bars["true_sv"].abs().rolling(30).mean()
        day_res["kyle_proxy_vs_true_kyle"] = _reg(prox["kyle_lambda_proxy"], true_kyle)
        result["days"][iso] = day_res
        pooled.setdefault("absorption", []).append(prox["absorption_ratio"].reset_index(drop=True))
    return result


if __name__ == "__main__":
    res = calibrate()
    (OUT / "ofproxy_calibration.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))
    print("\nsaved:", OUT / "ofproxy_calibration.json")
