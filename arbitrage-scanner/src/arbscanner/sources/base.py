from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Quote


class MarketSource(ABC):
    """Interface every venue adapter implements."""

    name: str = "base"

    @abstractmethod
    def fetch_quotes(self) -> list[Quote]:
        """Return current binary-market quotes from this source.

        Implementations should normalize prices to dollars in [0, 1] and may
        raise on network/HTTP errors — the Scanner isolates failures per source.
        """
        raise NotImplementedError
