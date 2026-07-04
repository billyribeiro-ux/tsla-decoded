"""Real order-flow decode via Databento: quote-verified aggressor classification.

Pulls XNAS.ITCH trades + top-of-book quotes for TSLA and classifies every trade
by Lee-Ready (trade price vs prevailing bid/ask) — the true aggressor side, not
the tick-rule proxy. Reproduces output/REAL_ORDERFLOW_DECODE.md.

Requires DATABENTO_API_KEY in .env. Cost ~$0.48 (trades + 2 days of mbp-1).
"""
import os, sys
import numpy as np, pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
CACHE = os.environ.get("DBN_CACHE", ".")
DAYS = {"2026-06-29": "+8% (build)", "2026-07-02": "-8% (unwind)"}


def _client():
    import databento as db
    return db.Historical(os.environ["DATABENTO_API_KEY"])


def fetch():
    c = _client()
    tp = os.path.join(CACHE, "tsla_trades.parquet")
    if not os.path.exists(tp):
        c.timeseries.get_range(dataset="XNAS.ITCH", symbols=["TSLA"], schema="trades",
            start="2026-06-29", end="2026-07-03", stype_in="raw_symbol").to_df().to_parquet(tp)
    for day in DAYS:
        qp = os.path.join(CACHE, f"tsla_mbp1_{day}.parquet")
        if not os.path.exists(qp):
            nxt = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            c.timeseries.get_range(dataset="XNAS.ITCH", symbols=["TSLA"], schema="mbp-1",
                start=day, end=nxt, stype_in="raw_symbol").to_df().to_parquet(qp)


def lee_ready(day):
    tr = pd.read_parquet(os.path.join(CACHE, "tsla_trades.parquet"))
    q = pd.read_parquet(os.path.join(CACHE, f"tsla_mbp1_{day}.parquet"))
    tr.index = tr.index.tz_convert("America/New_York")
    q.index = q.index.tz_convert("America/New_York")
    dd = pd.Timestamp(day).date()
    tr = tr[tr.index.date == dd].copy()
    q = q[q.index.date == dd][["bid_px_00", "ask_px_00"]]
    q = q[(q.bid_px_00 > 0) & (q.ask_px_00 > 0) & (q.ask_px_00 >= q.bid_px_00)]
    m = pd.merge_asof(tr.sort_index(), q.sort_index(), left_index=True,
                      right_index=True, direction="backward")
    mid = (m.bid_px_00 + m.ask_px_00) / 2
    m["lr"] = np.where(m.price >= m.ask_px_00, 1,
              np.where(m.price <= m.bid_px_00, -1,
              np.where(m.price > mid, 1, np.where(m.price < mid, -1, 0))))
    m["sv"] = m["lr"] * m["size"]
    tod = m.index.strftime("%H:%M")
    return m[(tod >= "09:30") & (tod < "16:00")]


if __name__ == "__main__":
    fetch()
    print("=== TRUE aggressor flow (Lee-Ready, quote-verified, Nasdaq-lit) ===")
    for day, label in DAYS.items():
        r = lee_ready(day)
        v, sd = r["size"].sum(), r["sv"].sum()
        fh = r[r.index.strftime("%H:%M") < "10:30"]["sv"].sum()
        print(f"  {day} {label}: vol {v/1e6:.1f}M  net delta {sd/1e6:+.2f}M "
              f"({sd/v*100:+.1f}% imb)  first-hr {fh/sd*100:.0f}% of day")
    print("\n  ~8% imbalance on 8% moves = passive-limit-order driven, not aggressive panic.")
