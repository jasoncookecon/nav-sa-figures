from __future__ import annotations

import json
from typing import Optional

import requests

from ..models import Quote
from .base import MarketSource

GAMMA_API = "https://gamma-api.polymarket.com"


class PolymarketSource(MarketSource):
    """Polymarket markets via the public Gamma API.

    IMPORTANT CAVEAT: Gamma's ``outcomePrices`` are summary/mid prices, not the
    live order-book ask. They are good enough to FLAG candidate arbitrage for a
    feasibility study, but an execution layer must pull the real CLOB order book
    (best ask + available size) before trusting any edge. Reported opportunities
    using these prices should be treated as optimistic.
    """

    name = "polymarket"

    def __init__(
        self,
        limit: int = 1000,
        timeout: float = 15.0,
        session: Optional[requests.Session] = None,
    ):
        self.limit = limit
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch_quotes(self) -> list[Quote]:
        quotes: list[Quote] = []
        offset = 0
        page = 500
        while offset < self.limit:
            want = min(page, self.limit - offset)
            params = {
                "closed": "false",
                "active": "true",
                "limit": want,
                "offset": offset,
            }
            resp = self.session.get(
                f"{GAMMA_API}/markets", params=params, timeout=self.timeout
            )
            resp.raise_for_status()
            markets = resp.json()
            if not markets:
                break
            for m in markets:
                q = self._to_quote(m)
                if q is not None:
                    quotes.append(q)
            offset += len(markets)
            if len(markets) < want:
                break
        return quotes

    def _to_quote(self, m: dict) -> Optional[Quote]:
        outcomes = _loads(m.get("outcomes"))
        prices = _loads(m.get("outcomePrices"))
        if not outcomes or not prices or len(outcomes) != 2 or len(prices) != 2:
            return None  # skip multi-outcome / malformed markets

        lower = [str(o).strip().lower() for o in outcomes]
        if "yes" in lower and "no" in lower:
            yi, ni = lower.index("yes"), lower.index("no")
        else:
            yi, ni = 0, 1
        try:
            yes_p = float(prices[yi])
            no_p = float(prices[ni])
        except (ValueError, TypeError):
            return None

        slug = m.get("slug", "")
        return Quote(
            source=self.name,
            market_id=str(m.get("id") or m.get("conditionId") or slug),
            title=m.get("question") or m.get("title") or slug,
            yes_ask=yes_p,
            no_ask=no_p,
            yes_bid=yes_p,
            no_bid=no_p,
            url=f"https://polymarket.com/event/{slug}" if slug else "",
            liquidity=_to_float(m.get("liquidity")),
            raw=m,
        )


def _loads(value):
    if value is None:
        return None
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
