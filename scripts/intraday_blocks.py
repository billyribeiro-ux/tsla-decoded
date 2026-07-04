"""Intraday execution timing: net delta (tick-rule signed volume) by 30-minute
block per session, revealing WHEN inside each day the accumulation/distribution
fired. Reproduces the tables in Intraday.md. Needs extended-hours 1-min JSON
(historical-chart/1min?extended=true) cached as ext_<date>.json, or set FETCH=1
to pull them via the FMP key in .env."""
import json, os, subprocess, sys
import numpy as np, pandas as pd

DAYS = ["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"]
DATA = os.environ.get("EXT_DIR", ".")


def ensure(day):
    p = os.path.join(DATA, f"ext_{day}.json")
    if os.path.exists(p):
        return p
    sys.path.insert(0, "src")
    from tsla_decoded.config import load_settings
    key = load_settings().api_key
    url = ("https://financialmodelingprep.com/stable/historical-chart/1min"
           f"?symbol=TSLA&from={day}&to={day}&extended=true&apikey={key}")
    open(p, "w").write(subprocess.check_output(["curl", "-sS", url]).decode())
    return p


def load(day):
    m = pd.DataFrame(json.load(open(ensure(day))))
    m["date"] = pd.to_datetime(m["date"]); m = m.sort_values("date").set_index("date")
    m["tod"] = m.index.strftime("%H:%M")
    return m[(m.tod >= "09:30") & (m.tod <= "16:00")].copy()


for day in DAYS:
    r = load(day)
    r["sv"] = np.sign(r["close"].diff()).fillna(0) * r["volume"]
    blk = r.resample("30min")
    nd, vol, px = blk["sv"].sum(), blk["volume"].sum(), blk["close"].last()
    first_hr = r[r.tod < "10:30"]["sv"].sum()
    print(f"=== {day}  full-day net delta {r.sv.sum()/1e6:+.1f}M  "
          f"| first-hour {first_hr/1e6:+.1f}M ({first_hr/r.sv.sum()*100:.0f}% of day) ===")
    for t, v in nd.items():
        imb = v / vol.loc[t] if vol.loc[t] else 0
        bar = ("+" if v >= 0 else "-") * int(min(abs(v) / 6e5, 20))
        print(f"  {t:%H:%M}  netD {v/1e6:+5.1f}M  imb {imb:+.2f}  px {px.loc[t]:.2f}  {bar}")
    print(f"  >> heaviest BUY {nd.idxmax():%H:%M} (+{nd.max()/1e6:.1f}M) | "
          f"heaviest SELL {nd.idxmin():%H:%M} ({nd.min()/1e6:.1f}M)\n")
