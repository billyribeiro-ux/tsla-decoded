# Triple-Barrier GBM FlowForensics (tbgbm) — results

- Data: 2021-01-04 09:30:00 .. 2026-07-02 15:59:00, 1380 RTH days, 536,394 1-min bars (2021+ only)
- CUSUM k=15.0, EWMA span=60, barriers pt=sl=2.0, cost gate + subtraction 6.0 bps rt
- Purged+embargoed walk-forward on calendar quarters, embargo 390 bars, 1000 block-shuffle nulls

## Variants (IN-SAMPLE vs OUT-OF-SAMPLE)

| variant | events | eff-N | IS AUC | OOS AUC | folds | fired | OOS exp (net bps) | hit | null mean | p-value |
|---|---|---|---|---|---|---|---|---|---|---|
| 3class_vert30 | 4226 | 4226 | 0.672 | 0.516 | 19 | 3638 | -5.28 | 49.42% | -5.93 | 0.085 |
| 3class_vert60 | 4226 | 4226 | 0.676 | 0.508 | 19 | 3635 | -5.91 | 47.51% | -5.89 | 0.520 |
| meta_vert30 | 4226 | 4226 | 0.650 | 0.523 | 19 | 496 | -3.92 | 51.21% | -5.81 | 0.074 |
| meta_vert60 | 4226 | 4226 | 0.635 | 0.530 | 19 | 388 | -5.55 | 45.62% | -6.00 | 0.371 |

## Baseline (shipped FlowForensics rule)
- Hand-tuned ~8-threshold conjunction, ~0.2 signals/day, mean +0.31%/signal managed, p=0.45 (statistically dead, ~3-4 independent events).

## Cost sensitivity (headline `meta_vert30`, gross = net + round-trip cost)
- Gross OOS expectancy ≈ +2.1 bps/trade (before cost). Net of cost:
  - 4 bps rt  -> -1.9 bps/trade  (loses)
  - 6 bps rt  -> -3.9 bps/trade  (loses)
  - 10 bps rt -> -7.9 bps/trade  (loses)
- The gross edge (~2 bps) never clears a realistic round-trip cost floor (≥4-6 bps).
  COST DOES NOT SURVIVE for any variant.

## Interpretation — HONEST VERDICT: no cost-surviving edge
- Sample: CUSUM lifted usable events from the rule's ~0.2/day (≈3-4 independent) to
  3.07/day = 4,226 events. Declustering makes them essentially non-overlapping, so
  average-uniqueness effective-N ≈ 4,226 — a ~1000x increase in independent N. The
  claim is now TESTABLE; that is the deliverable.
- Overfit is real and measured: IS AUC 0.65-0.68 collapses to OOS AUC 0.51-0.53
  (drop 0.13-0.17). The low-capacity GBM still cannot generalize — classic
  non-stationarity at 1-min TSLA.
- OOS net-of-cost expectancy is NEGATIVE for all 4 variants (-3.9 to -5.9 bps/trade).
- Block-shuffle null (1000 day/block permutations): best p=0.074 (`meta_vert30`),
  none < 0.05. Every OOS expectancy sits INSIDE the null band. After a multiple-testing
  haircut over the {3class,meta}x{30,60}x{pt,cost} grid, nothing survives.
- Consistent with the shipped rule's own p=0.45. Conclusion: at 1-min resolution this
  tick-rule/flow-proxy feature set carries NO statistically significant, cost-surviving
  predictive edge for TSLA. The model SAYS SO — which is strictly more information than
  the unvalidated rule provided. This is a valid, reportable negative finding, not a bug.
