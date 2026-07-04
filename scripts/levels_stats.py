"""Institutional moving averages (50/100/200 SMA), the pre-market-high open tell,
and hard statistics for the July 2 TSLA session.

Reproduces the numbers in output/VOLUME_PROFILE_DECODE.md.
"""
import sys, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "src")
import json, subprocess, os
import numpy as np, pandas as pd
from scipy.stats import norm
from tsla_decoded.config import load_settings
from tsla_decoded.fmp_client import FMPClient
from tsla_decoded import data_loader as dl

s = load_settings(); c = FMPClient(s.api_key, s.cache_dir)

# --- daily SMAs + statistics (need ~200 sessions before Jul 2) --------------
d = dl.daily(c, "TSLA", "2025-05-01", "2026-07-02").sort_index()
d["r"] = np.log(d.close / d.close.shift())
for n in (50, 100, 200):
    d[f"sma{n}"] = d.close.rolling(n).mean()
d["atr"] = (d.high - d.low).rolling(14).mean()
jul1, jul2 = d.loc["2026-07-01"], d.loc["2026-07-02"]

print("=== 50/100/200-day SMAs as of Jul 1 (institutional buy zones) ===")
for n in (50, 100, 200):
    v = jul1[f"sma{n}"]
    print(f"  {n}-SMA ${v:.2f}: Jul-2 close ${jul2.close:.2f} = {(jul2.close/v-1)*100:+.1f}% "
          f"({'BELOW' if jul2.close < v else 'above'}), {(jul2.close-v)/jul2.atr:+.1f} ATR")

rets = d["r"].dropna()
z = (jul2.r - rets.mean()) / rets.std()
print("\n=== Statistics (n=%d daily sessions) ===" % len(rets))
print(f"  Jul-2 return {jul2.r*100:+.2f}% = {z:+.2f}sigma, {(rets < jul2.r).mean()*100:.1f}th pctile, "
      f"~1 in {1/norm.cdf(z):.0f} days (p={norm.cdf(z)*100:.2f}%)")
print(f"  3-day run-up into it {(d.close.loc['2026-07-01']/d.close.loc['2026-06-26']-1)*100:+.1f}% = "
      f"{(d.close.pct_change(3) < d.close.loc['2026-07-01']/d.close.loc['2026-06-26']-1).mean()*100:.0f}th pctile")
print(f"  Overnight gap {np.log(jul2.open/jul1.close)*100:+.2f}% (UP -> drop was intraday)")

# --- pre-market high vs cash open (the opening tell) ------------------------
key = os.environ.get("FMP_API_KEY") or s.api_key
url = ("https://financialmodelingprep.com/stable/historical-chart/1min"
       f"?symbol=TSLA&from=2026-07-02&to=2026-07-02&extended=true&apikey={key}")
raw = json.loads(subprocess.check_output(["curl", "-sS", url]))
m = pd.DataFrame(raw); m["date"] = pd.to_datetime(m["date"]); m = m.sort_values("date").set_index("date")
tod = m.index.strftime("%H:%M")
pre = m[tod < "09:30"]; rth = m[(tod >= "09:30") & (tod <= "16:00")]
pmh = pre["high"].max(); pmh_t = pre["high"].idxmax()
open_pop = rth.head(2)["high"].max()
print("\n=== Opening tell ===")
print(f"  pre-market high ${pmh:.2f} @ {pmh_t:%H:%M} (new high, above RTH week high 432.85)")
print(f"  cash open ${rth['open'].iloc[0]:.2f} = {(rth['open'].iloc[0]/pmh-1)*100:+.1f}% below PM high")
print(f"  opening pop ${open_pop:.2f} = LOWER HIGH, {(open_pop/pmh-1)*100:+.1f}% short of PM high "
      f"-> failed challenge = sellers stacked on the offer")
