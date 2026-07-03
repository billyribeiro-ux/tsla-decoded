"""VPIN and Kyle's lambda sanity on synthetic tapes."""
import numpy as np
import pandas as pd

from tsla_decoded.microstructure import bulk_volume_classify, kyles_lambda, vpin_series

ET = "America/New_York"


def make_tape(n=780, seed=0, one_sided=False, lam_bps_per_m=0.0):
    """Two synthetic sessions of 1-min bars; optionally one-sided or with planted impact."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-06-01 09:30", periods=390, freq="1min", tz=ET).append(
        pd.date_range("2026-06-02 09:30", periods=390, freq="1min", tz=ET))[:n]
    vol = (1e5 * rng.lognormal(0, 0.3, n)).astype(float)
    if one_sided:
        rets = -np.abs(rng.normal(0, 0.001, n))       # relentless selling
    elif lam_bps_per_m > 0:
        signed = rng.choice([-1, 1], n) * vol
        rets = (lam_bps_per_m * signed / 1e6) / 1e4 + rng.normal(0, 1e-5, n)
    else:
        rets = rng.normal(0, 0.001, n)                 # balanced noise
    close = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        "open": np.r_[100, close[:-1]], "close": close,
        "high": np.maximum(np.r_[100, close[:-1]], close) * 1.0005,
        "low": np.minimum(np.r_[100, close[:-1]], close) * 0.9995,
        "volume": vol, "session": "regular",
    }, index=idx)
    return df


def test_bvc_conserves_volume():
    tape = make_tape()
    bvc = bulk_volume_classify(tape)
    assert np.allclose(bvc["buy_vol"] + bvc["sell_vol"], bvc["volume"])


def test_vpin_high_for_one_sided_flow():
    bucket = 1e5 * 20
    toxic = vpin_series(make_tape(one_sided=True), bucket, window=10).dropna()
    calm = vpin_series(make_tape(one_sided=False, seed=3), bucket, window=10).dropna()
    assert toxic.mean() > calm.mean() + 0.2
    assert toxic.mean() > 0.5


def test_kyles_lambda_recovers_planted_impact():
    planted = 50.0  # bps per 1M signed shares
    tape = make_tape(lam_bps_per_m=planted, seed=4)
    from tsla_decoded.ml_attrib import order_flow_features
    flow = order_flow_features(tape)
    est = kyles_lambda(tape, flow)
    # tick-rule signing is imperfect; require right order of magnitude and strong t
    assert est["lambda"] > planted * 0.4
    assert est["t"] > 5
