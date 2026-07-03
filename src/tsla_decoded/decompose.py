"""Market/sector decomposition: how much of each move was market beta vs TSLA-specific."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .features import log_returns

log = logging.getLogger(__name__)


def _aligned_returns(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rets = {}
    for sym, df in frames.items():
        reg = df[df["session"] == "regular"]
        r = log_returns(reg["close"])
        first_bar = pd.Series(reg.index.date, index=reg.index).ne(
            pd.Series(reg.index.date, index=reg.index).shift()
        )
        r[first_bar] = np.nan
        rets[sym] = r
    return pd.DataFrame(rets).dropna()


class MarketModel:
    """OLS: r_TSLA = a + b1*r_SPY + b2*r_QQQ, fit on baseline 5-min returns (HAC errors)."""

    def __init__(self, symbol: str, benchmarks: list[str]):
        self.symbol = symbol
        self.benchmarks = benchmarks
        self.result = None

    def fit(self, baseline_frames: dict[str, pd.DataFrame]) -> "MarketModel":
        rets = _aligned_returns(baseline_frames)
        y = rets[self.symbol]
        X = sm.add_constant(rets[self.benchmarks])
        self.result = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
        log.info("market model R²=%.3f betas=%s", self.result.rsquared,
                 dict(self.result.params.round(3)))
        return self

    def summary(self) -> dict:
        r = self.result
        return {
            "r_squared": round(float(r.rsquared), 4),
            "params": {k: round(float(v), 4) for k, v in r.params.items()},
        }

    def idio_share(self, week_frames: dict[str, pd.DataFrame],
                   start: pd.Timestamp, end: pd.Timestamp) -> dict:
        """Share of the event-window move NOT explained by SPY/QQQ (clipped to [0,1])."""
        rets = _aligned_returns(week_frames)
        # pad one bar so single-bar events still capture a return
        win = rets.loc[start - pd.Timedelta(minutes=5): end]
        if win.empty:
            return {"idio_share": np.nan, "actual_pct": np.nan, "market_pct": np.nan}
        X = sm.add_constant(win[self.benchmarks], has_constant="add")
        predicted = float(self.result.predict(X).sum())
        actual = float(win[self.symbol].sum())
        if abs(actual) < 1e-9:
            share = np.nan
        else:
            share = float(np.clip(1 - predicted / actual, 0.0, 1.0))
            # opposite-sign prediction means the move was fully idiosyncratic
            if np.sign(predicted) != np.sign(actual):
                share = 1.0
        return {
            "idio_share": share,
            "actual_pct": actual * 100,
            "market_pct": predicted * 100,
        }
