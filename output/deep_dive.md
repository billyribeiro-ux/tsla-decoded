# TSLA session-by-session forensics: 2026-06-29 → 2026-07-02

Each session decoded at 1-minute resolution: changepoint phases, order-flow imbalance, VWAP control, market-implied vs TSLA-specific attribution per phase, the individual minutes that carried the day, volume-at-price shelves, and the session's news timeline.

_Note: FMP `historical-chart` supplies regular-session bars only (09:30–16:00 ET); overnight/pre-market catalysts are attributed to the opening minutes they were absorbed in._


---

## Monday, June 29, 2026 — +8.40% close-to-close

|   open | high           | low            |   close | overnight gap   | open→close   | volume                  | close location in range   |
|--------|----------------|----------------|---------|-----------------|--------------|-------------------------|---------------------------|
| 381.79 | 413.27 @ 15:37 | 379.30 @ 09:30 |  411.59 | +0.55%          | +7.81%       | 49.8M (1.0× 20d median) | 95%                       |

VWAP: price spent **99%** of the session above the anchored VWAP, crossing it 5 time(s) — buyers controlled the auction.

### Session phases (1-minute changepoint segmentation)

| phase   | window (ET)   | character     | return   | volume   |   flow imb | above VWAP   | idio   |
|---------|---------------|---------------|----------|----------|------------|--------------|--------|
| P1      | 09:30–10:24   | upside drive  | +2.65%   | 10.1M    |       0.16 | 95%          | 100%   |
| P2      | 10:24–11:29   | upside drive  | +1.55%   | 8.2M     |       0.16 | 100%         | 3%     |
| P3      | 11:29–12:19   | upside drive  | +1.07%   | 5.5M     |       0.21 | 100%         | 52%    |
| P4      | 12:19–13:14   | upside drive  | +1.09%   | 6.0M     |       0.22 | 100%         | 55%    |
| P5      | 13:14–15:09   | upside drive  | +1.08%   | 12.3M    |       0.26 | 100%         | 71%    |
| P6      | 15:09–15:59   | consolidation | +0.18%   | 8.1M     |       0.18 | 100%         | 67%    |

### Play-by-play

- **09:30–10:24 — upside drive**: +2.65% in 55 min on 10.1M shares; flow imbalance +0.16 (buyers lifting offers); 100% TSLA-specific vs SPY/QQQ (market-implied -1.37%); range 379.30 (09:30) → 394.34 (10:03).
- **10:24–11:29 — upside drive**: +1.55% in 66 min on 8.2M shares; flow imbalance +0.16 (buyers lifting offers); 3% TSLA-specific vs SPY/QQQ (market-implied +1.49%); range 390.57 (10:24) → 398.44 (10:34).
- **11:29–12:19 — upside drive**: +1.07% in 51 min on 5.5M shares; flow imbalance +0.21 (buyers lifting offers); 52% TSLA-specific vs SPY/QQQ (market-implied +0.74%); range 397.28 (11:29) → 402.24 (12:18).
- **12:19–13:14 — upside drive**: +1.09% in 56 min on 6.0M shares; flow imbalance +0.22 (buyers lifting offers); 55% TSLA-specific vs SPY/QQQ (market-implied +0.52%); range 402.00 (12:20) → 406.67 (13:13).
- **13:14–15:09 — upside drive**: +1.08% in 116 min on 12.3M shares; flow imbalance +0.26 (buyers lifting offers); 71% TSLA-specific vs SPY/QQQ (market-implied +0.34%); range 406.31 (13:14) → 411.26 (15:09).
- **15:09–15:59 — consolidation**: +0.18% in 51 min on 8.1M shares; flow imbalance +0.18 (buyers lifting offers); 67% TSLA-specific vs SPY/QQQ (market-implied +0.17%); range 410.41 (15:10) → 413.27 (15:37).

### The minutes that mattered

