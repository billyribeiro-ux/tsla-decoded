"""metalabel STEP 0: backfill FMP 1-min RTH history into data/raw cache.

Writes directly to the same cache paths FMPClient.get() uses, so the existing
data_loader.intraday() picks them up transparently. Parallel fetch (FMP tolerates
~12 concurrent). TSLA IPO'd 2010-06-29; FMP serves 1-min back to then.

Usage: python scripts/ml/metalabel_backfill.py TSLA 2010-06-29 2026-07-02
       python scripts/ml/metalabel_backfill.py SPY  --days-from-signals output/ml/metalabel/signal_dates.json
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / "data" / "raw"
BASE = "https://financialmodelingprep.com/stable"
load_dotenv(REPO / ".env")
KEY = os.environ["FMP_API_KEY"]


def cache_path(endpoint: str, params: dict) -> Path:
    canon = json.dumps({"endpoint": endpoint, "params": params}, sort_keys=True)
    digest = hashlib.sha1(canon.encode()).hexdigest()[:16]
    slug = endpoint.replace("/", "_")
    return CACHE / f"{slug}__{digest}.json"


def weekdays(start: str, end: str):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            yield cur.isoformat()
        cur += timedelta(days=1)


def fetch_day(symbol: str, day: str, refresh: bool = False) -> tuple[str, int]:
    endpoint = "historical-chart/1min"
    params = {"symbol": symbol, "from": day, "to": day}
    path = cache_path(endpoint, params)
    if path.exists() and not refresh:
        try:
            data = json.loads(path.read_text())
            return day, (len(data) if isinstance(data, list) else 0)
        except Exception:
            pass
    for attempt in range(4):
        try:
            r = requests.get(f"{BASE}/{endpoint}",
                             params={**params, "apikey": KEY}, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code in (402, 403):
                data = {"__unavailable__": r.status_code}
            else:
                r.raise_for_status()
                data = r.json()
            path.write_text(json.dumps(data))
            return day, (len(data) if isinstance(data, list) else 0)
        except requests.RequestException:
            time.sleep(1.5 * (attempt + 1))
    return day, -1


def backfill(symbol: str, days: list[str], workers: int = 12) -> dict:
    t0 = time.time()
    counts = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_day, symbol, d): d for d in days}
        done = 0
        for fut in as_completed(futs):
            day, n = fut.result()
            counts[day] = n
            done += 1
            if done % 250 == 0:
                print(f"  {symbol}: {done}/{len(days)} days, {time.time()-t0:.0f}s", flush=True)
    nonempty = sum(1 for v in counts.values() if v and v > 0)
    print(f"{symbol}: {len(days)} days fetched, {nonempty} non-empty, "
          f"{time.time()-t0:.0f}s", flush=True)
    return counts


if __name__ == "__main__":
    symbol = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "--days-from-signals":
        dates = sorted(set(json.loads(Path(sys.argv[3]).read_text())))
        days = dates
    else:
        start, end = sys.argv[2], sys.argv[3]
        days = list(weekdays(start, end))
    print(f"backfilling {symbol}: {len(days)} weekdays", flush=True)
    counts = backfill(symbol, days)
    out = REPO / "output" / "ml" / "metalabel"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"backfill_{symbol}_counts.json").write_text(json.dumps(counts))
