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

## Honesty note

Causal attribution in markets is probabilistic. The report assigns each event a numeric
confidence and lists competing hypotheses rather than claiming false certainty.
