"""AUDIT (signal & feature gaps): quantify (A) the fidelity of the engine's core
tick-rule signed-volume feature vs Databento quote-verified Lee-Ready flow, and
(B) the intraday signal firing frequency + edge vs a shuffled/random null over the
full cached sample. Prefix: audit_sfg_*.
"""
import os, sys, glob, json
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from tsla_decoded.signal_backtest import compute_features, generate_signals, DEFAULTS

SP = "/tmp/claude-0/-home-user-tsla-decoded/95c77dab-52da-5fc9-b556-40637ad9c184/scratchpad"
ET = "America/New_York"


def load_all_1min():
    frames = []
    for f in glob.glob("data/raw/historical-chart_1min__*.json"):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        rows = d if isinstance(d, list) else d.get("data", d)
        if not rows:
            continue
        df = pd.DataFrame(rows)
        if "date" not in df:
            continue
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(ET, nonexistent="shift_forward", ambiguous=True)
    df = df.sort_values("date").drop_duplicates("date").set_index("date")
    tod = df.index.strftime("%H:%M")
    df["session"] = "regular"
    df.loc[tod < "09:30", "session"] = "pre"
    df.loc[tod > "15:59", "session"] = "post"
    return df[["open", "high", "low", "close", "volume", "session"]]


# ---------------------------------------------------------------------------
# A. tick-rule feature fidelity vs Lee-Ready true aggressor flow
# ---------------------------------------------------------------------------
def lee_ready_1min(day, iso):
    tr = pd.read_parquet(f"{SP}/tsla_trades.parquet")
    q = pd.read_parquet(f"{SP}/tsla_mbp1_{day}.parquet")
    tr.index = tr.index.tz_convert(ET); q.index = q.index.tz_convert(ET)
    dd = pd.Timestamp(iso).date()
    tr = tr[(tr.index.date == dd)].copy()
    q = q[q.index.date == dd][["bid_px_00", "ask_px_00"]]
    q = q[(q.bid_px_00 > 0) & (q.ask_px_00 > 0) & (q.ask_px_00 >= q.bid_px_00)]
    m = pd.merge_asof(tr.sort_index(), q.sort_index(), left_index=True,
                      right_index=True, direction="backward")
    mid = (m.bid_px_00 + m.ask_px_00) / 2
    m["lr"] = np.where(m.price >= m.ask_px_00, 1,
              np.where(m.price <= m.bid_px_00, -1,
              np.where(m.price > mid, 1, np.where(m.price < mid, -1, 0))))
    m["sv"] = m["lr"] * m["size"]
    tod = m.index.strftime("%H:%M")
    m = m[(tod >= "09:30") & (tod < "16:00")]
    # aggregate true signed volume + last price to 1-min bars
    g = m.resample("1min")
    out = pd.DataFrame({
        "true_sv": g["sv"].sum(),
        "true_vol": g["size"].sum(),
        "close": g["price"].last(),
    }).dropna(subset=["close"])
    out["true_imb_bar"] = out["true_sv"] / out["true_vol"].replace(0, np.nan)
    return out


def probe_A():
    print("\n=== PROBE A: tick-rule signed-volume fidelity vs Lee-Ready (Databento) ===")
    for day in ("jun29", "jul2"):
        d = {"jun29": "2026-06-29", "jul2": "2026-07-02"}[day]
        lr = lee_ready_1min(day, d)
        # engine's tick rule: sign of 1-min close-to-close * bar volume
        ret_sign = np.sign(lr["close"].diff())
        tick_sv = ret_sign * lr["true_vol"]   # same bar volume, tick-signed
        tick_imb = ret_sign  # per-bar direction
        df = pd.DataFrame({"true_sv": lr["true_sv"], "tick_sv": tick_sv,
                           "true_imb": lr["true_imb_bar"], "tick_dir": tick_imb}).dropna()
        # bar-level sign agreement between tick rule and true aggressor imbalance
        agree = (np.sign(df["true_imb"]) == df["tick_dir"]).mean()
        corr = df["true_sv"].corr(df["tick_sv"])
        # day-level cumulative signed volume (what the rule's cum_signed uses)
        true_cum = df["true_sv"].sum(); tick_cum = df["tick_sv"].sum()
        # 30-min rolling imbalance the engine actually thresholds at +/-0.20
        rt = df["true_sv"].rolling(30).sum() / df["true_sv"].abs().rolling(30).sum()
        print(f"\n {d}: n_bars={len(df)}")
        print(f"   bar sign-agreement (tick dir == true aggressor dir): {agree:.1%}")
        print(f"   corr(tick_signed_vol, true_signed_vol): {corr:.3f}")
        print(f"   day net: tick_cum={tick_cum/1e6:+.2f}M  true_cum={true_cum/1e6:+.2f}M  "
              f"sign {'MATCH' if np.sign(tick_cum)==np.sign(true_cum) else 'FLIP'}")
        print(f"   true day imbalance = {true_cum/df['true_vol' if 'true_vol' in df else 'true_sv'].abs().sum():+.3f}"
              if False else f"   true day |imb| = {abs(true_cum)/df['true_sv'].abs().sum():.3f}")


