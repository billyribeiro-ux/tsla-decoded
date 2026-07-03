"""ML attribution layer: permutation importance, order-flow proxies, regime clustering."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import StandardScaler

from .features import log_returns

log = logging.getLogger(__name__)


def order_flow_features(df_1min: pd.DataFrame) -> pd.DataFrame:
    """OHLCV-derived flow proxies on 1-min bars (regular session)."""
    df = df_1min[df_1min["session"] == "regular"].copy()
    ret = log_returns(df["close"])
    # tick rule: sign of the bar's close-to-close move signs its volume
    signed_vol = np.sign(ret).fillna(0) * df["volume"]
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng
    out = pd.DataFrame({
        "signed_volume": signed_vol,
        "clv": clv.fillna(0),
        "volume": df["volume"],
    })
    out["flow_imbalance_30m"] = (
        out["signed_volume"].rolling(30).sum() / out["volume"].rolling(30).sum()
    )
    return out


def event_flow_profile(flow: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    win = flow.loc[start - pd.Timedelta(minutes=5): end + pd.Timedelta(minutes=5)]
    if win.empty:
        return {}
    imb = float(win["signed_volume"].sum() / max(win["volume"].sum(), 1))
    clv = float(win["clv"].mean())
    character = "aggressive institutional-style selling" if imb < -0.35 else (
        "aggressive institutional-style buying" if imb > 0.35 else (
            "two-sided/rotational flow"))
    return {
        "volume_imbalance": round(imb, 3),
        "mean_clv": round(clv, 3),
        "total_volume": int(win["volume"].sum()),
        "character": character,
    }


def feature_importance(z: pd.DataFrame, bench_frames: dict[str, pd.DataFrame],
                       catalysts, seed: int = 7) -> dict:
    """Which evidence channel explains abnormal 5-min moves across the target week."""
    feats = pd.DataFrame(index=z.index)
    for sym, bdf in bench_frames.items():
        reg = bdf[bdf["session"] == "regular"]
        feats[f"ret_{sym}"] = log_returns(reg["close"]).reindex(z.index)
    feats["z_vol"] = z["z_vol"]
    feats["vwap_dev"] = z["vwap_dev"]
    for stype in ("press_release", "stock_news", "analyst", "economic"):
        ts_list = sorted([c.ts for c in catalysts if c.source_type == stype and c.ts is not None])
        if not ts_list:
            feats[f"min_since_{stype}"] = 1e4
            continue
        arr = pd.DatetimeIndex(ts_list)
        pos = arr.searchsorted(z.index, side="right") - 1
        mins = np.full(len(z), 1e4)
        valid = pos >= 0
        mins[valid] = (z.index[valid] - arr[pos[valid]]).total_seconds() / 60
        feats[f"min_since_{stype}"] = np.clip(mins, 0, 1e4)
    y = z["ret"].abs()
    mask = y.notna() & feats.notna().all(axis=1)
    X, y = feats[mask], y[mask]
    if len(X) < 50:
        return {}
    model = HistGradientBoostingRegressor(random_state=seed, max_iter=200)
    model.fit(X, y)
    imp = permutation_importance(model, X, y, n_repeats=10, random_state=seed)
    ranked = sorted(zip(X.columns, imp.importances_mean), key=lambda t: -t[1])
    return {name: round(float(v), 6) for name, v in ranked}


def regime_map(z: pd.DataFrame, k: int = 4, seed: int = 7) -> pd.Series:
    """K-means regimes per 30-min block on (realized vol, |ret|, volume z)."""
    blocks = z.resample("30min").agg(
        rv=("ret", lambda s: s.std()),
        absret=("ret", lambda s: s.abs().mean()),
        zvol=("z_vol", "mean"),
    ).dropna()
    if len(blocks) < k * 2:
        return pd.Series(dtype=int)
    Xs = StandardScaler().fit_transform(blocks)
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(Xs)
    labels = pd.Series(km.labels_, index=blocks.index, name="regime")
    # relabel so regime id increases with volatility
    order = blocks.groupby(labels)["rv"].mean().sort_values().index
    remap = {old: new for new, old in enumerate(order)}
    return labels.map(remap)
