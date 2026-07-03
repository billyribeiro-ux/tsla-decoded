"""Alignment scoring: a coincident press release must outrank a stale article."""
import pandas as pd

from tsla_decoded.catalysts import Catalyst, align, deliveries_check, relevance
from tsla_decoded.detect import Event

ET = "America/New_York"


def _event(start="2026-07-02 09:35", direction="down"):
    ts = pd.Timestamp(start, tz=ET)
    return Event(event_id="E0702-0935", start=ts, end=ts + pd.Timedelta(minutes=20),
                 direction=direction, magnitude_pct=-3.0, peak_z=6.0, peak_vol_z=7.0,
                 kind="spike", resolution="5min")


def test_coincident_pr_outranks_stale_news():
    ev = _event()
    fresh_pr = Catalyst(ts=pd.Timestamp("2026-07-02 09:20", tz=ET), source_type="press_release",
                        headline="Tesla Second Quarter 2026 Production, Deliveries & Deployments",
                        text="Tesla delivered 465,000 vehicles")
    stale = Catalyst(ts=pd.Timestamp("2026-06-30 08:00", tz=ET), source_type="stock_news",
                     headline="Tesla deliveries expected to decline analysts say")
    res = align([ev], [stale, fresh_pr])["E0702-0935"]
    assert res, "no candidates aligned"
    assert res[0]["catalyst"] is fresh_pr
    assert res[0]["delta_minutes"] == 15.0


def test_direction_consistency_boosts_bearish_for_down_moves():
    down = relevance(Catalyst(ts=None, source_type="stock_news",
                              headline="Tesla downgrade: analyst cuts to sell rating"), "down")
    up = relevance(Catalyst(ts=None, source_type="stock_news",
                            headline="Tesla downgrade: analyst cuts to sell rating"), "up")
    assert down > up


def test_deliveries_check_extracts_figures():
    pr = Catalyst(ts=pd.Timestamp("2026-07-02 08:00", tz=ET), source_type="press_release",
                  headline="Tesla Second Quarter 2026 Production, Deliveries & Deployments",
                  text="In Q2, we produced 470,500 vehicles and delivered 465,100 vehicles.")
    out = deliveries_check([pr])
    assert out and out["found"]
    assert out["figures"]["deliveries"] == 465100
    assert out["figures"]["production"] == 470500


def test_no_delivery_release_returns_none():
    assert deliveries_check([Catalyst(ts=None, source_type="stock_news",
                                      headline="Tesla opens new store")]) is None