| minute   | return   |   |ret| z | volume   |   vol z |   CLV |   close |
|----------|----------|-----------|----------|---------|-------|---------|
| 09:31    | +0.76%   |       0.7 | 39k      |    -4.4 |  0.59 |  384.3  |
| 09:41    | -0.52%   |       1.6 | 294k     |     0.8 | -0.39 |  387.43 |
| 09:43    | +0.44%   |       2.9 | 383k     |     3.4 |  0.63 |  390.72 |
| 10:03    | +0.65%   |       9.1 | 284k     |     3.7 |  0.81 |  394.06 |
| 10:04    | -0.54%   |       3.1 | 166k     |     6.5 | -0.67 |  391.92 |
| 12:40    | -0.07%   |       0.5 | 254k     |    20.8 | -0.01 |  403.25 |
| 13:13    | +0.06%   |       0.7 | 141k     |    18.6 |  0.38 |  406.55 |
| 13:37    | +0.01%   |      -1.3 | 213k     |    18   | -0.27 |  410.24 |

CLV = close-location value within the bar (−1 = closed on the low, +1 = on the high).

### Where the volume traded

Top price shelves: **$410** (7.9M); **$412** (7.5M); **$392** (5.2M).

### News timeline (session-relevant TSLA catalysts)

| ET    | source     | headline                                                                                 |
|-------|------------|------------------------------------------------------------------------------------------|
| 07:40 | stock_news | Tesla Stock In Focus: Regulatory Twists, Q2 Delivery Countdown, 16 GW Energy Partnership |
| 11:00 | stock_news | Why Tesla stock is climbing over 4% on Monday                                            |
| 12:12 | stock_news | Tesla's Robotaxi Fleet Is Tiny Compared To Waymo—JPMorgan Says That's By Design          |


---

## Tuesday, June 30, 2026 — +2.06% close-to-close

|   open | high           | low            |   close | overnight gap   | open→close   | volume                  | close location in range   |
|--------|----------------|----------------|---------|-----------------|--------------|-------------------------|---------------------------|
| 406.19 | 424.54 @ 15:17 | 406.13 @ 09:30 |  420.32 | -1.37%          | +3.48%       | 36.1M (0.7× 20d median) | 77%                       |

VWAP: price spent **98%** of the session above the anchored VWAP, crossing it 11 time(s) — buyers controlled the auction.

### Session phases (1-minute changepoint segmentation)

| phase   | window (ET)   | character                        | return   | volume   |   flow imb | above VWAP   | idio   |
|---------|---------------|----------------------------------|----------|----------|------------|--------------|--------|
| P1      | 09:30–10:04   | upside drive                     | +1.11%   | 5.3M     |       0.13 | 86%          | 0%     |
| P2      | 10:04–11:29   | grind higher                     | +0.58%   | 8.9M     |       0.08 | 98%          | 72%    |
| P3      | 11:29–12:34   | grind higher                     | +0.36%   | 4.3M     |       0.15 | 100%         | 0%     |
| P4      | 12:34–14:09   | consolidation                    | +0.33%   | 5.2M     |       0.13 | 100%         | 65%    |
| P5      | 14:09–14:59   | grind higher, one-sided buy flow | +0.87%   | 4.2M     |       0.31 | 100%         | 88%    |
| P6      | 14:59–15:59   | controlled selling               | -0.40%   | 8.7M     |      -0.12 | 100%         | 100%   |

### Play-by-play

