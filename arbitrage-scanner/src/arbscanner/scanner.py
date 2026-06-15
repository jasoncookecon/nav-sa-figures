from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .arbitrage import Opportunity, find_opportunity
from .fees import FeeModel, zero_fee
from .matching import match_quotes
from .models import Quote
from .sources.base import MarketSource

log = logging.getLogger("arbscanner")


@dataclass
class ScanConfig:
    match_threshold: float = 0.85
    contracts: int = 1
    min_profit: float = 0.0   # minimum total profit (dollars) to report
    min_roi: float = 0.0      # minimum ROI (fraction) to report


class Scanner:
    """Fetches quotes from every source, matches contracts, and reports arbs."""

    def __init__(
        self,
        sources: list[MarketSource],
        fee_models: Optional[dict[str, FeeModel]] = None,
        config: Optional[ScanConfig] = None,
        manual_map: Optional[dict[str, dict[str, str]]] = None,
    ):
        if len(sources) < 2:
            raise ValueError("need at least two sources to find cross-market arbitrage")
        self.sources = sources
        self.fee_models = fee_models or {}
        self.config = config or ScanConfig()
        # manual_map keyed by "sourceA->sourceB" -> {market_id_a: market_id_b}
        self.manual_map = manual_map or {}

    def _fee(self, source_name: str) -> FeeModel:
        return self.fee_models.get(source_name, zero_fee)

    def fetch_all(self) -> dict[str, list[Quote]]:
        result: dict[str, list[Quote]] = {}
        for s in self.sources:
            try:
                quotes = s.fetch_quotes()
                log.info("fetched %d quotes from %s", len(quotes), s.name)
                result[s.name] = quotes
            except Exception as exc:  # noqa: BLE001 - isolate per-source failure
                log.error("failed to fetch from %s: %s", s.name, exc)
                result[s.name] = []
        return result

    def scan(self) -> list[Opportunity]:
        quotes = self.fetch_all()
        names = [s.name for s in self.sources]
        opportunities: list[Opportunity] = []

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a_name, b_name = names[i], names[j]
                pairs = match_quotes(
                    quotes.get(a_name, []),
                    quotes.get(b_name, []),
                    threshold=self.config.match_threshold,
                    manual_map=self.manual_map.get(f"{a_name}->{b_name}"),
                )
                for p in pairs:
                    opp = find_opportunity(
                        p.a,
                        p.b,
                        match_score=p.score,
                        contracts=self.config.contracts,
                        a_fee=self._fee(a_name),
                        b_fee=self._fee(b_name),
                        flip_b=p.flip_b,
                    )
                    if (
                        opp is not None
                        and opp.is_arbitrage
                        and opp.profit >= self.config.min_profit
                        and opp.roi >= self.config.min_roi
                    ):
                        opportunities.append(opp)

        opportunities.sort(key=lambda o: o.roi, reverse=True)
        return opportunities
