"""Volume-spike release-day inference and reaction metrics on synthetic data."""
import numpy as np
import pandas as pd

from tsla_decoded.delivery_history import (
    ReleaseQuarter,
    _quarter_of,
    _quarter_starts,
    reaction_metrics,
    summarize,
)


def make_daily(start="2025-01-02", periods=200, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=periods)
    close = 300 * np.exp(np.cumsum(rng.normal(0, 0.02, periods)))
    return pd.DataFrame({
        "open": close * (1 + rng.normal(0, 0.004, periods)),
        "close": close,
        "volume": (5e7 * rng.lognormal(0, 0.15, periods)).astype(int),
    }, index=idx)


def test_quarter_of_maps_release_month_to_prior_quarter():
    assert _quarter_of(pd.Timestamp("2026-07-02")) == "2026-Q2"
    assert _quarter_of(pd.Timestamp("2026-01-02")) == "2025-Q4"
    assert _quarter_of(pd.Timestamp("2025-10-02")) == "2025-Q3"


def test_quarter_starts_first_three_trading_days():
    daily = make_daily()
    qs = _quarter_starts(daily, "2025-01-01", "2025-12-31")
    assert "2025-Q1" in qs  # April dates report Q1
    april = qs["2025-Q1"]
    assert len(april) == 3
    assert all(ts.month == 4 for ts in april)
    assert april[0] == min(april)


def test_reaction_metrics_around_known_day():
    daily = make_daily()
    day = daily.index[50]
    m = reaction_metrics(daily, day)
    c = daily["close"]
    assert m["release_day"] == day
    assert np.isclose(m["run_up_5d"], c.iloc[49] / c.iloc[44] - 1)
    assert np.isclose(m["reaction_cc"], c.iloc[50] / c.iloc[49] - 1)
    assert np.isclose(m["post_1d"], c.iloc[51] / c.iloc[50] - 1)


def test_reaction_metrics_snaps_weekend_to_next_trading_day():
    daily = make_daily()
    saturday = pd.Timestamp("2025-03-08")
    assert saturday not in daily.index
    m = reaction_metrics(daily, saturday)
    assert m["release_day"] == pd.Timestamp("2025-03-10")


def _rq(quarter, run_up, reaction):
    return ReleaseQuarter(quarter=quarter, release_day=pd.Timestamp("2026-07-02"),
                          identified_by="pr", run_up_5d=run_up, reaction_oc=reaction,
                          reaction_cc=reaction, post_1d=None, post_5d=None,
                          verdict="unknown", fade=run_up > 0.05 and reaction < 0)


def test_summarize_base_rates_and_focus_percentiles():
    quarters = [
        _rq("2025-Q3", 0.08, -0.04), _rq("2025-Q4", -0.02, 0.03),
        _rq("2026-Q1", 0.01, 0.01), _rq("2026-Q2", 0.13, -0.08),
    ]
    stats = summarize(quarters, focus="2026-Q2")
    assert stats["n"] == 4
    assert stats["pct_red_reaction"] == 0.5
    assert stats["pct_red_given_runup_gt5"] == 1.0
    assert stats["focus_runup_percentile"] == 1.0
    assert stats["focus_reaction_percentile"] == 0.25
    assert quarters[3].fade and not quarters[1].fade
