"""Entrypoint: run the full TSLA price-action investigation.

Usage: python run.py [--refresh] [--max-iters N]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from tsla_decoded import plots, report                      # noqa: E402
from tsla_decoded.config import load_settings               # noqa: E402
from tsla_decoded.fmp_client import FMPClient               # noqa: E402
from tsla_decoded.loop import Investigation, save_events_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="bypass JSON cache")
    parser.add_argument("--max-iters", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    if args.max_iters:
        settings.loop["max_iters"] = args.max_iters

    client = FMPClient(settings.api_key, settings.cache_dir, refresh=args.refresh)
    inv = Investigation(settings, client)
    state = inv.run()

    # sanity cross-check: intraday-derived daily return vs EOD endpoint
    z = state["z5"]
    daily_week = inv.daily.loc[settings.target_start: settings.target_end]
    state["daily_week"] = daily_week
    for day, dz in z.groupby(z.index.date):
        intraday_ret = (dz["close"].iloc[-1] / dz["close"].iloc[0] - 1) * 100
        eod = daily_week[daily_week.index.date == day]
        if not eod.empty:
            eod_ret = (eod["close"].iloc[0] / eod["open"].iloc[0] - 1) * 100
            if abs(intraday_ret - eod_ret) > 0.6:
                logging.warning("intraday vs EOD open-to-close mismatch on %s: %.2f vs %.2f",
                                day, intraday_ret, eod_ret)

    out = settings.output_dir
    (out / "charts").mkdir(parents=True, exist_ok=True)
    save_events_json(state, out / "events.json")

    plots.weekly_overview(inv.daily, state["events"], out / "charts" / "weekly_overview.png")
    for day in sorted({ts.date() for ts in z.index}):
        plots.intraday_day(z, state["events"], state["attributions"], day,
                           state.get("regimes"), out / "charts" / f"intraday_{day}.png")
    plots.decomposition_chart(z, inv.bench_week, inv.market_model,
                              out / "charts" / "decomposition.png")
    plots.dashboard(z, inv.tsla_week_5m, state["events"], state["attributions"],
                    inv.daily, state.get("deliveries_check"), out / "dashboard.html")
    report.write_report(state, settings, out / "report.md")

    print(f"\nDone. {len(state['events'])} events, "
          f"{len(state['events']) - len(state['unresolved'])} attributed at "
          f">= {settings.loop['confidence_threshold']} confidence; "
          f"{client.http_requests} HTTP requests this run.")
    print(f"Outputs: {out}/report.md, {out}/dashboard.html, {out}/charts/")


if __name__ == "__main__":
    main()
