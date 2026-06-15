from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from typing import Iterable, Optional

from .arbitrage import Opportunity

FIELDNAMES = [
    "scan_time",
    "roi",
    "profit_per_contract",
    "total_profit",
    "cost",
    "contracts",
    "match_score",
    "available_size",
    "a_source", "a_market_id", "a_side", "a_price", "a_size", "a_title", "a_url",
    "b_source", "b_market_id", "b_side", "b_price", "b_size", "b_title", "b_url",
]


def _num(value) -> str:
    return "" if value is None else f"{value:.4f}"


def _row(o: Opportunity, scan_time: str) -> dict:
    a, b = o.legs
    per_ct = o.profit / o.contracts if o.contracts else 0.0
    return {
        "scan_time": scan_time,
        "roi": f"{o.roi:.6f}",
        "profit_per_contract": f"{per_ct:.6f}",
        "total_profit": f"{o.profit:.6f}",
        "cost": f"{o.cost:.6f}",
        "contracts": o.contracts,
        "match_score": f"{o.match_score:.4f}",
        "available_size": _num(o.available_size),
        "a_source": a.source, "a_market_id": a.market_id, "a_side": a.side,
        "a_price": f"{a.price:.4f}", "a_size": _num(a.size),
        "a_title": a.title, "a_url": a.url,
        "b_source": b.source, "b_market_id": b.market_id, "b_side": b.side,
        "b_price": f"{b.price:.4f}", "b_size": _num(b.size),
        "b_title": b.title, "b_url": b.url,
    }


def append_opportunities(
    path: str,
    opportunities: Iterable[Opportunity],
    scan_time: Optional[str] = None,
) -> int:
    """Append opportunities to a CSV, writing the header for a new/empty file.

    All rows from one call share a single ``scan_time`` (UTC ISO-8601 by
    default) so you can group a scan and measure how long each edge survives
    across successive scans. Returns the number of rows written.
    """
    opportunities = list(opportunities)
    if not opportunities:
        return 0
    if scan_time is None:
        scan_time = datetime.now(timezone.utc).isoformat()

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()
        for o in opportunities:
            writer.writerow(_row(o, scan_time))
    return len(opportunities)
