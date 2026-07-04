# How to Capitalize on the Hidden-Distribution Finding

## The honest constraint first

**thinkorswim does not give thinkScript order flow.** A thinkScript study sees
OHLCV bars only. It cannot read the order book, trade-by-trade aggressor side, or
icebergs. thinkorswim *shows* Level II and Time & Sales as **display windows**, and
has a built-in **Volume Profile (Monkey Bars/TPO)** study — but the depth/flow data
is **not scriptable**. The iceberg distribution we decoded required MBP/MBO data
(your Databento feed). **You cannot detect the iceberg directly in thinkScript.**

## The insight that makes it tradeable anyway

You don't profit from *seeing* the iceberg — you profit from *reacting to the price
pattern it creates.* The hidden July 2 distribution left a **visible OHLCV shadow**:

1. A **high-volume push into a session high that gets rejected** (big upper wick,
   closes off the high) — the passive seller capping the move. That was the 09:31
   bar: 4.6× volume, closed $2 off its 432.35 high.
2. Then **VWAP is lost and successive elevated-volume bars close below it** — the
   distribution cascade (09:32–09:40, every bar high-volume, weak, below VWAP).

Both are fully computable from bars. I verified the **distribution-footprint score
ranked July 2 #1 of the four days (67 vs <27)** — clean separation — and the exact
SELL rule below fires **only on July 2, at 09:32**, silent on the three up days.

## The two indicators (in `thinkscript/`)

- **`FlowForensics_Absorption.ts`** (upper) — marks the **rejection/absorption bar**
  (orange dot: high-volume rejection at a session high = the iceberg's shadow) and
  fires a **SELL** when that rejection is confirmed by a VWAP loss on a distribution
  bar. Anchored VWAP, alerts, works on any intraday timeframe.
- **`FlowForensics_Absorption_Panel.ts`** (lower) — a **footprint meter**: relative
  volume weighted by wick-rejection and below-VWAP weak closes. **Red = supply /
  distribution, green = demand / accumulation.** Watch it spike red as price tests a
  high → a large passive seller is most likely working the offer.

### Validation (Python mirror, cached 1-min)
- **SELL fires 2026-07-02 @ 09:32** — ~$427, minutes into the −8% day, near the top.
- **Zero fires** on Jun 29 / 30 / Jul 1 (the accumulation days).
- **Baseline 0.2 signals/day** — highly selective (it needs the rejection *and* the
  VWAP-loss confirmation).

### How to trade it (the setup, not financial advice)
Best on a **known-catalyst day** (earnings, delivery/production numbers, big
guidance) after a **multi-day run-up** — that's when a large holder has a reason and
the liquidity to distribute. The signal: **price gaps up / makes its high in the
first minutes, the footprint panel flashes red, the absorption dot prints at the
high, then the SELL fires as VWAP breaks.** Short the confirmation; the July 2
analog gave ~$427 entry into a close at $393. Manage with a stop above the rejection
high and cover into the VWAP-distance stretch or a green-footprint flip.

## If you want to see the *actual* iceberg (real order flow)

thinkScript can't, but these can — worth it if you trade this pattern seriously:
- **Bookmap** — order-book *heatmap*; an iceberg refresh is literally visible as a
  persistent bright band on the offer. This is the closest to what we reconstructed.
- **Sierra Chart** / **Quantower** / **Jigsaw** — footprint (bid/ask volume per
  price) and DOM ladders with a depth feed.
- **Your Databento key** — you already have the exact data (MBP-10/MBO). A small
  custom script (like `scripts/orderbook_depth.py`) can compute live book imbalance
  and iceberg-refresh alerts outside thinkorswim. That's the institutional path, and
  you're already holding the feed.

## Honest caveats

This is the footprint of **one** decoded event, validated on one week plus a short
baseline. The absorption logic is mechanically sound and maps directly to the
order-book truth we verified — but backtest it through thinkorswim's strategy report
over many catalyst days and symbols before risking money. The footprint is a
*proxy* for order flow, not order flow. **Not investment advice.**
