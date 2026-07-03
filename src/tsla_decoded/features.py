"""Return/volatility/VWAP features and intraday-seasonality baselines."""
from __future__ import annotations

import numpy as np
import pandas as pd

MAD_SCALE = 1.4826  # MAD -> sigma for a normal distribution


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close).diff()


def anchored_vwap(df: pd.DataFrame) -> pd.Series:
    """Per-day anchored VWAP over regular-session bars."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    day = df.index.date
    return pv.groupby(day).cumsum() / df["volume"].groupby(day).cumsum()


def realized_vol(returns: pd.Series, window_bars: int) -> pd.Series:
    return returns.rolling(window_bars).std() * np.sqrt(window_bars)


def seasonality_baseline(baseline_df: pd.DataFrame) -> pd.DataFrame:
    """Per bar-of-day robust stats from the baseline panel (regular session only).

    Returns a frame indexed by "HH:MM" with median/MAD of |log return| and volume.
    """
    df = baseline_df[baseline_df["session"] == "regular"].copy()
    df["ret"] = log_returns(df["close"])
    # zero out cross-day boundaries: first bar of each day has no prior close
    first_bar = pd.Series(df.index.date, index=df.index).ne(
        pd.Series(df.index.date, index=df.index).shift()
    )
    df.loc[first_bar, "ret"] = np.nan
    df["tod"] = df.index.strftime("%H:%M")

    def mad(x):
        return (x - x.median()).abs().median()

    g = df.groupby("tod")
    out = pd.DataFrame({
        "absret_med": g["ret"].apply(lambda s: s.abs().median()),
        "absret_mad": g["ret"].apply(lambda s: mad(s.abs())),
        "vol_med": g["volume"].median(),
        "vol_mad": g["volume"].apply(mad),
    })
    # floor MADs to avoid divide-by-zero on quiet bars
    out["absret_mad"] = out["absret_mad"].clip(lower=out["absret_med"].median() * 0.1 + 1e-6)
    out["vol_mad"] = out["vol_mad"].clip(lower=max(out["vol_med"].median() * 0.05, 1.0))
    return out


def seasonal_zscores(target_df: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Seasonality-adjusted robust z-scores for each regular-session target bar."""
    df = target_df[target_df["session"] == "regular"].copy()
    df["ret"] = log_returns(df["close"])
    first_bar = pd.Series(df.index.date, index=df.index).ne(
        pd.Series(df.index.date, index=df.index).shift()
    )
    df.loc[first_bar, "ret"] = np.nan
    df["tod"] = df.index.strftime("%H:%M")
    b = baseline.reindex(df["tod"]).set_axis(df.index)
    df["z_ret"] = (df["ret"].abs() - b["absret_med"]) / (MAD_SCALE * b["absret_mad"])
    df["z_ret_signed"] = df["z_ret"] * np.sign(df["ret"]).fillna(0)
    df["z_vol"] = (df["volume"] - b["vol_med"]) / (MAD_SCALE * b["vol_mad"])
    df["vwap"] = anchored_vwap(df)
    df["vwap_dev"] = (df["close"] - df["vwap"]) / df["vwap"]
    return df
