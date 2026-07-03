"""FMP endpoint wrappers returning tidy, tz-aware (America/New_York) DataFrames."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from .fmp_client import FMPClient

log = logging.getLogger(__name__)

ET = "America/New_York"
RTH_START = "09:30"
RTH_END = "15:59"   # last bar label of the regular session for minute bars


def _to_frame(rows: list[dict] | None) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # FMP intraday timestamps are naive US/Eastern strings
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(ET, nonexistent="shift_forward", ambiguous=True)
    df = df.sort_values("date").set_index("date")
    df = df[~df.index.duplicated(keep="first")]
    tod = df.index.strftime("%H:%M")
    df["session"] = "regular"
    df.loc[tod < RTH_START, "session"] = "pre"
    df.loc[tod > RTH_END, "session"] = "post"
    return df[["open", "high", "low", "close", "volume", "session"]]


def _daterange_days(start: str, end: str):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            yield cur.isoformat()
        cur += timedelta(days=1)


def intraday(client: FMPClient, symbol: str, interval: str, start: str, end: str) -> pd.DataFrame:
    """Intraday OHLCV. 1-min is fetched per day (payload caps); coarser in ≤10-day chunks."""
    frames = []
    if interval == "1min":
        for day in _daterange_days(start, end):
            rows = client.get(f"historical-chart/{interval}", symbol=symbol, **{"from": day, "to": day})
            frames.append(_to_frame(rows))
    else:
        d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
        cur = d0
        while cur <= d1:
            chunk_end = min(cur + timedelta(days=9), d1)
            rows = client.get(
                f"historical-chart/{interval}",
                symbol=symbol,
                **{"from": cur.isoformat(), "to": chunk_end.isoformat()},
            )
            frames.append(_to_frame(rows))
            cur = chunk_end + timedelta(days=1)
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def daily(client: FMPClient, symbol: str, start: str, end: str) -> pd.DataFrame:
    rows = client.get("historical-price-eod/full", symbol=symbol, **{"from": start, "to": end})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


# -- catalyst sources -------------------------------------------------------

def stock_news(client: FMPClient, symbol: str, start: str, end: str, max_pages: int = 8) -> list[dict]:
    out: list[dict] = []
    for page in range(max_pages):
        rows = client.get("news/stock", symbols=symbol, **{"from": start, "to": end},
                          limit=250, page=page)
        if not rows:
            break
        out.extend(rows)
        if len(rows) < 250:
            break
    return out


def press_releases(client: FMPClient, symbol: str, max_pages: int = 4) -> list[dict]:
    out: list[dict] = []
    for page in range(max_pages):
        rows = client.get("news/press-releases", symbols=symbol, limit=100, page=page)
        if not rows:
            break
        out.extend(rows)
        if len(rows) < 100:
            break
    return out


def grades_news(client: FMPClient, symbol: str) -> list[dict]:
    return client.get("grades-news", symbol=symbol, limit=100) or []


def price_target_news(client: FMPClient, symbol: str) -> list[dict]:
    return client.get("price-target-news", symbol=symbol, limit=100) or []


def economic_calendar(client: FMPClient, start: str, end: str) -> list[dict]:
    return client.get("economic-calendar", **{"from": start, "to": end}) or []


def earnings_calendar(client: FMPClient, start: str, end: str) -> list[dict]:
    return client.get("earnings-calendar", **{"from": start, "to": end}) or []


def insider_trades(client: FMPClient, symbol: str) -> list[dict]:
    return client.get("insider-trading/search", symbol=symbol, page=0, limit=100) or []


def general_news(client: FMPClient, start: str, end: str, max_pages: int = 4) -> list[dict]:
    out: list[dict] = []
    for page in range(max_pages):
        rows = client.get("news/general-latest", **{"from": start, "to": end}, limit=250, page=page)
        if not rows:
            break
        out.extend(rows)
        if len(rows) < 250:
            break
    return out
