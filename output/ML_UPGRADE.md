# FlowForensics ML Upgrade — Multi-Agent Audit & Evidence Verdict

*Produced by a parallel Opus-4.8 workflow (14 agents: 4 auditors, 4 designers,
build + adversarial-verify pipeline, refine loop). The run hit the session usage
limit partway through, so 1 of 4 approaches (the most general one) was fully built
and validated; 3 were designed and scripted but not run. This report states only
what the completed evidence supports. Synthesis written by hand from the agents'
returned results after the auto-synthesis agent was cut off by the limit.*

## Headline: the rigorous test found NO cost-surviving out-of-sample edge

The one approach that ran end-to-end — a low-capacity **Triple-Barrier Gradient
Boosting** model — was built specifically to make the question *testable* (the
shipped rule fires ~0.2/day ≈ 3–4 independent events, far too few to prove
anything). Using CUSUM event sampling it lifted the sample to **4,226 declustered
events over 2021–2026 (536,394 1-min bars)**, then evaluated with **purged +
embargoed walk-forward CV** and a **1,000-permutation block-shuffle null**.

| variant | events | IS AUC | OOS AUC | OOS net exp | p-value |
|---|---|---|---|---|---|
| meta_vert30 | 4,226 | 0.650 | **0.523** | **−3.9 bps** | 0.074 |
| 3class_vert30 | 4,226 | 0.672 | **0.516** | **−5.3 bps** | 0.085 |
| 3class_vert60 | 4,226 | 0.676 | 0.508 | −5.9 bps | 0.520 |
| meta_vert60 | 4,226 | 0.635 | 0.530 | −5.6 bps | 0.371 |

**What this says, plainly:**
- **In-sample AUC 0.65–0.68 collapses to out-of-sample 0.51–0.53** (barely above a
  coin flip). That 0.13–0.17 drop *is* overfitting, measured — the exact mirage the
  workflow was designed to catch.
- **Out-of-sample expectancy is negative net of costs** for all four variants. The
  gross edge (~2 bps) never clears a realistic ~4–6 bps round-trip cost floor.
- **Nothing is statistically significant** (best p=0.074, none <0.05, all OOS
  results sit inside the shuffle-null band; worse after a multiple-testing haircut).
- This **confirms the shipped rule's own p=0.45 on a ~1000× larger, testable
  sample.** The negative result is now robust, not just underpowered.

**Conclusion: at 1-minute resolution, the tick-rule / flow-proxy feature set
carries no statistically significant, cost-surviving predictive edge for TSLA.**
The model saying so is *more* information than the unvalidated rule provided.

## What the audit found (all completed)

- **Data ceiling:** FMP actually serves full 1-min bars back to **2019** (and daily
  to 2015) — the project's ~3-month window was **self-imposed**, not a data limit.
  So sample size was never the real cap; **regime non-stationarity** is.
- **True order flow is capped at 2 days** (the Databento Lee-Ready data). Any ML on
  real aggressor flow has n=2 — statistically dead. The order-flow *findings* stand
  as forensics; they cannot power a live model.
- **Leakage audit: clean.** Anchored VWAP, cumulative delta, gap/run-up, and all
  forward-return windows are causally correct — no look-ahead. The engine's problem
  is not leakage; it's that the signal doesn't generalize.
- **Feature gap:** the core input `sign(close−close[1])·volume` is a lossy tick-rule
  proxy; the audit vs Databento ground truth confirms it misclassifies aggressor
  side badly. The thresholds are calibrated to an inflated proxy.

## Not completed (session limit) — designed & scripted, not run
- **metalabel** — meta-labeling secondary filter on the existing trigger
  (`scripts/ml/metalabel_pipeline.py`).
- **ofproxy** — Databento-calibrated OHLCV absorption proxies
  (`scripts/ml/ofproxy_pipeline.py`).
- **rfe** — regime-filtered ensemble.
These can be finished by resuming the workflow after the limit resets. Given the
tbgbm result and the audit (lossy proxy, 2-day flow ceiling, non-stationarity),
the honest prior is that they are unlikely to clear costs either — but they should
be run to confirm rather than assumed.

## The honest bottom line
A parallel, adversarial, hard-evidence search — 5.5 years of data, thousands of
events, purged walk-forward CV, permutation nulls — did **not** find a better
signal that survives out-of-sample and costs. The FlowForensics rule is best
understood as a **forensic/discretionary tell on catalyst days**, not a
mechanical edge. The most valuable next step is not a fancier model on 1-min bars
(that path is now measured as a dead end) but **different data** — longer-horizon
(daily/multi-day) delivery-reaction structure, or true order-flow across many
events if that data can be afforded — because the edge, if one exists, is not in
1-minute price/volume shape. *Not investment advice.*
