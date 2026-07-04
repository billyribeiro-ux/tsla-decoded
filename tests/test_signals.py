"""FlowForensics rules on synthetic tapes: fire on the signatures, stay quiet on noise."""
import numpy as np
import pandas as pd

from tsla_decoded.signal_backtest import DEFAULTS, compute_features, generate_signals

ET = "America/New_York"


def _frame(day, closes, volumes, opens=None, highs=None, lows=None):
    idx = pd.date_range(f"{day} 09:30", periods=len(closes), freq="1min", tz=ET)
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "open": opens if opens is not None else np.r_[closes[0], closes[:-1]],
        "high": highs if highs is not None else closes + 0.05,
        "low": lows if lows is not None else closes - 0.05,
        "close": closes,
        "volume": np.asarray(volumes, dtype=float),
        "session": "regular",
    }, index=idx)


def _flat_day(day, price=100.0, n=390, vol=1e5, seed=0):
    rng = np.random.default_rng(seed)
    closes = price + np.cumsum(rng.normal(0, 0.01, n))
    return _frame(day, closes, np.full(n, vol) * rng.lognormal(0, 0.05, n))


def test_accumulation_tape_fires_buy():
    # day 1 flat; day 2 grinds up on swelling one-sided volume, closes near bar highs
    n = 390
    up = 100 + np.arange(n) * 0.02                       # steady climb
    vol = np.where(np.arange(n) >= 35, 2.5e5, 1e5)       # volume ramps during the drive
    d2 = _frame("2026-06-02", up, vol,
                highs=up + 0.02, lows=up - 0.10)          # closes near highs -> CLV > 0
    tape = pd.concat([_flat_day("2026-06-01"), d2])
    feat = compute_features(tape, DEFAULTS)
    sig = generate_signals(feat, DEFAULTS)
    buys = sig[(sig["signal"] == "BUY") & (sig["ts"].dt.date == pd.Timestamp("2026-06-02").date())]
    assert len(buys) >= 1, "accumulation signature did not fire BUY"


def test_gap_up_rejection_fires_sell():
    # day 1 flat around 100; day 2 gaps up to 101, HOD in first minutes, then heavy dump
    n = 390
    closes = np.r_[np.linspace(101.0, 101.5, 4),          # opening pop = early HOD
                   np.linspace(101.4, 96.0, n - 4)]       # relentless slide
    vol = np.where(np.arange(n) < 60, 4e5, 1.5e5)         # front-loaded volume
    d2 = _frame("2026-06-02", closes, vol,
                opens=np.r_[101.0, closes[:-1]],
                highs=closes + 0.02, lows=closes - 0.02)
    tape = pd.concat([_flat_day("2026-06-01"), d2])
    feat = compute_features(tape, DEFAULTS)
    sig = generate_signals(feat, DEFAULTS)
    sells = sig[(sig["signal"] == "SELL")
                & (sig["ts"].dt.date == pd.Timestamp("2026-06-02").date())]
    assert len(sells) >= 1, "gap-up rejection signature did not fire SELL"
    assert sells["ts"].min().time() <= pd.Timestamp("10:45").time()


def test_quiet_tape_stays_quiet():
    tape = pd.concat([_flat_day("2026-06-01", seed=1), _flat_day("2026-06-02", seed=2)])
    feat = compute_features(tape, DEFAULTS)
    sig = generate_signals(feat, DEFAULTS)
    assert len(sig) == 0, f"noise tape produced signals: {sig}"
