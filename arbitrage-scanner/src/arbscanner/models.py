from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Quote:
    """A binary (Yes/No) market quote from a single source.

    All prices are expressed in dollars in the range [0, 1] — i.e. the cost to
    buy one contract that pays $1 if the outcome resolves in your favour.

    ``*_ask`` is the price you pay to BUY a contract.
    ``*_bid`` is the price you receive to SELL a contract.

    Arbitrage detection only needs the ask prices, but bids are carried through
    so a later execution layer can reason about exit liquidity.
    """

    source: str
    market_id: str
    title: str
    yes_ask: Optional[float]
    no_ask: Optional[float]
    yes_bid: Optional[float] = None
    no_bid: Optional[float] = None
    # Size (in contracts) resting at the best ask, when the source exposes
    # real order-book depth. None means "unknown / not provided".
    yes_ask_size: Optional[float] = None
    no_ask_size: Optional[float] = None
    url: str = ""
    liquidity: Optional[float] = None
    close_time: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def tradable(self) -> bool:
        """True when both sides have a real ask we could buy against."""
        return (
            self.yes_ask is not None
            and self.no_ask is not None
            and self.yes_ask > 0
            and self.no_ask > 0
        )