- **09:30–10:04 — upside drive**: +1.11% in 35 min on 5.3M shares; flow imbalance +0.13 (balanced tape); 0% TSLA-specific vs SPY/QQQ (market-implied +0.86%); range 406.13 (09:30) → 413.15 (10:03).
- **10:04–11:29 — grind higher**: +0.58% in 86 min on 8.9M shares; flow imbalance +0.08 (balanced tape); 72% TSLA-specific vs SPY/QQQ (market-implied +0.23%); range 412.25 (10:10) → 416.38 (11:02).
- **11:29–12:34 — grind higher**: +0.36% in 66 min on 4.3M shares; flow imbalance +0.15 (balanced tape); 0% TSLA-specific vs SPY/QQQ (market-implied +0.36%); range 415.14 (12:00) → 417.99 (11:39).
- **12:34–14:09 — consolidation**: +0.33% in 96 min on 5.2M shares; flow imbalance +0.13 (balanced tape); 65% TSLA-specific vs SPY/QQQ (market-implied +0.15%); range 416.00 (13:43) → 419.50 (13:07).
- **14:09–14:59 — grind higher, one-sided buy flow**: +0.87% in 51 min on 4.2M shares; flow imbalance +0.31 (buyers lifting offers); 88% TSLA-specific vs SPY/QQQ (market-implied +0.11%); range 417.71 (14:12) → 422.15 (14:59).
- **14:59–15:59 — controlled selling**: -0.40% in 61 min on 8.7M shares; flow imbalance -0.12 (balanced tape); 100% TSLA-specific vs SPY/QQQ (market-implied -0.05%); range 420.30 (15:59) → 424.54 (15:17).

### The minutes that mattered

| minute   | return   |   |ret| z | volume   |   vol z |   CLV |   close |
|----------|----------|-----------|----------|---------|-------|---------|
| 09:43    | -0.36%   |       2.1 | 189k     |     0.3 | -0.63 |  409.43 |
| 10:05    | +0.47%   |       5.3 | 437k     |     7.2 |  0.77 |  415.02 |
| 10:06    | -0.35%   |       2.1 | 247k     |     6.6 | -0.75 |  413.59 |
| 10:11    | +0.35%   |       1.6 | 157k     |     0.3 |  0.81 |  414.98 |
| 11:20    | +0.34%   |       6.8 | 129k     |     0.9 |  1    |  415.29 |
| 11:31    | +0.23%   |       2.4 | 355k     |    11.7 |  0.85 |  416.79 |
| 14:48    | +0.16%   |       2.5 | 571k     |    24.5 |  0.43 |  420.39 |
| 15:10    | -0.03%   |      -0.6 | 282k     |    12.1 | -0.39 |  423.83 |

CLV = close-location value within the bar (−1 = closed on the low, +1 = on the high).

### Where the volume traded

Top price shelves: **$416** (8.4M); **$418** (5.4M); **$422** (5.3M).

### News timeline (session-relevant TSLA catalysts)

| ET    | source     | headline                                                                    |
|-------|------------|-----------------------------------------------------------------------------|
| 08:50 | stock_news | Here's why the Magnificent 7 stocks have crashed and erased $2.3 trillion   |
| 09:05 | stock_news | Where Will Tesla Stock Be in 5 Years?                                       |
| 10:05 | stock_news | TSLA Stock Rises Ahead of Q2 Deliveries Report: Buy, Hold, or Sell?         |
| 11:32 | stock_news | Tesla starts testing Cybercab without pedals or a steering wheel in Austin  |
| 12:30 | stock_news | A $1.6 Trillion Disruption: Why Wall Street Is Worried About a SpaceX Phone |


---

## Wednesday, July 01, 2026 — +1.15% close-to-close

|   open | high           | low            |   close | overnight gap   | open→close   | volume                  | close location in range   |
|--------|----------------|----------------|---------|-----------------|--------------|-------------------------|---------------------------|
| 421.47 | 432.85 @ 11:27 | 418.20 @ 09:41 |  425.45 | +0.21%          | +0.94%       | 34.3M (0.7× 20d median) | 49%                       |

VWAP: price spent **56%** of the session above the anchored VWAP, crossing it 18 time(s) — a genuine two-sided fight.

### Session phases (1-minute changepoint segmentation)

