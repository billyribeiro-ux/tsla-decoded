"""Full-week auction decode: per-day pre-market tell, opening type, initial
balance / range extension, day-type, POC / value area / delta-at-price, and how
each day set up the next. TSLA Jun 29 - Jul 2 2026, from extended 1-min bars."""
import json, numpy as np, pandas as pd

BIN = 0.50
DAYS = ["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"]
PRIOR_CLOSE = {"2026-06-29": 379.71, "2026-06-30": 411.84,
               "2026-07-01": 420.60, "2026-07-02": 425.30}


def load(day):
    m = pd.DataFrame(json.load(open(f"ext_{day}.json")))
    m["date"] = pd.to_datetime(m["date"]); m = m.sort_values("date").set_index("date")
    m["tod"] = m.index.strftime("%H:%M")
    return m


def vprofile(bars):
    lo, hi = bars["low"].min(), bars["high"].max()
    edges = np.arange(np.floor(lo/BIN)*BIN, np.ceil(hi/BIN)*BIN + BIN, BIN)
    ctr = (edges[:-1]+edges[1:])/2
    vol = np.zeros(len(ctr)); dlt = np.zeros(len(ctr))
    sgn = np.sign(bars["close"].diff()).fillna(0)
    for (_, r), sg in zip(bars.iterrows(), sgn):
        b0 = max(np.searchsorted(edges, r.low, "right")-1, 0)
        b1 = min(np.searchsorted(edges, r.high, "right")-1, len(ctr)-1)
        n = max(b1-b0+1, 1); vol[b0:b1+1] += r.volume/n; dlt[b0:b1+1] += r.volume*sg/n
    poc = int(np.argmax(vol)); tot = vol.sum(); acc = vol[poc]; a = b = poc
    while acc < 0.7*tot:
        below = vol[a-1] if a > 0 else -1; above = vol[b+1] if b < len(vol)-1 else -1
        if above >= below: b += 1; acc += vol[b]
        else: a -= 1; acc += vol[a]
    return ctr[poc], ctr[a], ctr[b], ctr[np.argmax(dlt)], ctr[np.argmin(dlt)], dlt.sum()


def classify_open(rth, pm_high, pm_low):
    o = rth["open"].iloc[0]; first5 = rth.head(5)
    hi5, lo5 = first5["high"].max(), first5["low"].min()
    # open drive: opens and goes one way without returning through open in first 5
    back_through = ((first5["low"] < o) & (first5["high"] > o)).any()
    up_bias = (hi5 - o) > (o - lo5)
    if not back_through and up_bias and hi5 > o*1.002:
        return "Open-Drive UP (conviction long)"
    if not back_through and not up_bias and lo5 < o*0.998:
        return "Open-Drive DOWN (conviction short)"
    if up_bias and rth.head(15)["low"].min() < o:
        return "Open-Rejection-Reverse (popped, sold back)"
    return "Open-Auction (two-sided, low conviction)"


def daytype(rth):
    o, c = rth["open"].iloc[0], rth["close"].iloc[-1]
    hi, lo = rth["high"].max(), rth["low"].min()
    rng = hi - lo
    close_loc = (c - lo)/rng if rng else .5
    open_loc = (o - lo)/rng if rng else .5
    ext = abs(c - o)/rng if rng else 0
    if ext > 0.7 and (close_loc > 0.85 or close_loc < 0.15):
        return f"TREND day ({'up' if c>o else 'down'}) — open & close at opposite extremes"
    if ext > 0.45:
        return f"Normal-Variation ({'up' if c>o else 'down'}) — directional with rotation"
    return "Balanced/Neutral — rotational, little net progress"


print(f"{'='*78}\nTSLA WEEK AUCTION DECODE — Jun 29 -> Jul 2 2026 (bin ${BIN})\n{'='*78}")
prev_va = None
for day in DAYS:
    m = load(day); pre = m[m.tod < "09:30"]; rth = m[(m.tod >= "09:30") & (m.tod <= "16:00")]
    pmh, pml = pre["high"].max(), pre["low"].min()
    pmh_t = pre["high"].idxmax()
    o, c = rth["open"].iloc[0], rth["close"].iloc[-1]
    hi, lo = rth["high"].max(), rth["low"].min()
    poc, val, vah, buyd, seld, netd = vprofile(rth)
    ib = rth.head(60); ib_hi, ib_lo = ib["high"].max(), ib["low"].min()
    ext_up = hi - ib_hi; ext_dn = ib_lo - lo
    pop = rth.head(3)["high"].max()
    chg = (c/PRIOR_CLOSE[day]-1)*100
    print(f"\n### {day}   {chg:+.2f}%   O {o:.2f}  H {hi:.2f}  L {lo:.2f}  C {c:.2f}")
    print(f"  PRE-MKT: high {pmh:.2f}@{pmh_t:%H:%M} low {pml:.2f} | open {o:.2f} = {(o/pmh-1)*100:+.1f}% vs PM high")
    print(f"  OPEN TELL: pop {pop:.2f} vs PM high {pmh:.2f} = {(pop/pmh-1)*100:+.1f}% -> "
          + ("CHALLENGED/exceeded PM high (buyers in control)" if pop >= pmh
             else "FAILED to challenge PM high (sellers capping)"))
    print(f"  OPEN TYPE: {classify_open(rth, pmh, pml)}")
    print(f"  DAY TYPE:  {daytype(rth)}")
    print(f"  INITIAL BALANCE (first hr): {ib_lo:.2f}-{ib_hi:.2f} | range ext up {ext_up:+.2f} dn {ext_dn:+.2f}")
    print(f"  PROFILE: POC {poc:.2f}  value {val:.2f}-{vah:.2f}  | buy-delta@ {buyd:.2f}  sell-delta@ {seld:.2f}  netDelta {netd/1e6:+.1f}M")
    if prev_va:
        loc = ("ABOVE prior value (higher acceptance)" if o > prev_va[1]
               else "BELOW prior value (lower acceptance)" if o < prev_va[0]
               else "INSIDE prior value (balance)")
        print(f"  OPEN vs prior-day value {prev_va[0]:.2f}-{prev_va[1]:.2f}: {loc}")
    prev_va = (val, vah)
