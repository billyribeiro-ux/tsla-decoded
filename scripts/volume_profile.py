"""Volume-profile / market-profile decode of the TSLA week from 1-min bars.

Distributes each minute's volume (and tick-rule signed volume = delta) uniformly
across that bar's high-low range into price bins, then derives per-day and
composite POC / Value Area / HVN-LVN / naked POCs / delta-at-price.

Honest limit: true footprint bid/ask imbalance needs tick data with trade
direction. From 1-min OHLCV, delta is approximated by the tick rule
(sign of close-to-close). Stated where it matters.
"""
import sys, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "src")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tsla_decoded.config import load_settings
from tsla_decoded.fmp_client import FMPClient
from tsla_decoded import data_loader as dl

BIN = 0.50  # price bin width in dollars

s = load_settings(); c = FMPClient(s.api_key, s.cache_dir)
m1 = dl.intraday(c, "TSLA", "1min", s.target_start, s.target_end)
reg = m1[m1.session == "regular"].copy()
reg["sv_sign"] = np.sign(reg["close"].diff()).fillna(0)

lo_all, hi_all = reg["low"].min(), reg["high"].max()
edges = np.arange(np.floor(lo_all / BIN) * BIN, np.ceil(hi_all / BIN) * BIN + BIN, BIN)
centers = (edges[:-1] + edges[1:]) / 2


def profile(bars):
    """Return (vol_at_price, delta_at_price) arrays over `centers`."""
    vol = np.zeros(len(centers)); delta = np.zeros(len(centers))
    for _, r in bars.iterrows():
        lo, hi, v, sg = r["low"], r["high"], r["volume"], r["sv_sign"]
        if hi <= lo:
            idx = np.searchsorted(edges, lo, "right") - 1
            idx = min(max(idx, 0), len(centers) - 1)
            vol[idx] += v; delta[idx] += v * sg
            continue
        b0 = max(np.searchsorted(edges, lo, "right") - 1, 0)
        b1 = min(np.searchsorted(edges, hi, "right") - 1, len(centers) - 1)
        n = b1 - b0 + 1
        vol[b0:b1 + 1] += v / n
        delta[b0:b1 + 1] += (v * sg) / n
    return vol, delta


def value_area(vol, pct=0.70):
    poc = int(np.argmax(vol)); total = vol.sum(); acc = vol[poc]
    lo = hi = poc
    while acc < pct * total:
        below = vol[lo - 1] if lo > 0 else -1
        above = vol[hi + 1] if hi < len(vol) - 1 else -1
        if above >= below:
            hi += 1; acc += vol[hi]
        else:
            lo -= 1; acc += vol[lo]
    return poc, lo, hi


days = sorted({t.date() for t in reg.index})
print(f"bin=${BIN}  range ${lo_all:.2f}-${hi_all:.2f}\n")
poc_hist = []
for d in days:
    b = reg[reg.index.date == d]
    vol, delta = profile(b)
    poc, val_lo, val_hi = value_area(vol)
    o, cl = b["open"].iloc[0], b["close"].iloc[-1]
    poc_hist.append((d, centers[poc], centers[val_lo], centers[val_hi], centers[np.argmax(delta)], centers[np.argmin(delta)]))
    print(f"{d}  O {o:.2f} C {cl:.2f}")
    print(f"   POC ${centers[poc]:.2f}  ValueArea ${centers[val_lo]:.2f}-${centers[val_hi]:.2f}"
          f"  ({(vol[val_lo:val_hi+1].sum()/vol.sum()):.0%} vol)")
    print(f"   most BUYING delta @ ${centers[np.argmax(delta)]:.2f}   most SELLING delta @ ${centers[np.argmin(delta)]:.2f}")
    # HVN/LVN
    order = np.argsort(vol)[::-1]
    hvn = sorted(centers[order[:3]])
    print(f"   high-volume nodes (shelves): {['$%.2f'%x for x in hvn]}")
    print()

# composite
vol, delta = profile(reg)
poc, val_lo, val_hi = value_area(vol)
print("=== COMPOSITE (whole week) ===")
print(f"   Naked/virgin POC of week: ${centers[poc]:.2f}  ValueArea ${centers[val_lo]:.2f}-${centers[val_hi]:.2f}")
print(f"   week net delta: {delta.sum()/1e6:.1f}M signed shares "
      f"({'net BUYING' if delta.sum()>0 else 'net SELLING'})")

# POC migration read
print("\n=== POC MIGRATION ===")
for i,(d,p,vl,vh,bd,sd) in enumerate(poc_hist):
    arrow = "" if i==0 else ("  UP" if p>poc_hist[i-1][1] else "  DOWN")
    print(f"   {d}: POC ${p:.2f}{arrow}")

# naked POCs: prior-day POC not traded through on July 2
jul2 = reg[reg.index.date == days[-1]]
j2lo, j2hi = jul2["low"].min(), jul2["high"].max()
print("\n=== NAKED POCs left above July 2's range ===")
for d,p,vl,vh,bd,sd in poc_hist[:-1]:
    if p > j2hi:
        print(f"   {d} POC ${p:.2f} — untouched, sits ${p-j2hi:.2f} above Jul-2 high (unfinished business overhead)")

# chart: composite profile + per-day POC
fig, ax = plt.subplots(figsize=(9, 11))
buy = np.where(delta > 0, delta, 0); sell = np.where(delta < 0, -delta, 0)
ax.barh(centers, vol, height=BIN*0.9, color="#b0bec5", label="volume at price")
ax.barh(centers, buy, height=BIN*0.5, color="#2e7d32", label="buy delta")
ax.barh(centers, -sell, height=BIN*0.5, color="#c62828", label="sell delta")
ax.axhline(centers[poc], color="#000", lw=1.5, ls="--", label=f"week POC ${centers[poc]:.2f}")
ax.axhline(centers[val_hi], color="#607d8b", lw=0.8, ls=":")
ax.axhline(centers[val_lo], color="#607d8b", lw=0.8, ls=":")
for d,p,vl,vh,bd,sd in poc_hist:
    ax.plot(vol.max()*1.05, p, "o", color="#1565c0")
    ax.annotate(f"{d.strftime('%m-%d')} POC", (vol.max()*1.06, p), fontsize=7, va="center")
ax.set_ylabel("price"); ax.set_xlabel("volume (shares, distributed across bar range)")
ax.set_title("TSLA Jun29-Jul2 — composite volume profile, POC, value area, delta-at-price")
ax.legend(loc="lower right", fontsize=8); ax.grid(alpha=0.2, axis="x")
fig.tight_layout(); fig.savefig("output/charts/volume_profile.png", dpi=130)
print("\nchart -> output/charts/volume_profile.png")
