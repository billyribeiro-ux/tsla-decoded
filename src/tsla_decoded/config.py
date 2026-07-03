"""Settings loaded from config.yaml + .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    api_key: str
    symbol: str
    target_start: str
    target_end: str
    baseline_start: str
    baseline_end: str
    daily_start: str
    daily_end: str
    benchmarks: list[str]
    peers: list[str]
    news_start: str
    news_end: str
    detection: dict = field(default_factory=dict)
    loop: dict = field(default_factory=dict)
    cache_dir: Path = REPO_ROOT / "data" / "raw"
    output_dir: Path = REPO_ROOT / "output"


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("FMP_API_KEY", "")
    if not api_key:
        raise SystemExit("FMP_API_KEY not set — copy .env.example to .env and add your key")

    cfg = yaml.safe_load((config_path or REPO_ROOT / "config.yaml").read_text())
    paths = cfg.get("paths", {})
    return Settings(
        api_key=api_key,
        symbol=cfg["symbol"],
        target_start=cfg["target"]["start"],
        target_end=cfg["target"]["end"],
        baseline_start=cfg["baseline"]["start"],
        baseline_end=cfg["baseline"]["end"],
        daily_start=cfg["daily"]["start"],
        daily_end=cfg["daily"]["end"],
        benchmarks=cfg["benchmarks"],
        peers=cfg["peers"],
        news_start=cfg["news"]["start"],
        news_end=cfg["news"]["end"],
        detection=cfg["detection"],
        loop=cfg["loop"],
        cache_dir=REPO_ROOT / paths.get("cache_dir", "data/raw"),
        output_dir=REPO_ROOT / paths.get("output_dir", "output"),
    )
