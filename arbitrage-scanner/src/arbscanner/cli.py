from __future__ import annotations

import argparse
import logging
import time
from typing import Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from .fees import build_fee_model
from .opportunity_logger import append_opportunities
from .scanner import ScanConfig, Scanner
from .sources.kalshi import KalshiSource
from .sources.polymarket import PolymarketSource

SOURCE_REGISTRY = {
    "kalshi": KalshiSource,
    "polymarket": PolymarketSource,
}

_SOURCE_KWARGS = ("limit", "status", "timeout")


def load_config(path: Optional[str]) -> dict:
    if not path:
        return {}
    if yaml is None:
        raise SystemExit("pyyaml is required to read config files: pip install pyyaml")
    with open(path) as f:
        return yaml.safe_load(f) or {}


def build_from_config(cfg: dict) -> Scanner:
    source_specs = cfg.get("sources") or [{"type": "kalshi"}, {"type": "polymarket"}]
    sources = []
    fee_models = {}
    for spec in source_specs:
        kind = spec["type"]
        cls = SOURCE_REGISTRY[kind]
        kwargs = {k: v for k, v in spec.items() if k in _SOURCE_KWARGS}
        sources.append(cls(**kwargs))
        if "fees" in spec:
            fee_models[kind] = build_fee_model(spec["fees"])

    sc = cfg.get("scan", {})
    config = ScanConfig(
        match_threshold=sc.get("match_threshold", 0.85),
        contracts=sc.get("contracts", 1),
        min_profit=sc.get("min_profit", 0.0),
        min_roi=sc.get("min_roi", 0.0),
    )
    return Scanner(
        sources,
        fee_models=fee_models,
        config=config,
        manual_map=cfg.get("manual_map", {}),
    )


def print_opportunities(opps) -> None:
    if not opps:
        print("No arbitrage opportunities found this scan.")
        return
    try:
        from rich.console import Console
        from rich.table import Table

        title = f"{len(opps)} arbitrage opportunit{'y' if len(opps) == 1 else 'ies'}"
        table = Table(title=title)
        for col in ("ROI", "Profit/ct", "Match", "Leg A", "Leg B"):
            table.add_column(col)
        for o in opps:
            a, b = o.legs
            table.add_row(
                f"{o.roi * 100:.1f}%",
                f"${o.profit / o.contracts:.3f}",
                f"{o.match_score * 100:.0f}%",
                f"{a.source}:{a.side} {a.price:.2f} {a.title[:40]}",
                f"{b.source}:{b.side} {b.price:.2f} {b.title[:40]}",
            )
        Console().print(table)
    except ImportError:
        for o in opps:
            a, b = o.legs
            print(
                f"[{o.roi * 100:5.1f}% ROI] "
                f"{a.source}:{a.side}@{a.price:.2f} + {b.source}:{b.side}@{b.price:.2f} | "
                f"{a.title[:50]} <=> {b.title[:50]}"
            )


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description="Scan prediction markets for cross-platform arbitrage (read-only).",
    )
    p.add_argument("-c", "--config", help="path to YAML config")
    p.add_argument("--once", action="store_true", help="run a single scan and exit")
    p.add_argument(
        "--interval", type=float, default=60.0,
        help="seconds between scans in loop mode (default: 60)",
    )
    p.add_argument(
        "--log", metavar="CSV",
        help="append every opportunity to this CSV (overrides scan.log_file in config)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="log fetch progress")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cfg = load_config(args.config)
    scanner = build_from_config(cfg)
    log_path = args.log or (cfg.get("scan") or {}).get("log_file")

    while True:
        opps = scanner.scan()
        print_opportunities(opps)
        if log_path:
            n = append_opportunities(log_path, opps)
            if n:
                print(f"Logged {n} opportunit{'y' if n == 1 else 'ies'} to {log_path}")
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
