from __future__ import annotations

import json
import logging
from typing import Optional

import requests

from ..models import Quote
from .base import MarketSource

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

log = logging.getLogger("arbscanner")


class PolymarketSource(MarketSource):
    """Polymarket markets via the public Gamma + CLOB APIs.

    Two-step fetch:

    1. **Gamma** (`/markets`) gives the list of binary markets, their titles,
       slugs, and the two CLOB token ids for the Yes/No outcomes. Its
       ``outcomePrices`` are summary/mid prices — used only as a fallback.
    2. **CLOB** (`/books`) gives the real order book per token, from which we
       take the *best ask* (lowest ask price) and the size resting there. This
       is the price you would actually pay and the quantity you could fill, so
       it is what arbitrage detection should use.

    If the CLOB step fails (network/schema), we log a warning and fall back to
    the Gamma mid-prices rather than dropping the whole source. Set
    ``use_clob=False`` to skip the order-book step entirely (faster, but the
    prices are then optimistic mid-prices with no size).
    """

    name = "polymarket"

    def __init__(
        self,
        limit: int = 1000,
        timeout: float = 15.0,
        session: Optional[requests.Session] = None,
        use_clob: bool = True,
        clob_batch: int = 100,
    ):
        self.limit = limit
        self.timeout = timeout
        self.session = session or requests.Session()
        self.use_clob = use_clob
        self.clob_batch = clob_batch

    def fetch_quotes(self) -> list[Quote]:
        # entries: (quote, yes_token_id, no_token_id)
        entries: list[tuple[Quote, Optional[str], Optional[str]]] = []
        for m in self._fetch_gamma_markets():
            parsed = self._parse_market(m)
            if parsed is not None:
                entries.append(parsed)

        if self.use_clob and entries:
            tokens = {t for _, yt, nt in entries for t in (yt, nt) if t}
            try:
                best = self._fetch_best_asks(sorted(tokens))
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "Polymarket CLOB book fetch failed (%s); "
                    "falling back to Gamma mid-prices", exc,
                )
            else:
                for q, yt, nt in entries:
                    self._apply_book(q, "yes", best.get(yt) if yt else None)
                    self._apply_book(q, "no", best.get(nt) if nt else None)

        return [q for q, _, _ in entries]

    # --- Gamma ---------------------------------------------------------------

    def _fetch_gamma_markets(self) -> list[dict]:
        markets: list[dict] = []
        offset = 0
        page = 500
        while offset < self.limit:
            want = min(page, self.limit - offset)
            params = {"closed": "false", "active": "true", "limit": want, "offset": offset}
            resp = self.session.get(f"{GAMMA_API}/markets", params=params, timeout=self.timeout)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            markets.extend(batch)
            offset += len(batch)
            if len(batch) < want:
                break
        return markets

    def _parse_market(self, m: dict):
        outcomes = _loads(m.get("outcomes"))
        prices = _loads(m.get("outcomePrices"))
        tokens = _loads(m.get("clobTokenIds"))
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

        yes_token = no_token = None
        if isinstance(tokens, list) and len(tokens) == 2:
            yes_token, no_token = str(tokens[yi]), str(tokens[ni])

        slug = m.get("slug", "")
        quote = Quote(
            source=self.name,
            market_id=str(m.get("id") or m.get("conditionId") or slug),
            title=m.get("question") or m.get("title") or slug,
            yes_ask=yes_p,  # Gamma fallback; overwritten by CLOB best ask
            no_ask=no_p,
            yes_bid=yes_p,
            no_bid=no_p,
            url=f"https://polymarket.com/event/{slug}" if slug else "",
            liquidity=_to_float(m.get("liquidity")),
            raw=m,
        )
        return quote, yes_token, no_token

    # --- CLOB ----------------------------------------------------------------

    def _fetch_best_asks(self, token_ids: list[str]) -> dict[str, tuple[float, float]]:
        """Map token_id -> (best_ask_price, size_at_best_ask)."""
        best: dict[str, tuple[float, float]] = {}
        for i in range(0, len(token_ids), self.clob_batch):
            chunk = token_ids[i : i + self.clob_batch]
            body = [{"token_id": t} for t in chunk]
            resp = self.session.post(f"{CLOB_API}/books", json=body, timeout=self.timeout)
            resp.raise_for_status()
            for book in resp.json() or []:
                tid = book.get("asset_id") or book.get("token_id")
                levels = []
                for lvl in book.get("asks") or []:
                    try:
                        levels.append((float(lvl["price"]), float(lvl["size"])))
                    except (KeyError, ValueError, TypeError):
                        continue
                if tid and levels:
                    # Best ask = lowest price you can buy at.
                    best[str(tid)] = min(levels, key=lambda x: x[0])
        return best

    @staticmethod
    def _apply_book(quote: Quote, side: str, book: Optional[tuple[float, float]]) -> None:
        if book is None:
            # No resting asks for this token -> mark untradable on that side.
            if side == "yes":
                quote.yes_ask = None
            else:
                quote.no_ask = None
            return
        price, size = book
        if side == "yes":
            quote.yes_ask, quote.yes_ask_size = price, size
        else:
            quote.no_ask, quote.no_ask_size = price, size


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
