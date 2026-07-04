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
    # day 1 flat around 100; day 2 gaps up to 101, HOD in first minutes, then a
    # steep dump that loses the prior session's VWAP (~100) inside the open window
    n = 390
    closes = np.r_[np.linspace(101.0, 101.5, 4),          # opening pop = early HOD
                   np.linspace(101.4, 97.0, 56),          # fast liquidation wave
                   np.linspace(97.0, 96.0, n - 60)]       # afternoon drift
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


# ---------------------------------------------------------------------------
# daily rules (FlowForensics_Daily.ts mirror)
# ---------------------------------------------------------------------------

def _daily_frame(rows):
    """rows: list of (open, high, low, close, volume)."""
    idx = pd.bdate_range("2026-03-02", periods=len(rows))
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)


def _flat_rows(n, price=100.0, vol=5e7):
    return [(price, price + 0.5, price - 0.5, price, vol)] * n


def test_daily_key_reversal_fires_sell():
    from tsla_decoded.signal_backtest import DAILY_DEFAULTS, generate_daily_signals
    rows = _flat_rows(30)
    rows += [(100, 104, 99.5, 103.5, 5.5e7),   # 3-day run-up builds
             (104, 107, 103.5, 106.5, 5.5e7),
             (107, 110, 106.5, 109.5, 5.5e7)]
    rows += [(110.5, 111, 101.5, 102.0, 9e7)]  # gap-up open, huge red close on the low
    sig = generate_daily_signals(_daily_frame(rows), DAILY_DEFAULTS)
    sells = sig[sig["signal"] == "SELL"]
    assert len(sells) == 1 and sells.iloc[0]["trigger"] == "key-reversal"


def test_daily_accumulation_fires_buy():
    from tsla_decoded.signal_backtest import DAILY_DEFAULTS, generate_daily_signals
    rows = _flat_rows(30)
    # modest positive drift so 10-day imbalance is positive but run-up stays small
    for i in range(6):
        p = 100 + i * 0.4
        rows.append((p, p + 0.6, p - 0.2, p + 0.4, 5.6e7))
    rows.append((102.4, 106.5, 102.2, 106.2, 8e7))  # accumulation day: big up, close on high
    sig = generate_daily_signals(_daily_frame(rows), DAILY_DEFAULTS)
    buys = sig[sig["signal"] == "BUY"]
    assert len(buys) >= 1
    assert buys.iloc[-1]["trigger"] == "accumulation-day"


def test_daily_flat_series_quiet():
    from tsla_decoded.signal_backtest import DAILY_DEFAULTS, generate_daily_signals
    sig = generate_daily_signals(_daily_frame(_flat_rows(40)), DAILY_DEFAULTS)
    assert len(sig) == 0


# ---------------------------------------------------------------------------
# timeframe robustness (v1.2): the same signature must fire at 1-min AND 5-min
# ---------------------------------------------------------------------------

def test_distribution_fires_at_1min_and_5min():
    """A gap-up-then-liquidation day must fire SELL whether bars are 1-min or 5-min."""
    from tsla_decoded.signal_backtest import (
        resample_intraday, scale_params, compute_features, generate_signals)
    n = 390
    closes = np.r_[np.linspace(101.0, 101.5, 4),
                   np.linspace(101.4, 97.0, 56),
                   np.linspace(97.0, 96.0, n - 60)]
    vol = np.where(np.arange(n) < 60, 4e5, 1.5e5)
    d2 = _frame("2026-06-02", closes, vol,
                opens=np.r_[101.0, closes[:-1]],
                highs=closes + 0.02, lows=closes - 0.02)
    tape = pd.concat([_flat_day("2026-06-01"), d2])

    fired = {}
    for label, bar_min, rule in (("1min", 1, None), ("5min", 5, "5min")):
        bars = tape if rule is None else resample_intraday(tape, rule)
        p = scale_params(DEFAULTS, bar_min)
        sig = generate_signals(compute_features(bars, p), p)
        sells = sig[(sig["signal"] == "SELL")
                    & (sig["ts"].dt.date == pd.Timestamp("2026-06-02").date())]
        fired[label] = len(sells)
    assert fired["1min"] >= 1, "SELL missing at 1-min"
    assert fired["5min"] >= 1, "SELL missing at 5-min (the reported bug)"


def test_scale_params_converts_minutes_to_bars():
    from tsla_decoded.signal_backtest import scale_params
    p5 = scale_params(DEFAULTS, 5)
    assert p5["imb_window"] == round(DEFAULTS["imb_window"] / 5)  # 30 -> 6
    assert p5["below_vwap_bars"] == round(DEFAULTS["below_vwap_bars"] / 5)  # 15 -> 3
    assert p5["open_window_min"] == DEFAULTS["open_window_min"]  # minute gate unchanged
