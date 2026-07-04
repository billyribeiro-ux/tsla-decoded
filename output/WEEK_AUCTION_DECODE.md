# TSLA Full-Week Auction Decode — June 29 → July 2, 2026

Every session read the same way July 2 was: pre-market tell, opening type,
initial balance & range extension, Market-Profile day type, POC / value area,
and **net delta** (tick-rule signed volume). Built from extended-hours 1-minute
bars. The four days are not four events — they are **one position, built and
unwound**, and the numbers prove it.

## The week on one screen

| | Mon Jun 29 | Tue Jun 30 | Wed Jul 1 | Thu Jul 2 |
|---|---|---|---|---|
| **Result** | **+8.4%** | +2.1% | +1.1% | **−7.6%** |
| **Day type** | **TREND UP** | Normal-Var up | **BALANCED** | **TREND DOWN** |
| **Open vs PM high** | challenged ✓ | **failed ✗** | challenged ✓ | **failed ✗** |
| **Range extension** | +16.6 **up** | +8.2 up | +5.2 up | +11.7 **down** |
| **POC** | 409.25 | 415.25 ↑ | 426.25 ↑ | **391.25 ↓↓** |
| **Net delta** | **+10.0M** | +2.7M | +0.8M | **−10.6M** |
| **Open vs prior value** | — | inside | inside | inside |

## The killer number: the delta round-trip

**Monday's net delta was +10.0M signed shares. Thursday's was −10.6M.** The
buying that built the position Monday was unwound almost share-for-share Thursday.
The whole week nets to just +2.9M — meaning **~10 million shares were accumulated
and then ~10 million distributed.** The price echoes it: +8.4% Monday, −7.6%
Thursday — a near-perfect round trip. This isn't four separate days reacting to
four separate things. It's **one campaign: accumulate Monday, distribute Thursday,
back to start.**

## The day-type progression is a textbook distribution top

**TREND UP → Normal-Variation → BALANCED → TREND DOWN.** That exact sequence is
how tops form:

1. **Mon — TREND UP (the build).** Opens at the low (379.30), closes at the high
   (411.48), range extension **+16.6 up and 0.0 down** — pure one-directional
   conviction. Net delta **+10.0M**, and the buy-delta sits at **$409.25 — the
   highs.** They weren't bottom-fishing; they were *lifting offers near the top of
   the range*, the signature of urgent, informed accumulation. The open even
   **challenged and exceeded the pre-market high** — buyers in control from bar one.

2. **Tue — Normal-Variation up (the continuation, weakening).** Still up, still
   net-buying (+2.7M) — but that's **a quarter of Monday's conviction**, and the
   open **failed to challenge the pre-market high** for the first time. Sell-delta
   appears at **$423.75, the top of the day's range** — the first distribution
   into strength. First crack.

3. **Wed — BALANCED / NEUTRAL (the top).** The week's **high prints here (432.85)**
   — and the day goes nowhere (rotational, net delta collapses to **+0.8M**). A
   balanced day after two up days, on the high, with buying pressure gone, is
   **distribution disguised as consolidation.** The crowd is now doing the buying
   while size quietly sells — net delta near zero is exactly what that looks like.
   The open challenged the PM high but couldn't hold it: **a new high that failed =
   the bull trap.**

4. **Thu — TREND DOWN (the unwind).** Opens near the high, closes near the low,
   range extension **+11.7 down**. Net delta **−10.6M**. Pre-market blow-off to
   438.29, open fails the PM-high challenge (432.35 lower high), and value collapses
   to POC **$391.25** — below the entire week's build zone. The position is gone.

## The pre-market-high tell, across the week

The signal you flagged on Thursday was live **all week** and it called every turn:

- **Mon: challenged ✓** → trend up followed.
- **Tue: failed ✗** → first warning; day still rose but conviction halved.
- **Wed: challenged ✓ but balanced** → a *hollow* challenge — made the high, no
  follow-through. The most dangerous kind: a new high nobody defended.
- **Thu: failed ✗** → the break. Trend down.

Two failed PM-high challenges (Tue, Thu) bracketed the top; the one "success" (Wed)
was a trap that printed the high and died. **The open's relationship to the
pre-market high was the week's tell, not just Thursday's.**

## Every day was an "Open-Rejection-Reverse" — and that's the point

The open type came back **Open-Rejection-Reverse every single session** — price
popped at the open and got sold back into range each day. On the up days buyers
absorbed the pullback and pushed on; by Thursday the same opening pop found **no
absorption** and became the high of the day. Same opening behavior, opposite
outcome — because the *net delta* underneath flipped from +10M to −10.6M. The
opening pattern was constant; **who was on the other side of it changed.**

## POC migration — the value staircase and the cliff

$409.25 → $415.25 → $426.25 (three days of value stair-stepping **up**, healthy
acceptance higher) → **$391.25** (a $35 collapse below the whole build). Value was
accepted higher for three days, then relocated beneath everything in one — the
auction rejecting three days of work in a single session.

## The one-line verdict

The week was a **complete accumulation-distribution round trip**: ~10M shares
bought on a Monday trend day into the highs, held through a weakening Tuesday and a
balanced-top Wednesday, then ~10M shares dumped on a Thursday trend day — the delta
symmetric, the price symmetric, the day-types a copybook top, and the pre-market-
high tell flashing at every hinge. Not four days of news; **one trade.**

*Reproduce: `python scripts/week_auction.py` (needs extended-hours 1-min per day).
Not investment advice.*
