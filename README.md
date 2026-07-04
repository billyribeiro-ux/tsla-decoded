# tsla-decoded

Forensic decomposition of TSLA price action for the week of **2026-06-29 → 2026-07-02**
(the last session before the July 4 holiday weekend), built on the Financial Modeling Prep API.

The pipeline answers two questions with evidence-weighted confidence scores:

1. What caused the **July 2 sell-off** (−8.1% on ~74M shares)?
2. What caused the **intraday spikes** during June 29 – July 2?

## Method

- **Event detection** — intraday-seasonality-adjusted robust z-scores (median/MAD per bar-of-day
  over a 40-day baseline), PELT changepoint detection on returns and realized volatility,
  anchored-VWAP drift detection, and overnight-gap detection.
- **Market decomposition** — OLS of TSLA 5-minute returns on SPY and QQQ (HAC errors) to split
  each event into market-driven vs TSLA-idiosyncratic components.
- **Catalyst alignment** — every press release, news article, analyst action, and economic
  release is normalized, time-aligned to event windows, and scored by
  `source_weight × relevance × recency`; the Q2 vehicle-delivery release gets a dedicated check.
- **ML attribution** — gradient-boosted permutation importance over abnormal-return bars,
  OHLCV order-flow proxies (tick-rule signed volume, close-location value), and K-means
  intraday regime clustering.
- **Iterative loop** — unresolved events escalate through finer resolution (1-min), wider
  catalyst windows, macro/cross-asset checks, and insider-trade sweeps until every major event
  reaches confidence ≥ 0.70 or evidence stops improving.

## Run

```bash
cp .env.example .env       # put your FMP_API_KEY in .env (never committed)
pip install -r requirements.txt
python run.py              # add --refresh to bypass the JSON cache
pytest tests/              # synthetic-data sanity tests
```

Outputs land in `output/`: `report.md`, `charts/*.png`, and an interactive `dashboard.html`.

## FlowForensics — thinkorswim indicator (thinkscript/)

The measured signatures compiled into thinkScript for thinkorswim, validated
bar-for-bar against the cached 1-minute data (`python run.py --signals`,
results in `output/signal_validation.md`):

| file | chart | what it does |
|---|---|---|
| `FlowForensics_Signals.ts` | intraday (1/5-min) upper | BUY/SELL arrows: Jun-29 accumulation signature (above anchored VWAP, imbalance ≥ +0.20, swelling volume, strong closes, day signed volume at highs) and Jul-2 signatures (gap-up rejected below prior-session VWAP with day imbalance ≤ −0.30, or below-VWAP distribution with failed reclaim); VWAP cloud, labels, alerts, v1.1 audit gates |
| `FlowForensics_Flow.ts` | intraday lower | the order-flow evidence panel **with the same BUY/SELL arrows**: zone-colored imbalance histogram, day-anchored imbalance, relative volume, thresholds |
| `FlowForensics_Strategy.ts` | intraday, Strategies tab | AddOrder backtest version: long + optional short, profit target, VWAP-cross stop, auto-flatten 15:55 |
| `FlowForensics_Daily.ts` | daily upper | daily translations: BUY = accumulation day (close in top quartile, volume > 1.15× 20d, positive 10d flow, above 10-EMA, not extended); SELL = gap-up key reversal after ≥8% run-up, or heavy-volume breakdown below prior low |
| `FlowForensics_Daily_Flow.ts` | daily lower | daily flow panel with the same signals: 10d imbalance histogram, relative volume, 3-day run-up vs gates |

Daily validation: on 64 sessions (Apr–Jul 2026) exactly two daily signals
fired — BUY on 2026-06-29 and SELL (key reversal) on 2026-07-02.

Install: thinkorswim → Charts → Studies → Edit Studies → Create → paste the
file contents → OK (strategy goes under the Strategies tab). Suggested setup:
1-min or 5-min chart, regular trading hours.

Validated event capture with shipped defaults (v1.1, post-audit gates: 15:00
BUY cutoff, 3-day run-up gate, prior-session-VWAP context for opening
rejections): SELL fired 2026-07-02 **09:35** (the −8% day, minutes into the
liquidation), BUY fired 2026-06-29 **10:33** (the +8% accumulation day),
0.67 signals/day on the quiet baseline; target-week signals 88% profitable
to session close (see `output/signal_validation.md` for the audit). These
rules encode one measured week + a 2-week baseline on one symbol — run the
strategy report over longer history before trusting them. Not investment advice.

## Honesty note

Causal attribution in markets is probabilistic. The report assigns each event a numeric
confidence and lists competing hypotheses rather than claiming false certainty.
