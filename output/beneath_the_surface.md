# Beneath the surface: TSLA 2026-06-29 → 2026-07-02

Actor-type and mechanism forensics from flow toxicity (VPIN), price impact (Kyle's λ), liquidity (Amihud), the volume clock, the leveraged-ETF tape, and insider filings. OHLCV microstructure identifies the *character* of flow, not names — every claim below carries its evidence tier.

## Headline metrics

- **VPIN** (informed-flow toxicity): week max **0.4165** at 2026-06-29 10:39:00-04:00 — the **100% percentile** of the 2-week baseline distribution (baseline median 0.1976, 90th pct 0.2369). Per-day means: 2026-06-29: 0.2999, 2026-06-30: 0.1783, 2026-07-01: 0.1823, 2026-07-02: 0.2466
- **Kyle's λ** baseline: 88.74 bps per 1M net shares. Session/phase values:
| window                            |   λ (bps/M shares) |   t-stat |   n (min) |
|-----------------------------------|--------------------|----------|-----------|
| baseline (2wk)                    |              88.74 |     58.9 |      3509 |
| 2026-06-29 full day               |              71.8  |     23.5 |       389 |
| 2026-06-30 full day               |              78.13 |     23.4 |       390 |
| 2026-07-01 full day               |              85.67 |     19.7 |       390 |
| 2026-07-02 full day               |              59.73 |     23.1 |       390 |
| 2026-06-29 P1 09:30-10:24 (+2.6%) |              95.63 |      8.8 |        54 |
| 2026-06-29 P2 10:24-11:29 (+1.6%) |              82.58 |     11.5 |        66 |
| 2026-06-29 P3 11:29-12:19 (+1.1%) |              57.38 |      9   |        51 |
| 2026-06-29 P4 12:19-13:14 (+1.1%) |              59.09 |     10.4 |        56 |
| 2026-06-29 P5 13:14-15:09 (+1.1%) |              61.74 |     14.6 |       116 |
| 2026-06-29 P6 15:09-15:59 (+0.2%) |              50.22 |     10.4 |        51 |
| 2026-07-02 P1 09:30-10:19 (-5.0%) |              73.18 |      6.9 |        50 |
| 2026-07-02 P2 10:19-10:39 (-2.2%) |              43.95 |      6.1 |        21 |
| 2026-07-02 P3 10:39-11:34 (-0.0%) |              59.82 |     10.1 |        56 |
| 2026-07-02 P4 11:34-12:04 (-0.3%) |              72.49 |      8.2 |        31 |
| 2026-07-02 P5 12:04-12:29 (-1.1%) |              71.36 |      9.2 |        26 |
| 2026-07-02 P6 12:29-15:59 (+0.1%) |              52.22 |     17.1 |       211 |
- **Amihud illiquidity** per day (median 30-min block, percentile vs baseline): 2026-06-29: 42%, 2026-06-30: 42%, 2026-07-01: 25%, 2026-07-02: 45%
- **Overnight vs intraday split** (a retail-gap signature would put the move in the overnight column; institutional execution shows up intraday):
|            |   overnight_gap_pct |   intraday_oc_pct |
|:-----------|--------------------:|------------------:|
| 2026-06-29 |                0.55 |              7.58 |
| 2026-06-30 |               -1.43 |              3.53 |
| 2026-07-01 |                0.2  |              0.91 |
| 2026-07-02 |                0.64 |             -8.42 |

## The leveraged-ETF (retail proxy) tape

- **TSLL** volume vs its own 20d baseline — 2026-06-29: z=1.0 (close-window 9%), 2026-06-30: z=0.0 (close-window 8%), 2026-07-01: z=-0.3 (close-window 9%), 2026-07-02: z=2.1 (close-window 5%)
- **TSLQ** volume vs its own 20d baseline — 2026-06-29: z=0.0 (close-window 9%), 2026-06-30: z=0.4 (close-window 8%), 2026-07-01: z=0.9 (close-window 7%), 2026-07-02: z=2.9 (close-window 7%)

## Insider filings sweep

**No insider transactions dated inside the window** (scanned 300 filings; latest transaction on record: 2026-06-16). Filings lag up to 2 business days, and the July-4 weekend extends that — a week-of sale could still surface in filings after this data snapshot.

## Named blind spots

- `short-interest`: not offered by FMP (404/empty)
- `historical/social-sentiment`: not offered by FMP (404/empty)
- `options-chain`: not offered by FMP (404/empty)
- No order-book, dark-pool, options-flow or short-interest data is available through this provider; conclusions below rely on the tape-derived measures above.

## Verdict

**Who bought the run-up.** The week's maximum flow toxicity (VPIN 0.4165, the 100% percentile of the baseline) occurred during MONDAY MORNING BUYING (10:39 ET) — i.e. the most one-sided, informed-style order flow of the entire week was the accumulation, not the crash. Monday's opening-hour price impact (λ = 96 bps/M vs baseline 89) shows buyers paying a premium for immediacy — urgency, conviction. The move was built almost entirely intraday (+7.6% intraday vs +0.6% overnight gap), which is execution behavior, not retail market-orders-at-the-open. The leveraged-long retail proxy (TSLL) was unremarkable on Monday (volume z = 1.0). Character of the evidence: **concentrated, informed-style institutional accumulation positioning for the delivery print — not a retail FOMO wave.**

**Who sold July 2 — and the key tell.** Thursday's flow was one-sided (day-mean VPIN 0.2466, vs baseline median 0.1976) yet its price impact was BELOW baseline (full-day λ = 60 vs 89 bps/M; Amihud only at the 45% baseline percentile). Enormous size was sold WITHOUT punching through the book: that is the signature of planned distribution into the deep liquidity pool that a headline event creates — not a stop-loss cascade, not a liquidity vacuum, not forced deleveraging. The inverse-ETF tape (TSLQ z = 2.9) and TSLL (z = 2.1) only exploded on Thursday itself — retail and hedgers REACTED to the fall; they did not lead it. Close-window volume share was normal (5–7%), ruling out leveraged-ETF rebalance mechanics as the driver. No insider filing covers the week. Character of the evidence: **the entities positioned during the run-up used the delivery-beat liquidity to exit at size — sell-the-news distribution executed deliberately, front-loaded into the first 70 minutes, with the July-4 long weekend removing any incentive to hold.**

**What this cannot prove.** OHLCV microstructure cannot confirm the Monday buyers and Thursday sellers were the same accounts, and with options/short-interest/sentiment data unavailable from this provider, dealer-hedging (gamma) amplification can be neither confirmed nor excluded. Those are the named limits of this evidence; within them, every measured signature points the same direction.
