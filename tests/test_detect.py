"""Detector must find a planted spike in synthetic data and stay quiet on noise."""
import numpy as np
import pandas as pd
import pytest

from tsla_decoded.detect import detect_events
from tsla_decoded.features import seasonality_baseline, seasonal_zscores

ET = "America/New_York"
CFG = {
    "ret_z_threshold": 4.0, "vol_z_threshold": 5.0, "vol_z_ret_min": 2.0,
    "merge_gap_minutes": 15, "vwap_dev_sigma": 2.0, "gap_z_threshold": 2.5,
    "major_event_z": 4.0,
}


def make_panel(days, seed=0, spike_at=None):
    """Synthetic 5-min RTH panel: lognormal noise, U-shaped volume."""
    rng = np.random.default_rng(seed)
    frames = []
    for d in days:
        idx = pd.date_range(f"{d} 09:30", f"{d} 15:55", freq="5min", tz=ET)
        n = len(idx)
        u = np.abs(np.linspace(-1, 1, n))
        vol = (1e5 * (1 + 2 * u ** 2) * rng.lognormal(0, 0.2, n)).astype(int)
        rets = rng.normal(0, 0.0012, n)
        if spike_at is not None and d == spike_at[0]:
            rets[spike_at[1]] = spike_at[2]
            vol[spike_at[1]] *= 12
        close = 100 * np.exp(np.cumsum(rets))
        df = pd.DataFrame({
            "open": close * (1 - rets / 2), "high": close * 1.001, "low": close * 0.999,
            "close": close, "volume": vol, "session": "regular",
        }, index=idx)
        frames.append(df)
    return pd.concat(frames)


@pytest.fixture(scope="module")
def baseline_days():
    return [f"2026-06-{d:02d}" for d in range(1, 27) if pd.Timestamp(f"2026-06-{d:02d}").weekday() < 5]


def test_planted_spike_detected(baseline_days):
    base = make_panel(baseline_days, seed=1)
    stats = seasonality_baseline(base)
    week = make_panel(["2026-06-29"], seed=2, spike_at=("2026-06-29", 40, -0.03))
    daily = pd.DataFrame({
        "open": 100.0, "close": [100 * (1 + x) for x in np.random.default_rng(3).normal(0, 0.02, 30)],
    }, index=pd.date_range("2026-05-15", periods=30, freq="B"))
    events, _ = detect_events(week, stats, daily, CFG)
    spikes = [e for e in events if e.kind == "spike"]
    assert spikes, "planted -3% bar not detected"
    ev = spikes[0]
    assert ev.direction == "down"
    assert ev.start.strftime("%H:%M") == (pd.Timestamp("09:30") + pd.Timedelta(minutes=200)).strftime("%H:%M")


def test_quiet_data_no_spikes(baseline_days):
    base = make_panel(baseline_days, seed=1)
    stats = seasonality_baseline(base)
    week = make_panel(["2026-06-29"], seed=5)  # pure noise
    daily = pd.DataFrame({"open": 100.0, "close": 100.0},
                         index=pd.date_range("2026-05-15", periods=30, freq="B"))
    events, _ = detect_events(week, stats, daily, CFG)
    assert not [e for e in events if e.kind == "spike"]


def test_baseline_zscores_standard(baseline_days):
    """z-scores of the baseline against itself should be roughly standard."""
    base = make_panel(baseline_days, seed=1)
    stats = seasonality_baseline(base)
    z = seasonal_zscores(base, stats)
    assert abs(z["z_ret"].median()) < 0.6
    assert (z["z_ret"] > 4).mean() < 0.01
    assert abs(z["z_vol"].median()) < 0.6
