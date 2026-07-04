# TSLA Jun 29 – Jul 2, 2026 — Volume-Profile / Auction Decode

The market read through **volume at price**, not time: Point of Control (POC, the
single most-traded price), Value Area (the 70% of volume around POC → VAH/VAL),
high/low-volume nodes (shelves and cliffs), naked POCs, and **delta-at-price**
(net buying vs selling by level). Built by distributing each 1-minute bar's
volume — and its tick-rule signed volume — uniformly across the bar's high-low
range into $0.50 bins.

*Honest limit: a true footprint (bid/ask imbalance per price) needs tick data
with trade direction, which no OHLCV feed carries. Delta here is the tick-rule
approximation (sign of close-to-close). It is directionally reliable, not exact.*

## The POC migration — the spine of the whole week

| Day | POC | Value Area | Read |
|-----|-----|-----------|------|
| Mon Jun 29 | **$409.25** | 396.75 – 413.25 | value builds off the lows |
| Tue Jun 30 | **$415.25** ↑ | 413.75 – 422.75 | value accepted higher |
| Wed Jul 1 | **$426.25** ↑ | 424.25 – 428.75 | value accepted higher again — but this is the top |
| Thu Jul 2 | **$391.25** ↓↓ | 390.25 – 401.25 | value **collapses ~$35** below where it had been |

Three sessions of the POC stair-stepping **up** ($409 → $415 → $426) is textbook
healthy accumulation: each day the market did most of its business a little
higher and *accepted* it. Then July 2 didn't just pull back — the POC **teleported
down to $391.25, below Monday's entire value area ($396.75 low).** In one session
the market relocated its "fair price" beneath where the whole week's accumulation
had happened. That is not a dip. That is the auction rejecting everything it built.

## The single most important number: the week's composite POC is $391.25

The most-traded price of the **entire week** is $391.25 — exactly where July 2
closed and bottomed. Because July 2 carried the week's heaviest volume (74M
shares), the distribution day *became* the week's center of gravity. When the
fairest price of the week by volume is the crash-day low, the selling wasn't a
wick — it was where the business got done.

## Acceptance, not a flush — the subtlety that matters

July 2's POC sits at the **low end of its range** ($391.25, right by the $389.34
low), with a fat shelf of volume at $390.75–391.75. This is the decisive
distinction:

- A **liquidity flush** (panic air-pocket) leaves the POC **high** with a thin
  single-print tail stabbing down — price spikes down and snaps back.
- July 2 did the opposite: **enormous volume traded down at the lows and price
  stayed there.** The market *accepted* the lower prices. Acceptance is a far
  stronger, more deliberate signal than a flush — it confirms **distribution**
  (planned unloading) over a stop-run.

This aligns with the earlier microstructure finding (below-normal price impact =
orderly selling): the profile shows *where* that orderly selling was absorbed.

## Delta-at-price — where buyers and sellers actually stood

- **Buy delta (green)** concentrates **$396–$416** — the Mon–Wed accumulation
  zone. That's where the position was built.
- **Sell delta (red)** concentrates in two places: **$418–$426** (distribution
  into Wednesday's highs — they sold the top they made) and **$390–$391** (final
  capitulation). 
- Green delta reappears at **$391–$397 on July 2** — dip-buyers stepping in and
  being **absorbed** by the larger sell flow. They caught a falling knife into the
  distribution.

## Structure left on the chart

- **Low-Volume Node / cliff below $390:** the profile thins out sharply under $390.
  Once $390 broke there was almost no volume shelf beneath it — which is *why* the
  low extended to $389.34 fast and *why* $390 was defended into the close.
- **Naked POC overhead at $426.25 (Wed):** after July 2's open, price never
  returned to Wednesday's point of control. It sits "naked" above — classic
  unfinished business and a magnet/target on any future rally back up.
- **Value-area rejection at the open:** July 2 opened at $428.12 — *inside*
  Wednesday's value area (424–429) — poked to $432.35, was rejected, and drove
  down through **every** prior value area in one session. Opening inside prior
  value and failing is a well-known short-side tell; this was that, at scale.

## What the auction says the week actually was

