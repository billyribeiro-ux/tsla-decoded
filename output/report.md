# TSLA decoded: 2026-06-29 → 2026-07-02

Forensic attribution of the week's price action from FMP intraday/news data: seasonality-adjusted event detection, SPY/QQQ beta decomposition, catalyst time-alignment, order-flow proxies, and an iterative escalation loop.

## The week at a glance

| date       |   open |   high |    low |   close | chg    | volume   |
|------------|--------|--------|--------|---------|--------|----------|
| 2026-06-29 | 381.79 | 413.27 | 379.3  |  411.84 | +7.87% | 57.6M    |
| 2026-06-30 | 406    | 424.54 | 406    |  420.6  | +3.60% | 43.4M    |
| 2026-07-01 | 421.46 | 432.86 | 418.09 |  425.3  | +0.91% | 40.1M    |
| 2026-07-02 | 428.01 | 432.35 | 389.3  |  393.45 | -8.07% | 73.9M    |

## Q2 deliveries hypothesis

**Release found:** “Tesla Second Quarter 2026 Production, Deliveries & Deployments”
- timestamp: 2026-07-02T09:05:00-04:00
- extracted figures: {'deliveries': 480000, 'production': 450000, 'deliveries_exact': 480126}
- reaction coverage: “Tesla Second Quarter 2026 Production, Deliveries & Deployments”; “Sunrun, Renew Home, and Tesla Team Up to Deliver More Than 16 Gigawatts of Fast,”; “Tesla Crushes Q2 Deliveries & Energy Storage Forecasts: What's Next?”; “Tesla's 13% Rally Sets Up a Balanced Risk Reward Ahead of Q2 Delivery Numbers”

## Market decomposition model

OLS of TSLA 5-min returns on SPY, QQQ over the baseline (2026-05-04 → 2026-06-26): R² = 0.3542, betas = SPY=0.4061, QQQ=0.9511.
An event's *idio share* is the fraction of its move not explained by this model — high idio share means TSLA-specific cause, low means the market moved TSLA.

## Detected events and attribution

| event      | window (ET)           | kind   | move   |   peak z | idio   | top catalyst                                                            | lead   |   conf |    |
|------------|-----------------------|--------|--------|----------|--------|-------------------------------------------------------------------------|--------|--------|----|
| S0629      | Mon 06-29 09:30–15:55 | day    | +8.12% |      2.6 | 83%    | Tesla Reports Q2 Deliveries in a Matter of Days. Here's the Number Tha… | +0m    |   0.58 | ○  |
| E0629-1025 | Mon 06-29 09:57–10:25 | spike  | +1.05% |      5.5 | 100%   | Tesla Stock In Focus: Regulatory Twists, Q2 Delivery Countdown, 16 GW … | +27m   |   0.62 | ○  |
| E0630-1140 | Tue 06-30 11:10–11:40 | spike  | -0.28% |      4.2 | 8%     | TSLA Stock Rises Ahead of Q2 Deliveries Report: Buy, Hold, or Sell?     | +64m   |   0.37 | ○  |
| S0702      | Thu 07-02 09:30–15:55 | day    | -7.78% |      2.5 | 74%    | Tesla Second Quarter 2026 Production, Deliveries & Deployments          | +0m    |   0.88 | ✓  |
| E0702-1015 | Thu 07-02 09:47–10:30 | spike  | -3.52% |      7.7 | 77%    | Tesla Second Quarter 2026 Production, Deliveries & Deployments          | +17m   |   0.88 | ✓  |
| E0702-1100 | Thu 07-02 11:00       | spike  | -0.67% |      3.2 | 39%    | Tesla Second Quarter 2026 Production, Deliveries & Deployments          | +90m   |   0.53 | ○  |
| E0702-1205 | Thu 07-02 11:37–12:05 | spike  | -0.80% |      5.2 | 43%    | Stock Market Rebounds, But AI Falters; Meta, Tesla, Jobs Report In Foc… | +0m    |   0.47 | ○  |

`lead` = minutes the catalyst preceded the event start (negative ⇒ published after the move began). `idio` = share of the move not explained by SPY/QQQ. ✓ = attributed at confidence ≥ 0.7.

## Event detail

### S0629 — day +8.12% (Monday Jun 29 09:30 ET)