# ---------------------------------------------------------------------------
# B. signal frequency + edge vs null over the full cached sample
# ---------------------------------------------------------------------------
def probe_B(bars):
    print("\n=== PROBE B: intraday signal frequency + edge over full cached sample ===")
    # use only the contiguous 2026-04..07 block (legacy single days can't form rolling ctx)
    reg = bars[(bars.index >= "2026-04-01")]
    daily_closes = reg[reg["session"] == "regular"]["close"].groupby(
        reg[reg["session"] == "regular"].index.date).last()
    daily_closes.index = pd.to_datetime(daily_closes.index)
    feat = compute_features(reg, DEFAULTS, daily_closes)
    n_days = len({t.date() for t in feat.index})
    sig = generate_signals(feat, DEFAULTS)
    print(f" contiguous days: {n_days}, total signals: {len(sig)}, "
          f"rate: {len(sig)/n_days:.3f}/day")
    if len(sig):
        print(sig.groupby(["signal", "trigger"]).size().to_string())
    # forward 30/60-min signed returns per signal
    closes = feat["close"]
    rows = []
    for _, r in sig.iterrows():
        for h in (15, 30, 60):
            tgt = r["ts"] + pd.Timedelta(minutes=h)
            db = closes[(closes.index.date == r["ts"].date()) & (closes.index <= tgt)]
            if len(db):
                fwd = (db.iloc[-1] / r["price"] - 1) * 100
                r[f"f{h}"] = fwd if r["signal"] == "BUY" else -fwd
        rows.append(r)
    fwd = pd.DataFrame(rows)
    COST = 0.07  # round-trip: ~1-2bps + half-spread per side ~= 0.06-0.08% for TSLA
    if len(fwd):
        for h in (15, 30, 60):
            c = fwd[f"f{h}"].dropna()
            cw = c.clip(c.quantile(0.02), c.quantile(0.98))  # winsorized (bad-tick guard)
            net = c.median() - COST
            print(f"   +{h}m signed: mean(wins) {cw.mean():+.3f}%  median {c.median():+.3f}%  "
                  f"hit {(c>0).mean():.0%}  n={len(c)}  | net-of-{COST:.2f}%cost median {net:+.3f}%")
        print("   per-trigger (30m median signed %, hit, n):")
        for (sg, tg), g in fwd.groupby(["signal", "trigger"]):
            c = g["f30"].dropna()
            print(f"     {sg}/{tg}: median {c.median():+.3f}%  hit {(c>0).mean():.0%}  n={len(c)}")
        # NULL: random entries matched by count/time-of-day distribution
        rng = np.random.default_rng(7)
        reg_only = feat[feat["min_of_day"].between(30, 330)]
        null_means = []
        for _ in range(2000):
            idx = rng.choice(len(reg_only), size=len(fwd), replace=False)
            samp = reg_only.iloc[idx]
            vals = []
            for ts, pr in zip(samp.index, samp["close"]):
                tgt = ts + pd.Timedelta(minutes=30)
                db = closes[(closes.index.date == ts.date()) & (closes.index <= tgt)]
                if len(db):
                    vals.append(abs(db.iloc[-1] / pr - 1) * 100)  # unsigned move magnitude
            null_means.append(np.mean(vals) if vals else np.nan)
        null_means = np.array([x for x in null_means if not np.isnan(x)])
        obs_abs = fwd["f30"].abs().mean()
        pct = (null_means <= obs_abs).mean()
        print(f"   NULL (random entries, |move| magnitude at 30m): "
              f"obs |signed30| mean={obs_abs:.3f}%, null mean={null_means.mean():.3f}%, "
              f"obs at {pct:.0%} pctile of null")


if __name__ == "__main__":
    os.chdir(os.path.join(os.path.dirname(__file__), "..", ".."))
    probe_A()
    bars = load_all_1min()
    probe_B(bars)