Accumulation with rising accepted value Mon–Wed (POC climbing $409→$426, buy
delta building $396–416) → distribution into the Wednesday top and the Thursday
open (sell delta $418–426) → a full value collapse to a new accepted low
(POC $391, week's volume center), dip-buyers absorbed, a cliff opening beneath
$390, and a naked POC left overhead at $426. The profile and the flow tell the
same story from two angles: **positions were built low, sold high into the event,
and value was driven below the entire build zone — deliberate distribution, not a
news-shock flush.**

## The opening tell — the failed challenge of the pre-market high (the black box)

The whole day is decoded by one sequence at the open. Pre-market and cash tape,
minute by minute:

| Time | Price action | What it means |
|------|-------------|---------------|
| **09:00** | pre-market **spikes to $438.29** on 76k (the biggest PM bar) | blow-off top — a **NEW high, +1.3% above the entire cash-session week high** ($432.85), on anticipation + the FSD/probe-closed headlines |
| **09:05** | **delivery beat prints → price immediately drops to $424** | the "good news" was **sold the instant it was public.** Sell-the-news began 25 min *before* the cash open |
| 09:05–09:29 | grinds down to $428.19 | never recovers toward $438; distribution already underway in thin pre-market |
| **09:30** | cash opens **$428.12 — already −2.3% below the PM high** | the distributor had a 30-minute head start in the thin tape |
| **09:31** | opening pop to **$432.35 on 504k** (≈100× a PM bar) | maximum-liquidity buying surge — market-on-open + momentum — **tops $5.94 (−1.4%) BELOW the PM high.** A **lower high.** |
| 09:32+ | rolls over, sells all day | the failed challenge confirmed sellers in control |

**Why this is the signal.** The open is the single biggest liquidity event of the
day — 504k shares in minute one vs 1–4k pre-market bars. That surge *normally*
drags price to at least **test** the pre-market extreme. Here it threw everything
it had and still made a **lower high $6 short of $438.29.** That doesn't mean
buyers were absent — they showed up in force at 9:31 — it means **sellers were
bigger and stacked on the offer, absorbing 100% of the open's buying pressure.**
That is the fingerprint of a large, patient distributor capping every bounce.

The "black box" — a delivery *beat*, a pre-market *new high*, then an 8% *collapse*
— decodes cleanly: pre-market ran to a blow-off top on anticipation → the actual
number printed and was instantly sold → the cash open's biggest-liquidity push
failed to reclaim the PM high (lower high at 9:31) → one-way distribution from
there. **Anyone reading the tape had the short the moment 9:31 failed to challenge
$438.29.** The failed PM-high challenge is the cleanest single confirmation tell of
the entire session.

## Institutional moving averages — it sliced through all three

The 50/100/200-day SMAs are the levels institutional desks defend and buy. Going
into July 2 the stock (Jul-1 close $425.30) sat **above all three**. By the close
it was **below all three** — a full technical regime break in one session:

| SMA (as of Jul 1) | Level | Jul-2 low | Jul-2 close vs SMA | Distance (ATR) |
|-------------------|-------|-----------|--------------------|----------------|
| 50-day  | $406.28 | broke below | **−3.2%** below | −0.7 ATR |
| 100-day | $398.26 | broke below | **−1.2%** below | −0.3 ATR |
| 200-day | $418.69 | broke below | **−6.0%** below | −1.4 ATR |

The **200-day at $418.69 — the single most-watched institutional line — was lost
inside the first ~15 minutes** (price was already through $413 by 9:45). Price
then blew through the 50 and the 100 and *closed beneath all three.* A close below
the 200-day after being above it the prior day is a textbook institutional
regime-change signal — and it means the selling was heavy enough to **overrun every
level where dip-buyers normally step in.** The volume profile confirms who tried:
the green buy-delta at $391–$397 is exactly those dip-buyers — and they were
**absorbed** by the larger sell flow, not rewarded.

## Hard statistics (daily sample, n = 293 sessions)

| Metric | Value | Significance |
|--------|-------|-------------|
| Jul-2 return | **−7.78%** | **−2.61σ**, **0.7th percentile** — a bottom-0.7% tail day |
| Frequency | — | ~**1 in 221** trading days (0.45% under a normal fit) |
| Annualized daily vol | 48% | the −7.8% = a **2.6-sigma** single-day event |
| Volume 73.9M | **+1.8σ** vs 50-day | 51st percentile raw, but heavy vs recent base |
| 3-day run-up into it | **+12.0%** | **96th percentile** — the setup was as extreme as the drop |
| Overnight gap | **+0.64% (UP)** | the entire −8% was **intraday** — again, no overnight news shock |

The two extremes bracket the whole thesis: a **96th-percentile run-up** immediately
followed by a **0.7th-percentile drop**, with the gap *up* — statistically, this is
a stretched-long position violently unwinding intraday, not a market reacting to
fresh bad news. The magnitude (−2.6σ, 1-in-221) rules out ordinary noise; the
intraday-only nature and the run-up context rule in positioning.

*Reproduce: `python scripts/volume_profile.py` → `output/charts/volume_profile.png`;
SMA/stats via `scripts/levels_stats.py`. Not investment advice.*