| phase   | window (ET)   | character          | return   | volume   |   flow imb | above VWAP   | idio   |
|---------|---------------|--------------------|----------|----------|------------|--------------|--------|
| P1      | 09:30–10:04   | consolidation      | -0.27%   | 4.9M     |      -0.13 | 63%          | 0%     |
| P2      | 10:04–11:04   | grind higher       | +0.98%   | 7.6M     |       0.1  | 100%         | 93%    |
| P3      | 11:04–11:54   | consolidation      | +0.21%   | 6.2M     |       0.13 | 100%         | 65%    |
| P4      | 11:54–12:44   | consolidation      | -0.31%   | 2.8M     |      -0.12 | 100%         | 77%    |
| P5      | 12:44–13:29   | consolidation      | -0.23%   | 2.4M     |      -0.03 | 50%          | 76%    |
| P6      | 13:29–13:59   | controlled selling | -0.36%   | 1.7M     |      -0.11 | 0%           | 47%    |
| P7      | 13:59–14:59   | consolidation      | +0.19%   | 3.4M     |      -0.04 | 0%           | 0%     |
| P8      | 14:59–15:59   | consolidation      | -0.07%   | 5.9M     |       0.1  | 23%          | 100%   |

### Play-by-play

- **09:30–10:04 — consolidation**: -0.27% in 35 min on 4.9M shares; flow imbalance -0.13 (balanced tape); 0% TSLA-specific vs SPY/QQQ (market-implied +0.62%); range 418.20 (09:41) → 425.18 (09:31).
- **10:04–11:04 — grind higher**: +0.98% in 61 min on 7.6M shares; flow imbalance +0.10 (balanced tape); 93% TSLA-specific vs SPY/QQQ (market-implied +0.09%); range 423.39 (10:05) → 428.98 (10:50).
- **11:04–11:54 — consolidation**: +0.21% in 51 min on 6.2M shares; flow imbalance +0.13 (balanced tape); 65% TSLA-specific vs SPY/QQQ (market-implied +0.23%); range 427.54 (11:04) → 432.85 (11:27).
- **11:54–12:44 — consolidation**: -0.31% in 51 min on 2.8M shares; flow imbalance -0.12 (balanced tape); 77% TSLA-specific vs SPY/QQQ (market-implied -0.08%); range 427.02 (12:36) → 429.06 (11:54).
- **12:44–13:29 — consolidation**: -0.23% in 46 min on 2.4M shares; flow imbalance -0.03 (balanced tape); 76% TSLA-specific vs SPY/QQQ (market-implied -0.06%); range 425.47 (13:05) → 427.72 (12:48).
- **13:29–13:59 — controlled selling**: -0.36% in 31 min on 1.7M shares; flow imbalance -0.11 (balanced tape); 47% TSLA-specific vs SPY/QQQ (market-implied -0.28%); range 424.91 (13:59) → 426.88 (13:29).
- **13:59–14:59 — consolidation**: +0.19% in 61 min on 3.4M shares; flow imbalance -0.04 (balanced tape); 0% TSLA-specific vs SPY/QQQ (market-implied -0.22%); range 423.73 (14:40) → 425.75 (14:59).
- **14:59–15:59 — consolidation**: -0.07% in 61 min on 5.9M shares; flow imbalance +0.10 (balanced tape); 100% TSLA-specific vs SPY/QQQ (market-implied -0.11%); range 424.91 (15:01) → 427.27 (15:44).

### The minutes that mattered

| minute   | return   |   |ret| z | volume   |   vol z |   CLV |   close |
|----------|----------|-----------|----------|---------|-------|---------|
| 09:31    | -0.92%   |       1.1 | 358k     |     1.8 | -0.49 |  420.94 |
| 09:34    | +0.53%   |       1.2 | 248k     |     1.1 |  0.76 |  423.44 |
| 09:39    | -0.53%   |       3.3 | 227k     |     1.2 | -0.85 |  419.45 |
| 09:41    | +0.37%   |       0.9 | 162k     |    -0.8 |  0.52 |  420.27 |
| 10:05    | +0.50%   |       5.7 | 341k     |     4.9 |  0.91 |  425.82 |
| 10:06    | +0.21%   |       0.9 | 272k     |     7.8 |  0.75 |  426.73 |
| 10:49    | +0.25%   |       2.4 | 233k     |    15.8 |  0.89 |  428.79 |
| 11:14    | +0.18%   |       1.9 | 198k     |    10   |  0.51 |  430.33 |

