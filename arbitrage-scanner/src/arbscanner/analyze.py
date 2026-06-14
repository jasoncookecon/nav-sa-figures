"""Edge-persistence analysis over a logged opportunities CSV.

The point of logging is to answer: *how long does a given arbitrage edge
actually survive?* A one-scan flicker is not executable by hand and barely so
automated; an edge that persists across many scans and real size is the thing
worth building execution for. This module groups logged rows by market pair and
reports how long and how strongly each edge lasted.

Run:  arbscanner-analyze opportunities.csv --top 20
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional


@dataclass
class EdgeStats:
    key: tuple[str, str, str, str]  # (a_source, a_market_id, b_source, b_market_id)
    title: str
    scan_times: list[datetime]
    max_roi: float
    mean_roi: float
    max_size: Optional[float]

    @property
    def count(self) -> int:
        return len(self.scan_times)

    @property
    def first(self) -> datetime:
        return self.scan_times[0]

    @property
    def last(self) -> datetime:
        return self.scan_times[-1]

    @property
    def span_seconds(self) -> float:
        return (self.last - self.first).total_seconds()


def _key(row: dict) -> tuple[str, str, str, str]:
    return (
        row.get("a_source", ""), row.get("a_market_id", ""),
        row.get("b_source", ""), row.get("b_market_id", ""),
    )


def _parse_time(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _maybe_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def summarize(rows: Iterable[dict]) -> list[EdgeStats]:
    """Group rows by market pair into per-edge persistence stats."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault(_key(row), []).append(row)

    edges: list[EdgeStats] = []
    for key, group in groups.items():
        times, rois, sizes = [], [], []
        for r in group:
            t = _parse_time(r.get("scan_time", ""))
            if t is not None:
                times.append(t)
            roi = _maybe_float(r.get("roi"))
            if roi is not None:
                rois.append(roi)
            sz = _maybe_float(r.get("available_size"))
            if sz is not None:
                sizes.append(sz)
        if not times:
            continue
        edges.append(
            EdgeStats(
                key=key,
                title=group[0].get("a_title", ""),
                scan_times=sorted(times),
                max_roi=max(rois) if rois else 0.0,
                mean_roi=sum(rois) / len(rois) if rois else 0.0,
                max_size=max(sizes) if sizes else None,
            )
        )
    return edges


def load_rows(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _fmt_span(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.1f}min"
    return f"{seconds / 3600:.1f}h"


def build_report(rows: list[dict], top: int = 20, sort: str = "persistence") -> str:
    edges = summarize(rows)
    all_times = sorted(t for e in edges for t in e.scan_times)
    n_scans = len({t.isoformat() for t in all_times})
    persistent = [e for e in edges if e.count > 1]

    lines: list[str] = []
    if not edges:
        return "No opportunities in log — nothing to analyze yet."

    span = ""
    if all_times:
        span = f" ({all_times[0].isoformat()} .. {all_times[-1].isoformat()})"
    lines.append(f"Distinct scans logged: {n_scans}{span}")
    lines.append(f"Distinct edges (market pairs): {len(edges)}")
    pct = 100 * len(persistent) / len(edges) if edges else 0
    lines.append(f"Edges seen in >1 scan: {len(persistent)} ({pct:.0f}%)")
    lines.append("")

    if sort == "roi":
        edges.sort(key=lambda e: e.max_roi, reverse=True)
        heading = f"Top {min(top, len(edges))} edges by max ROI:"
    else:
        edges.sort(key=lambda e: (e.span_seconds, e.count), reverse=True)
        heading = f"Top {min(top, len(edges))} edges by persistence:"
    lines.append(heading)
    lines.append(f"{'scans':>5}  {'span':>8}  {'maxROI':>7}  {'maxSize':>8}  pair / title")
    for e in edges[:top]:
        size = "?" if e.max_size is None else f"{e.max_size:.0f}"
        pair = f"{e.key[0]}:{e.key[1]} / {e.key[2]}:{e.key[3]}"
        lines.append(
            f"{e.count:>5}  {_fmt_span(e.span_seconds):>8}  "
            f"{e.max_roi * 100:>6.1f}%  {size:>8}  {pair}  | {e.title[:50]}"
        )
    return "\n".join(lines)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description="Analyze edge persistence in a logged opportunities CSV.",
    )
    p.add_argument("csv", help="path to the opportunities CSV written by --log")
    p.add_argument("--top", type=int, default=20, help="rows to show (default: 20)")
    p.add_argument(
        "--sort", choices=("persistence", "roi"), default="persistence",
        help="rank edges by how long they lasted (default) or by max ROI",
    )
    args = p.parse_args(argv)
    print(build_report(load_rows(args.csv), top=args.top, sort=args.sort))


if __name__ == "__main__":
    main()