- peak |return z| 2.6, volume z 8.3, idio share 83% (actual +6.65% vs market-implied +1.13%)
- order flow: two-sided/rotational flow (imbalance +0.20, CLV +0.08, 49.8M shares)
- full-session move +8.1% = 2.6σ of daily vol — catalyst window spans overnight/pre-market
- 1-min onset refined to 09:40
- cross-asset: sector-wide move (peers moved together) {'RIVN': 6.2, 'LCID': 9.35, 'NIO': 2.04}
- confidence **0.58** (alignment 0.42, idio-consistency 0.83, timing 1.00, uniqueness 0.14)
- candidate catalysts:
  1. [0.42] (stock_news, 06-28 19:03) Tesla Reports Q2 Deliveries in a Matter of Days. Here's the Number That Matters.
  1. [0.36] (stock_news, 06-29 07:40) Tesla Stock In Focus: Regulatory Twists, Q2 Delivery Countdown, 16 GW Energy Partnership
  1. [0.22] (general_news, 06-28 22:48) Rollins: A Rare Generational Wealth-Building Opportunity (Rating Upgrade)

### E0629-1025 — spike +1.05% (Monday Jun 29 09:57 ET)

- peak |return z| 5.5, volume z -1.6, idio share 100% (actual +0.89% vs market-implied -0.81%)
- order flow: two-sided/rotational flow (imbalance +0.25, CLV +0.07, 6.7M shares)
- 1-min onset refined to 09:57
- cross-asset: sector-wide move (peers moved together) {'RIVN': 2.52, 'LCID': 2.43, 'NIO': 0.81}
- confidence **0.62** (alignment 0.29, idio-consistency 1.00, timing 1.00, uniqueness 0.64)
- candidate catalysts:
  1. [0.29] (stock_news, 06-29 07:40) Tesla Stock In Focus: Regulatory Twists, Q2 Delivery Countdown, 16 GW Energy Partnership
  1. [0.10] (general_news, 06-29 05:30) How a Tight-Lipped Fed Could Lead to Higher Mortgage Rates
  1. [0.10] (general_news, 06-29 06:28) Stock Market's Risk Appetite Is Shifting as AI, Iran, and Fed Fears Linger

### E0630-1140 — spike -0.28% (Tuesday Jun 30 11:10 ET)

- peak |return z| 4.2, volume z -0.6, idio share 8% (actual +0.22% vs market-implied +0.21%)
- order flow: two-sided/rotational flow (imbalance +0.12, CLV +0.04, 3.4M shares)
- 1-min onset refined to 11:10
- cross-asset: TSLA-specific vs peers {'RIVN': 0.0, 'LCID': 1.86, 'NIO': 0.0}
- confidence **0.37** (alignment 0.25, idio-consistency 0.08, timing 0.70, uniqueness 0.64)
- candidate catalysts:
  1. [0.25] (stock_news, 06-30 10:05) TSLA Stock Rises Ahead of Q2 Deliveries Report: Buy, Hold, or Sell?
  1. [0.09] (stock_news, 06-30 10:23) Prediction: This Is Where Tesla's Price Target Points In 2027
  1. [0.09] (stock_news, 06-30 11:32) Tesla starts testing Cybercab without pedals or a steering wheel in Austin

### S0702 — day -7.78% (Thursday Jul 02 09:30 ET)

- peak |return z| 2.5, volume z 8.2, idio share 74% (actual -7.85% vs market-implied -2.02%)
- order flow: two-sided/rotational flow (imbalance -0.17, CLV -0.08, 62.3M shares)
- full-session move -7.8% = 2.5σ of daily vol — catalyst window spans overnight/pre-market
- confidence **0.88** (alignment 1.00, idio-consistency 0.74, timing 1.00, uniqueness 0.55)
- candidate catalysts:
  1. [1.00] (press_release, 07-02 09:05) Tesla Second Quarter 2026 Production, Deliveries & Deployments
  1. [0.60] (stock_news, 07-02 09:05) Tesla Second Quarter 2026 Production, Deliveries & Deployments
  1. [0.45] (stock_news, 07-02 09:08) Tesla reports 480,126 vehicle deliveries for second quarter, topping expectation

### E0702-1015 — spike -3.52% (Thursday Jul 02 09:47 ET)

- peak |return z| 7.7, volume z 7.4, idio share 77% (actual -3.58% vs market-implied -0.81%)
- order flow: aggressive institutional-style selling (imbalance -0.48, CLV -0.20, 15.6M shares)
- 1-min onset refined to 09:47
- confidence **0.88** (alignment 0.97, idio-consistency 0.78, timing 1.00, uniqueness 0.57)
- candidate catalysts:
  1. [0.87] (press_release, 07-02 09:05) Tesla Second Quarter 2026 Production, Deliveries & Deployments
  1. [0.52] (stock_news, 07-02 09:05) Tesla Second Quarter 2026 Production, Deliveries & Deployments
  1. [0.39] (stock_news, 07-02 09:08) Tesla reports 480,126 vehicle deliveries for second quarter, topping expectation

### E0702-1100 — spike -0.67% (Thursday Jul 02 11:00 ET)

