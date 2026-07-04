# TSLA Intraday Decode — June 29 → July 2, 2026

The week at **execution resolution**: not just *what* the flow was, but *when
inside each session* it fired. Net delta (tick-rule signed volume) by 30-minute
block, from extended-hours 1-minute bars. The intraday timing reveals the single
most telling thing about the whole campaign — **the buyer had time, the seller did
not.**

---

## The core finding: patient accumulation, urgent distribution

| | Monday (build) | Thursday (unwind) |
|---|---|---|
| Full-day net delta | **+10.0M** | **−10.6M** |
| **Shape** | **spread across all day** | **front-loaded into hour 1** |
| Biggest block | 09:30 (+2.0M) then a steady bid | **10:00 (−5.5M), imb −0.63** |
| First 60 min | +3.1M (27% of day) | **−9.1M (86% of day)** |
| Blocks in flow direction | **12 of 14 green** | 5 of first 6 red |
| Into-the-close (15:00–16:00) | still **buying** (+1.7M) | small bounce (+2.0M cover) |

**Monday's buyer fed the position in all session long** — 12 of 14 thirty-minute
blocks were net-positive, a relentless bid that bought every dip from 9:30 to the
close. That is how you *build* size without shoving the price against yourself: you
spread it across the whole day. **Thursday's seller did the opposite** — it dumped
−9.1M in the **first hour** (86% of the day's selling), with a −0.63 imbalance at
10:00 that is about as one-sided as a real tape gets. That is how you *exit* when
the catalyst is public and everyone is watching: you hit the bids immediately, into
the opening liquidity, before price falls further.

**Accumulation had days of runway before a known catalyst, so it was patient.
Distribution had one window — the good-news liquidity at the open — so it was
violent.** The *timing signature* alone tells you build-vs-exit, independent of
price.

---

## Day-by-day intraday execution

### Monday June 29 — the build (+10.0M, patient all-day bid)
```
09:30  +2.0M  imb +0.31   px 391.84   ← opening drive, immediate demand
12:00  +1.3M  imb +0.43   px 403.98   ← lifting offers mid-day
13:00  +1.3M  imb +0.39   px 408.80
14:30  +1.0M  imb +0.36   px 410.29
15:00  +0.9M  imb +0.25   px 411.98   ← STILL buying into the close
15:30  +0.8M  imb +0.15   px 411.59
```
A bid under the market the entire session. The buy-delta concentrated **at the
highs** ($409 zone), and the buyer was **still accumulating into the close** — a
strong institutional tell (get the position on before end of day). Twelve green
blocks out of fourteen. Nothing about this is retail chasing; it's a program
working an order.

### Tuesday June 30 — continuation, first crack (+2.7M)
```
14:30  +1.2M  imb +0.40   px 422.02   ← last real buy push
15:30  −1.2M  imb −0.29   px 420.32   ← FIRST distribution into the close
```
Still net-buying, but a **quarter** of Monday's force — and the day ended with the
**first meaningful sell block (−1.2M into the close)**, the mirror image of Monday's
buy-into-close. The hand-off was beginning.

### Wednesday July 1 — the top tick, in real time (+0.8M)
```
11:00  +2.0M  imb +0.46   px 431.87   ← buy spike prints the WEEK HIGH (432.85)
11:30  −0.8M  imb −0.33   px 428.41   ← immediately sold
12:00 → 14:00 : net NEGATIVE every block  ← 2.5 hours of distribution
```
This is the exact top, caught in the flow. A +2.0M buy spike at 11:00 drove the
**high of the entire week ($432.85)** — and was **instantly distributed**, followed
by 2½ hours of net selling. A new high made on a buy spike and then sold is the
**bull trap**, and the net-delta shows it happening minute for minute. Net delta
for the whole day collapsed to +0.8M: buyers and sellers now matched — the crowd
buying the high while size sold it.

### Thursday July 2 — the unwind (−10.6M, front-loaded liquidation)
```
09:30  −3.6M  imb −0.40   px 413.05   ← delivery beat (9:05) sold from the open
10:00  −5.5M  imb −0.63   px 401.60   ← the heaviest, most one-sided block of the week
12:00  −2.1M  imb −0.52   px 392.94   ← second wave
15:00  −0.9M  imb −0.31   px 391.24   ← probes the low
15:30  +2.0M  imb +0.42   px 393.24   ← late short-cover / dip-buy bounce
```
−9.1M in the first hour. The 10:00 block's **−0.63 imbalance** is the fingerprint of
a large seller hitting every bid into the opening liquidity the good news created.
A second wave at noon (−2.1M) finished the job; the late +2.0M is a small
short-cover bounce into the close, not real demand.

---

## The opening sequence, every day (the pre-market-high tell)

| Day | PM high | Open pop | Challenged? | What followed |
|-----|---------|----------|-------------|---------------|
| Mon | 384.59 | 386.46 | **yes ✓** | trend up, +10M bid all day |
| Tue | 412.30 | 410.60 | **failed ✗** | up but conviction halved |
| Wed | 421.50 | 425.18 | yes, **hollow** | made week high, then sold — trap |
| Thu | 438.29 | 432.35 | **failed ✗** | −10.6M liquidation |

Every session was an **Open-Rejection-Reverse** (pop at the open, sold back into
range). On the up days the pullback was *absorbed* by the standing bid and price
pushed on; by Thursday the same opening pop met **no absorption** and became the
high of the day. **The opening pattern never changed — the net delta underneath it
flipped from +10M to −10.6M.** Same shape, opposite outcome.

---

## VWAP control, session by session

| Day | Time above anchored VWAP | Read |
|-----|--------------------------|------|
| Mon | ~99% | buyers owned the auction |
| Tue | ~98% | still buyers, tiring |
| Wed | ~56%, 18 VWAP crosses | genuine fight — the balance/top |
| Thu | ~1% | sellers owned it from bar one |

Wednesday's VWAP fight (56%, price crossing it 18 times) is the same top the delta
and day-type flagged — three independent measures pointing at the same session as
the hinge.

---

## What the intraday timing proves

1. **It was one position, built then unwound** — +10.0M Monday vs −10.6M Thursday,
   nearly share-for-share.
2. **The build was patient (all-day bid, buying into the close), the exit was urgent
   (86% in hour one)** — the timing signature of accumulate-ahead-of-catalyst,
   dump-into-the-news.
3. **The top is timestamped: Wednesday 11:00**, a buy spike to the week high
   instantly distributed, then 2½ hours of net selling.
4. **Thursday's selling began at the open right after the 9:05 delivery print** — the
   good news was the trigger to exit, executed into its own liquidity.
5. **The pre-market-high tell and the VWAP control agreed with the delta at every
   hinge** — four independent lenses, one story.

**The intraday tape doesn't just show that Tesla was accumulated and distributed —
it shows the accumulation was unhurried and the distribution was a race for the
exit, which is exactly what "smart money positions early and sells the news" looks
like at execution resolution.**

*Reproduce: `python scripts/intraday_blocks.py` (extended-hours 1-min per day).
Not investment advice.*
