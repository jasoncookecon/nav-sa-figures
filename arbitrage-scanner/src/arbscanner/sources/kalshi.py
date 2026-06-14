from __future__ import annotations

from typing import Optional

import requests

from ..models import Quote
from .base import MarketSource

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiSource(MarketSource):
    """Kalshi public markets feed.

    Uses the unauthenticated market data endpoint, which is sufficient for
    read-only scanning. Prices come back in cents (1..99) and are converted to
    dollars. Placing trades would require API-key authentication (a later
    execution phase, intentionally out of scope here).
    """

    name = "kalshi"

    def __init__(
        self,
        limit: int = 1000,
        status: str = "open",
        timeout: float = 15.0,
        session: Optional[requests.Session] = None,
    ):
        self.limit = limit
        self.status = status
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch_quotes(self) -> list[Quote]:
        quotes: list[Quote] = []
        cursor: Optional[str] = None
        fetched = 0
        while fetched < self.limit:
            params: dict[str, object] = {
                "limit": min(1000, self.limit - fetched),
                "status": self.status,
            }
            if cursor:
                params["cursor"] = cursor
            resp = self.session.get(
                f"{KALSHI_API}/markets", params=params, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            markets = data.get("markets", [])
            for m in markets:
                quotes.append(self._to_quote(m))
            fetched += len(markets)
            cursor = data.get("cursor")
            if not cursor or not markets:
                break
        return quotes

    @staticmethod
    def _cents(value) -> Optional[float]:
        # 0 means "no resting offer", which we treat as untradable.
        if value in (None, 0):
            return None
        return value / 100.0

    def _to_quote(self, m: dict) -> Quote:
        ticker = m.get("ticker", "")
        return Quote(
            source=self.name,
            market_id=ticker,
            title=m.get("title") or m.get("subtitle") or ticker,
            yes_ask=self._cents(m.get("yes_ask")),
            no_ask=self._cents(m.get("no_ask")),
            yes_bid=self._cents(m.get("yes_bid")),
            no_bid=self._cents(m.get("no_bid")),
            url=f"https://kalshi.com/markets/{ticker}",
            liquidity=m.get("liquidity"),
            raw=m,
        )
