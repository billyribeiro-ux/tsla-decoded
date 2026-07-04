# Out-of-sample validation: 2026-05-04 → 2026-06-26

The shipped FlowForensics v1.1 defaults — frozen, no re-tuning — run on the two months before the decoded week (38 trading days, of which 29 precede 2026-06-13 and are strictly out-of-sample; later days were the tuning baseline and are marked).

## STRICT OUT-OF-SAMPLE

| ts               | signal   | trigger           |   price |   mfe |   mae |   to_close |   managed | exit      | sample   |
|:-----------------|:---------|:------------------|--------:|------:|------:|-----------:|----------:|:----------|:---------|
| 2026-05-06 11:50 | BUY      | accumulation      |  395.3  |  1.54 | -0.36 |       0.81 |      1.25 | target    | OOS      |
| 2026-05-06 12:23 | BUY      | accumulation      |  396.98 |  1.11 | -0.28 |       0.39 |      0.39 | close     | OOS      |
| 2026-05-06 13:11 | BUY      | accumulation      |  399.01 |  0.59 | -0.58 |      -0.12 |     -0.12 | close     | OOS      |
| 2026-05-06 14:10 | BUY      | accumulation      |  399.64 |  0.43 | -0.35 |      -0.28 |     -0.28 | close     | OOS      |
| 2026-05-07 11:12 | SELL     | distribution      |  409.88 |  1.79 | -0.48 |      -0.48 |      1.25 | target    | OOS      |
| 2026-05-08 10:02 | BUY      | accumulation      |  429.3  |  0.34 | -1.46 |      -0.23 |     -1.23 | vwap-stop | OOS      |
| 2026-05-08 14:23 | BUY      | accumulation      |  428.53 |  0.16 | -0.9  |      -0.05 |     -0.47 | vwap-stop | OOS      |
| 2026-05-13 09:47 | SELL     | opening-rejection |  430.37 | -0.11 | -5.23 |      -3.46 |     -1.07 | vwap-stop | OOS      |
| 2026-05-13 10:30 | BUY      | accumulation      |  443.8  |  2.04 | -0.07 |       0.33 |      1.25 | target    | OOS      |
| 2026-05-14 09:35 | SELL     | opening-rejection |  443.97 |  0.48 | -1.74 |       0.15 |     -0.34 | vwap-stop | OOS      |
| 2026-05-14 11:39 | BUY      | accumulation      |  449.64 |  0.46 | -1.51 |      -1.41 |     -0.82 | vwap-stop | OOS      |
| 2026-05-15 09:46 | SELL     | distribution      |  425.7  |  0.82 | -0.98 |       0.79 |     -0.68 | vwap-stop | OOS      |
| 2026-05-15 13:34 | BUY      | accumulation      |  429.3  | -0.02 | -1.65 |      -1.63 |     -0.71 | vwap-stop | OOS      |
| 2026-05-22 10:33 | BUY      | accumulation      |  428.56 |  0.65 | -1.03 |      -0.61 |     -0.47 | vwap-stop | OOS      |
| 2026-05-26 10:45 | BUY      | accumulation      |  431.99 |  0.67 | -1.01 |       0.36 |     -0.35 | vwap-stop | OOS      |
| 2026-05-27 10:44 | BUY      | accumulation      |  443.84 |  0.34 | -1.27 |      -0.78 |     -0.69 | vwap-stop | OOS      |
| 2026-05-29 12:14 | BUY      | accumulation      |  438.38 |  0.53 | -0.96 |      -0.64 |     -0.74 | vwap-stop | OOS      |
| 2026-06-02 09:35 | SELL     | opening-rejection |  414.3  |  0.06 | -2.33 |      -2.28 |     -0.23 | vwap-stop | OOS      |
| 2026-06-05 09:36 | SELL     | opening-rejection |  419.05 |  7.24 |  0.37 |       6.72 |      1.25 | target    | OOS      |
| 2026-06-08 13:25 | BUY      | accumulation      |  410.02 |  0.67 | -0.49 |      -0.25 |     -0.25 | close     | OOS      |
| 2026-06-11 09:35 | SELL     | opening-rejection |  381    | -0.03 | -4.83 |      -4.74 |     -0.4  | vwap-stop | OOS      |
| 2026-06-11 12:54 | SELL     | distribution      |  384.99 |  0.34 | -3.74 |      -3.65 |     -0.26 | vwap-stop | OOS      |
- **BUY**: n=14, managed win rate 21%, mean managed -0.23%, mean to-close -0.29%, mean MFE +0.68%
- **SELL**: n=8, managed win rate 25%, mean managed -0.06%, mean to-close -0.87%, mean MFE +1.32%

## baseline (in-sample)

| ts               | signal   | trigger           |   price |   mfe |   mae |   to_close |   managed | exit      | sample   |
|:-----------------|:---------|:------------------|--------:|------:|------:|-----------:|----------:|:----------|:---------|
| 2026-06-17 12:21 | BUY      | accumulation      |  404.17 |  0.26 | -2.48 |      -1.96 |     -0.98 | vwap-stop | baseline |
| 2026-06-17 15:10 | SELL     | distribution      |  399.89 |  1.44 | -0.32 |       0.92 |      1.25 | target    | baseline |
| 2026-06-18 09:36 | SELL     | opening-rejection |  391.72 |  1.73 | -2.68 |      -2.23 |      0.13 | vwap-stop | baseline |
| 2026-06-18 11:46 | SELL     | distribution      |  387.7  | -0.1  | -3.75 |      -3.29 |     -0.49 | vwap-stop | baseline |
| 2026-06-22 10:06 | BUY      | accumulation      |  412.33 |  0.38 | -2.54 |      -1.77 |     -1.17 | vwap-stop | baseline |
| 2026-06-23 10:23 | SELL     | distribution      |  387.56 |  2.13 | -0.47 |       1.54 |     -0.45 | vwap-stop | baseline |
| 2026-06-25 09:35 | SELL     | opening-rejection |  373.4  |  0.47 | -1.24 |      -0.42 |     -0.5  | vwap-stop | baseline |
| 2026-06-26 11:17 | BUY      | accumulation      |  381.75 |  1.51 | -0.82 |      -0.64 |      1.25 | target    | baseline |
- **BUY**: n=3, managed win rate 33%, mean managed -0.30%, mean to-close -1.46%, mean MFE +0.72%
- **SELL**: n=5, managed win rate 40%, mean managed -0.01%, mean to-close -0.70%, mean MFE +1.13%

## Daily rules over the window

_No daily signals in the window (they are event detectors; the decoded week's accumulation/reversal pair remains their only firing in 2026 data)._

**Read honestly:** this is one symbol over two months. A positive OOS expectancy here supports the decoded concept; it is still not a guarantee of future performance. Not investment advice.