CLV = close-location value within the bar (−1 = closed on the low, +1 = on the high).

### Where the volume traded

Top price shelves: **$426** (14.6M); **$428** (7.4M); **$424** (3.8M).

### News timeline (session-relevant TSLA catalysts)

| ET    | source     | headline                                                                        |
|-------|------------|---------------------------------------------------------------------------------|
| 06:20 | stock_news | ‘Big Short' Michael Burry just bet against this Elon Musk company               |
| 07:17 | stock_news | Tesla Deliveries Should Show a Second Straight Quarter of Growth                |
| 07:30 | stock_news | Tesla deliveries are set to rise — no thanks to the U.S.                        |
| 11:25 | stock_news | Forget Tesla: Why Smart Money Is Ditching Tesla To Buy Apple Stock              |
| 12:30 | stock_news | "Struggle Street" for UBER: Peak Business Performance Sees GOOGL, TSLA Pressure |
| 13:10 | stock_news | Will Tesla (TSLA) Beat Estimates Again in Its Next Earnings Report?             |
| 13:21 | stock_news | Why Tesla stock is beating the broader market today                             |
| 16:30 | economic   | Atlanta Fed GDPNow (Q2) (US)                                                    |


---

## Thursday, July 02, 2026 — -7.54% close-to-close

|   open | high           | low            |   close | overnight gap   | open→close   | volume                  | close location in range   |
|--------|----------------|----------------|---------|-----------------|--------------|-------------------------|---------------------------|
| 428.12 | 432.35 @ 09:31 | 389.34 @ 15:23 |  393.23 | +0.66%          | -8.15%       | 62.3M (1.3× 20d median) | 9%                        |

VWAP: price spent **1%** of the session above the anchored VWAP, crossing it 2 time(s) — sellers controlled the auction.

### Session phases (1-minute changepoint segmentation)

| phase   | window (ET)   | character                             | return   | volume   |   flow imb | above VWAP   | idio   |
|---------|---------------|---------------------------------------|----------|----------|------------|--------------|--------|
| P1      | 09:30–10:19   | liquidation wave, one-sided sell flow | -5.02%   | 13.5M    |      -0.46 | 4%           | 100%   |
| P2      | 10:19–10:39   | liquidation wave, one-sided sell flow | -2.22%   | 7.6M     |      -0.48 | 0%           | 71%    |
| P3      | 10:39–11:34   | consolidation                         | -0.04%   | 10.8M    |      -0.01 | 0%           | 0%     |
| P4      | 11:34–12:04   | consolidation                         | -0.29%   | 4.2M     |       0.08 | 0%           | 100%   |
| P5      | 12:04–12:29   | liquidation wave, one-sided sell flow | -1.11%   | 3.5M     |      -0.4  | 0%           | 69%    |
| P6      | 12:29–15:59   | consolidation                         | +0.08%   | 23.9M    |      -0.01 | 0%           | 100%   |

### Play-by-play

- **09:30–10:19 — liquidation wave, one-sided sell flow**: -5.02% in 50 min on 13.5M shares; flow imbalance -0.46 (sellers hitting bids); 100% TSLA-specific vs SPY/QQQ (market-implied +0.18%); range 407.22 (10:19) → 432.35 (09:31).
- **10:19–10:39 — liquidation wave, one-sided sell flow**: -2.22% in 21 min on 7.6M shares; flow imbalance -0.48 (sellers hitting bids); 71% TSLA-specific vs SPY/QQQ (market-implied -1.05%); range 398.20 (10:39) → 409.00 (10:19).
- **10:39–11:34 — consolidation**: -0.04% in 56 min on 10.8M shares; flow imbalance -0.01 (balanced tape); 0% TSLA-specific vs SPY/QQQ (market-implied -0.57%); range 394.34 (11:20) → 399.64 (10:39).
- **11:34–12:04 — consolidation**: -0.29% in 31 min on 4.2M shares; flow imbalance +0.08 (balanced tape); 100% TSLA-specific vs SPY/QQQ (market-implied -0.15%); range 396.86 (12:02) → 400.74 (11:41).
- **12:04–12:29 — liquidation wave, one-sided sell flow**: -1.11% in 26 min on 3.5M shares; flow imbalance -0.40 (sellers hitting bids); 69% TSLA-specific vs SPY/QQQ (market-implied -0.44%); range 392.82 (12:29) → 397.53 (12:05).
- **12:29–15:59 — consolidation**: +0.08% in 211 min on 23.9M shares; flow imbalance -0.01 (balanced tape); 100% TSLA-specific vs SPY/QQQ (market-implied +0.09%); range 389.34 (15:23) → 394.39 (14:10).

