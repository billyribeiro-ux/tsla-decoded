# FlowForensics Trade Playbook

How to take trades off the FlowForensics indicators. This is an intraday,
catalyst-day, distribution/accumulation setup — **not** a day-trading system and
**not** investment advice. The edge is real but statistically unproven (3-month
backtest: 17 signals, t=0.78, p=0.45); trade it small, with the stop, on the right
days only.

## SHORT setup — distribution (what July 2, 2026 was)

**1. Context filter — only hunt on these days:**
- A known catalyst that session (earnings, deliveries/production, guidance, major news), AND
- The stock is up multiple days into it (a crowded long to unwind).
- No catalyst + no run-up → skip. This filter is what separates edge from noise.

**2. Signal stack — wait for all of it, in order:**
1. RED CVD divergence dot near the high (`FlowForensics_CVD`) — price up, delta not confirming. Early warning.
2. ORANGE absorption/rejection dot (`FlowForensics_Absorption`) — high-volume bar rejected at the session high (upper wick). The seller appears.
3. Price closes below anchored VWAP and can't reclaim. The trigger.
4. RED SELL arrow fires = all aligned. Entry bar.

**3. Entry:** short on the SELL arrow / VWAP break. (Jul 2: ~09:35, ~$427.)

**4. Stop (mandatory):** just above the rejection-bar high. Reclaim of that high =
thesis dead, get out. (Jul 2: ~$432, ~1.2% risk.) This stop caps the short-squeeze
tail — it turns the backtest's -5% blow-up into a -1% scratch.

**5. Targets (from the volume profile, `scripts/volume_profile.py`):**
- First: 1.5x risk OR the prior-day value-area low / a high-volume shelf below.
- Runner: trail below VWAP; cover into a green-footprint flip or profile support.

**6. Management:** VWAP reclaimed and held → exit. Flatten by end of day.

## LONG setup — accumulation (mirror; Monday, June 29 behavior)

- GREEN CVD divergence dot at a session low (delta holding as price drops), AND
- Green demand footprint, AND
- Price RECLAIMS anchored VWAP = entry.
- Stop below the low; target the prior POC / value-area high above.

## Risk rules (more important than the entry)

- Risk <= 0.5% of the account per trade. Unproven edge = small size.
- Paper-trade one month first; confirm the stack completes and fills are real.
- The stop is non-negotiable every time — one squeeze without it erases months.
- Selective: ~0.2 signals/day. One or two trades, not ten. Forcing it on quiet
  days = off-script and negative expectancy.

## What the tools are (and are not)

- `FlowForensics_CVD` divergence = OHLC-approximated delta, not true order flow.
- `FlowForensics_Absorption` = the OHLCV footprint of hidden distribution.
- None of these see the actual order book / iceberg (thinkScript can't). They trade
  the *shadow* the distribution leaves in the bars. For the real book: Bookmap,
  Sierra Chart, or your Databento feed.

*Backtest reality: mean +0.31%/signal stop-managed, 53% win, +5.3% cumulative over
3 months before costs. A directional lean to harvest with discipline, not an ATM.
Not investment advice.*
