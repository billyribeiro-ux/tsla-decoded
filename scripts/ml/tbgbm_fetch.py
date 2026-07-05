"""tbgbm_fetch: backfill FMP 1-min RTH + daily bars for TSLA, 2021-01-04 onward.

Deliberately drops 2010-2020 (different vol/liquidity regime per audit).
Writes consolidated parquet to output/ml/tbgbm/tbgbm_1min.parquet and
tbgbm_daily.parquet. Idempotent: uses the FMP per-day JSON cache under data/raw.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tsla_decoded.config import load_settings          # noqa: E402
from tsla_decoded.fmp_client import FMPClient           # noqa: E402
from tsla_decoded import data_loader as dl              # noqa: E402

OUT = ROOT / "output" / "ml" / "tbgbm"
OUT.mkdir(parents=True, exist_ok=True)

START = "2021-01-04"
END = "2026-07-02"
SYMBOL = "TSLA"


def _weekdays(start: str, end: str):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            yield cur.isoformat()
        cur += timedelta(days=1)


def main() -> None:
    s = load_settings()
    client = FMPClient(s.api_key, s.cache_dir, refresh=False)

    # -- daily bars (single call; covers overnight gap context) -------------
    daily = dl.daily(client, SYMBOL, START, END)
    daily.to_parquet(OUT / "tbgbm_daily.parquet")
    print(f"daily: {len(daily)} rows  {daily.index.min()} .. {daily.index.max()}")

    # -- 1-min RTH per day --------------------------------------------------
    frames = []
    days = list(_weekdays(START, END))
    empty = 0
    for i, day in enumerate(days):
        rows = client.get("historical-chart/1min", symbol=SYMBOL,
                          **{"from": day, "to": day})
        if not rows:
            empty += 1
            continue
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        frames.append(df[["date", "open", "high", "low", "close", "volume"]])
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(days)} days  http={client.http_requests}  empty={empty}",
                  flush=True)

    allbars = pd.concat(frames, ignore_index=True)
    allbars = allbars.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    # RTH filter: 09:30..15:59 label
    tod = allbars["date"].dt.strftime("%H:%M")
    allbars = allbars[(tod >= "09:30") & (tod <= "15:59")].reset_index(drop=True)
    allbars.to_parquet(OUT / "tbgbm_1min.parquet")
    ndays = allbars["date"].dt.date.nunique()
    print(f"1min: {len(allbars)} bars over {ndays} trading days "
          f"({allbars['date'].min()} .. {allbars['date'].max()})")
    print(f"empty/holiday days skipped: {empty}   total http requests: {client.http_requests}")


if __name__ == "__main__":
    main()
