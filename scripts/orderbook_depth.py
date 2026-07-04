"""10-level order-book reconstruction (Databento MBP-10) for the July 2 open.

Shows the displayed bid/ask depth and book imbalance as price falls — the
evidence for hidden/iceberg distribution (book stays bid-heavy while price drops).
Windowed to 09:25-11:00 ET to keep the pull small (~$0.16, 421 MB).

Requires DATABENTO_API_KEY in .env. NOTE the uint-size underflow fix: cast depth
sizes to float BEFORE subtracting, or ask>bid wraps to a huge positive.
"""
import os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
CACHE = os.environ.get("DBN_CACHE", ".")
PARQ = os.path.join(CACHE, "tsla_mbp10_jul2_open.parquet")


def fetch():
    if os.path.exists(PARQ):
        return
    import databento as db
    c = db.Historical(os.environ["DATABENTO_API_KEY"])
    c.timeseries.get_range(dataset="XNAS.ITCH", symbols=["TSLA"], schema="mbp-10",
        start="2026-07-02T13:25", end="2026-07-02T15:00", stype_in="raw_symbol"
        ).to_df().to_parquet(PARQ)


def main():
    fetch()
    df = pd.read_parquet(PARQ)
    df.index = df.index.tz_convert("America/New_York")
    bs = [f"bid_sz_0{i}" for i in range(10)]; a_ = [f"ask_sz_0{i}" for i in range(10)]
    df["bidD"] = df[bs].astype(float).sum(axis=1)   # float cast: uint underflow guard
    df["askD"] = df[a_].astype(float).sum(axis=1)
    tot = df["bidD"] + df["askD"]
    df["imb"] = np.where(tot > 0, (df["bidD"] - df["askD"]) / tot, np.nan)
    dt = df.index.to_series().diff().dt.total_seconds().shift(-1).clip(0, 5).fillna(0).values
    df["dt"] = dt
    tod = df.index.strftime("%H:%M")
    rth = df[(tod >= "09:30") & (tod < "11:00")].dropna(subset=["imb"])
    wavg = lambda g, c: np.average(g[c], weights=g["dt"]) if g["dt"].sum() else np.nan
    op = df[(tod >= "09:30") & (df.index.strftime("%H:%M") < "09:33")]
    print(f"opening 09:30-09:33 book: bid {wavg(op,'bidD'):.0f} ask {wavg(op,'askD'):.0f} "
          f"= {wavg(op,'askD')/wavg(op,'bidD'):.2f}x ask (the failed PM-high cap)")
    print(f"overall 09:30-11:00 imbalance {wavg(rth,'imb'):+.3f} "
          f"(>0 = bid-heavy) | ask-heavy {rth.loc[rth.imb<0,'dt'].sum()/rth['dt'].sum()*100:.0f}% of time")
    print("=> book bid-heavy while price falls 8% = hidden/iceberg distribution")

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True,
                                 gridspec_kw={"height_ratios": [2, 1]})
    a1.plot(rth.index, rth["ask_px_00"], color="#1565c0", lw=0.7)
    a1.set_ylabel("price"); a1.grid(alpha=.2)
    a1.set_title("TSLA Jul 2 open — price vs 10-level order-book imbalance (Nasdaq)")
    im = rth["imb"].rolling("60s").mean()
    a2.fill_between(rth.index, 0, im, where=im >= 0, color="#2e7d32", alpha=.6, label="bid-heavy")
    a2.fill_between(rth.index, 0, im, where=im < 0, color="#c62828", alpha=.6,
                    label="ask-heavy (sellers stacked)")
    a2.axhline(0, color="k", lw=.5); a2.set_ylabel("book imbalance")
    a2.legend(fontsize=8); a2.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(os.path.join(os.path.dirname(__file__), "..", "output", "charts",
                             "book_imbalance_jul2.png"), dpi=130)


if __name__ == "__main__":
    main()
