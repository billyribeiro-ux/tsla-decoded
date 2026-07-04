# FlowForensics signal validation (hard evidence)

The thinkScript rules re-implemented bar-for-bar in Python and run on the cached 1-minute data: the target week (the two measured regimes) plus a 9-day baseline for sparsity and forward-return context.

## Chosen defaults (shipped in the .ts files)

| input           |   default |
|-----------------|-----------|
| imb_window      |     30    |
| buy_thresh      |      0.2  |
| sell_thresh     |     -0.3  |
| relvol_fast     |     10    |
| relvol_slow     |     50    |
| relvol_thresh   |      1.25 |
| clv_smooth      |     10    |
| open_window_min |     75    |
| open_high_min   |     15    |
| below_vwap_bars |     15    |
| cooldown_min    |     30    |

## Event capture

- SELL on 2026-07-02: fired at **2026-07-02 09:35:00-04:00** (within the 09:36–10:05 liquidation onset: **True**)
- BUY on 2026-06-29: fired at **2026-06-29 10:33:00-04:00** (within the morning accumulation drive: **True**)
- baseline sparsity: **0.89 signals/day** over the baseline

## Target-week signals (signed forward returns, % in signal direction)

| ts                        | signal   | trigger           |   price |    imb |   fwd_15m |   fwd_30m |   fwd_60m |
|:--------------------------|:---------|:------------------|--------:|-------:|----------:|----------:|----------:|
| 2026-06-29 10:33:00-04:00 | BUY      | accumulation      |  397.99 |  0.301 |    -0.704 |    -0.116 |     0.352 |
| 2026-06-29 12:31:00-04:00 | BUY      | accumulation      |  404.58 |  0.346 |    -0.497 |    -0.311 |     1.147 |
| 2026-06-29 13:15:00-04:00 | BUY      | accumulation      |  407.17 |  0.44  |     0.489 |     0.707 |     0.314 |
| 2026-06-29 15:15:00-04:00 | BUY      | accumulation      |  412.26 |  0.296 |     0.019 |     0.01  |    -0.163 |
| 2026-06-30 11:39:00-04:00 | BUY      | accumulation      |  417.47 |  0.248 |    -0.077 |    -0.137 |     0.057 |
| 2026-06-30 13:07:00-04:00 | BUY      | accumulation      |  419.17 |  0.301 |    -0.16  |    -0.558 |    -0.32  |
| 2026-06-30 14:48:00-04:00 | BUY      | accumulation      |  420.39 |  0.286 |     0.538 |     0.771 |     0.426 |
| 2026-07-01 09:39:00-04:00 | SELL     | opening-rejection |  419.45 | -0.395 |    -0.913 |    -1.707 |    -1.907 |
| 2026-07-01 11:14:00-04:00 | BUY      | accumulation      |  430.33 |  0.277 |     0.358 |     0.04  |    -0.507 |
| 2026-07-02 09:35:00-04:00 | SELL     | opening-rejection |  422.83 | -0.069 |     2.476 |     2.488 |     5.558 |
| 2026-07-02 10:23:00-04:00 | SELL     | opening-rejection |  404.27 | -0.544 |     1.227 |     1.918 |     2.206 |

## Baseline signals

| ts                        | signal   | trigger           |   price |    imb |   fwd_15m |   fwd_30m |   fwd_60m |
|:--------------------------|:---------|:------------------|--------:|-------:|----------:|----------:|----------:|
| 2026-06-15 15:57:00-04:00 | BUY      | accumulation      |  410.43 |  0.341 |     0.192 |     0.192 |     0.192 |
| 2026-06-17 12:21:00-04:00 | BUY      | accumulation      |  404.17 |  0.566 |     0     |    -0.235 |     0.012 |
| 2026-06-17 15:14:00-04:00 | SELL     | distribution      |  401.02 | -0.322 |     0.825 |     1.673 |     1.194 |
| 2026-06-18 15:42:00-04:00 | BUY      | accumulation      |  398.33 |  0.496 |     0.695 |     0.53  |     0.53  |
| 2026-06-22 10:06:00-04:00 | BUY      | accumulation      |  412.33 |  0.516 |    -0.172 |    -0.604 |    -0.96  |
| 2026-06-23 10:24:00-04:00 | SELL     | distribution      |  386.88 | -0.365 |    -0.46  |     0.289 |     0.832 |
| 2026-06-25 09:35:00-04:00 | SELL     | opening-rejection |  373.4  | -0.282 |    -0.64  |    -0.57  |    -1.146 |
| 2026-06-26 11:17:00-04:00 | BUY      | accumulation      |  381.75 |  0.356 |     1.139 |     1.31  |     0.422 |
- baseline +15m: mean +0.20%, hit rate 50% (n=8)
- baseline +30m: mean +0.32%, hit rate 62% (n=8)
- baseline +60m: mean +0.13%, hit rate 75% (n=8)

## Threshold grid

|   buyT |   sellT |   score | sell≤10:05   | buy≤11:00   |   base/day |
|--------|---------|---------|--------------|-------------|------------|
|   0.15 |   -0.15 |    3.44 | True         | True        |       1.11 |
|   0.15 |   -0.2  |    3.44 | True         | True        |       1.11 |
|   0.15 |   -0.25 |    3.56 | True         | True        |       0.89 |
|   0.15 |   -0.3  |    3.56 | True         | True        |       0.89 |
|   0.2  |   -0.15 |    3.44 | True         | True        |       1.11 |
|   0.2  |   -0.2  |    3.44 | True         | True        |       1.11 |
|   0.2  |   -0.25 |    3.56 | True         | True        |       0.89 |
|   0.2  |   -0.3  |    3.56 | True         | True        |       0.89 |
|   0.25 |   -0.15 |    3.44 | True         | True        |       1.11 |
|   0.25 |   -0.2  |    3.44 | True         | True        |       1.11 |
|   0.25 |   -0.25 |    3.56 | True         | True        |       0.89 |
|   0.25 |   -0.3  |    3.56 | True         | True        |       0.89 |
|   0.3  |   -0.15 |    3.44 | True         | True        |       1.11 |
|   0.3  |   -0.2  |    3.44 | True         | True        |       1.11 |
|   0.3  |   -0.25 |    3.56 | True         | True        |       0.89 |
|   0.3  |   -0.3  |    3.56 | True         | True        |       0.89 |

**Sample-size honesty:** these rules encode two measured regimes from one stock and one week plus a 2-week baseline. Run thinkorswim's own strategy report over longer history before any live use. Not investment advice.