- peak |return z| 3.2, volume z 5.6, idio share 39% (actual -0.32% vs market-implied -0.20%)
- order flow: two-sided/rotational flow (imbalance +0.12, CLV -0.21, 2.8M shares)
- confidence **0.53** (alignment 0.57, idio-consistency 0.39, timing 0.70, uniqueness 0.35)
- candidate catalysts:
  1. [0.47] (press_release, 07-02 09:05) Tesla Second Quarter 2026 Production, Deliveries & Deployments
  1. [0.31] (stock_news, 07-02 10:14) Why Tesla stock is tanking 3% even after crushing delivery estimates
  1. [0.28] (stock_news, 07-02 09:05) Tesla Second Quarter 2026 Production, Deliveries & Deployments

### E0702-1205 — spike -0.80% (Thursday Jul 02 11:37 ET)

- peak |return z| 5.2, volume z 2.9, idio share 43% (actual -1.08% vs market-implied -0.62%)
- order flow: two-sided/rotational flow (imbalance -0.06, CLV -0.04, 5.6M shares)
- 1-min onset refined to 11:37
- cross-asset: sector-wide move (peers moved together) {'RIVN': -1.16, 'LCID': -0.65, 'NIO': -0.41}
- confidence **0.47** (alignment 0.39, idio-consistency 0.43, timing 1.00, uniqueness 0.10)
- candidate catalysts:
  1. [0.39] (stock_news, 07-02 11:36) Stock Market Rebounds, But AI Falters; Meta, Tesla, Jobs Report In Focus: Weekly Review
  1. [0.35] (stock_news, 07-02 11:06) Tesla Drops 7% Despite Blowout Q2 Delivery Beat, Nio Slips After Its Own Delivery Update
  1. [0.35] (press_release, 07-02 09:05) Tesla Second Quarter 2026 Production, Deliveries & Deployments

## Investigation loop

- iteration 0 [P0: 5-min detection, TSLA news/PR/analyst] — events 7, confidences {'S0629': 0.577, 'E0629-1025': 0.345, 'E0630-1140': 0.532, 'S0702': 0.881, 'E0702-1015': 0.68, 'E0702-1100': 0.325, 'E0702-1205': 0.467} (HTTP so far: 0)
- iteration 1 [P1: 1-min onset refinement] — events 7, confidences {'S0629': 0.577, 'E0629-1025': 0.467, 'E0630-1140': 0.286, 'S0702': 0.881, 'E0702-1015': 0.601, 'E0702-1100': 0.325, 'E0702-1205': 0.498} (HTTP so far: 0)
- iteration 2 [P2: widened windows + economic calendar + general news] — events 7, confidences {'S0629': 0.577, 'E0629-1025': 0.625, 'E0630-1140': 0.367, 'S0702': 0.881, 'E0702-1015': 0.876, 'E0702-1100': 0.529, 'E0702-1205': 0.475} (HTTP so far: 0)
- iteration 3 [P3: cross-asset (peers vs market) check] — events 7, confidences {'S0629': 0.577, 'E0629-1025': 0.625, 'E0630-1140': 0.367, 'S0702': 0.881, 'E0702-1015': 0.876, 'E0702-1100': 0.529, 'E0702-1205': 0.475} (HTTP so far: 0)
- early stop: iteration 3: max confidence delta 0.000

## What explains abnormal moves (permutation importance)

| feature                 |   importance |
|-------------------------|--------------|
| ret_QQQ                 |     0.344294 |
| z_vol                   |     0.246557 |
| ret_SPY                 |     0.243202 |
| min_since_economic      |     0.224194 |
| min_since_analyst       |     0.191475 |
| vwap_dev                |     0.1713   |
| min_since_press_release |     0.151439 |
| min_since_stock_news    |     0.141283 |

## Data sources / capabilities

| endpoint                  | status   |
|---------------------------|----------|
| economic-calendar         | ok       |
| grades-news               | ok       |
| historical-chart/1min     | ok       |
| historical-chart/5min     | ok       |
| historical-price-eod/full | ok       |
| news/general-latest       | ok       |
| news/press-releases       | ok       |
| news/stock                | ok       |
| price-target-news         | ok       |

## Certainty statement

4 event(s) remain below the 0.7 confidence threshold: S0629, E0629-1025, E0630-1140, E0702-1205. For these, the ranked candidates above are hypotheses, not verdicts; the missing evidence is noted per event.

Causal attribution in markets is probabilistic: timestamps, news coverage and decomposition narrow the field of explanations, but order-level intent is not observable from public OHLCV data. The confidences above quantify exactly how far the evidence goes — nothing here should be read as certainty or as investment advice.