### The minutes that mattered

| minute   | return   |   |ret| z | volume   |   vol z |   CLV |   close |
|----------|----------|-----------|----------|---------|-------|---------|
| 09:32    | -0.76%   |       5   | 263k     |     7.7 | -0.78 |  427.07 |
| 09:35    | -0.59%   |       2.4 | 396k     |     2.3 | -0.89 |  422.83 |
| 09:36    | -0.66%   |      15.2 | 449k     |     4.3 | -0.87 |  420.04 |
| 09:40    | -0.51%   |       3.1 | 346k     |     3   | -0.68 |  416.59 |
| 10:12    | +0.45%   |       4.7 | 211k     |     1.3 |  0.95 |  413.83 |
| 10:39    | -0.18%   |       3.9 | 400k     |    18.2 | -0.46 |  398.59 |
| 10:49    | +0.19%   |       1.5 | 309k     |    23.7 |  0.32 |  397    |
| 14:04    | +0.14%   |       2   | 616k     |    27.1 |  1    |  392.66 |

CLV = close-location value within the bar (−1 = closed on the low, +1 = on the high).

### Where the volume traded

Top price shelves: **$392** (13.1M); **$394** (7.6M); **$396** (7.4M).

### News timeline (session-relevant TSLA catalysts)

| ET    | source        | headline                                                                                 |
|-------|---------------|------------------------------------------------------------------------------------------|
| 07:08 | stock_news    | Tesla Deliveries Need to Beat Expectations to Lift the Stock                             |
| 08:12 | stock_news    | Tesla Stock Surges 15% as FSD Update Backs Its Autonomy Thesis                           |
| 08:20 | stock_news    | Safety Regulator Closes Tesla Phantom Braking Probe After Complaints Drop Sharply        |
| 09:05 | press_release | Tesla Second Quarter 2026 Production, Deliveries & Deployments                           |
| 09:05 | stock_news    | Tesla Second Quarter 2026 Production, Deliveries & Deployments                           |
| 09:06 | stock_news    | Tesla sales rebound as it cashes in on sky-high gas prices                               |
| 09:06 | stock_news    | Tesla Sales Surge as Sales Recover in Europe                                             |
| 09:07 | stock_news    | Tesla posts stronger-than-expected Q2 deliveries as Europe sales improve                 |
| 09:08 | stock_news    | Tesla reports 480,126 vehicle deliveries for second quarter, topping expectation         |
| 09:18 | stock_news    | Tesla crushes delivery estimates, giving its stock a boost                               |
| 09:20 | stock_news    | Tesla saw a massive sales jump in the second quarter                                     |
| 10:14 | stock_news    | Why Tesla stock is tanking 3% even after crushing delivery estimates                     |
| 11:06 | stock_news    | Tesla Drops 7% Despite Blowout Q2 Delivery Beat, Nio Slips After Its Own Delivery Update |
| 11:08 | stock_news    | Elon Musk's Tesla shocks Wall Street with record sales — but shares still tumble         |


---

*Flow imbalance = tick-rule signed volume / total volume over the window; idio = share of the phase's move not explained by the SPY/QQQ beta model. All timestamps ET. Not investment advice.*