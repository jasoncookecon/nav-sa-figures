from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .fees import FeeModel, zero_fee
from .models import Quote

PAYOUT = 1.0  # each winning contract settles at $1


@dataclass
class ArbLeg:
    source: str
    market_id: str
    title: str
    side: str  # "YES" or "NO"
    price: float
    url: str


@dataclass
class Opportunity:
    legs: tuple[ArbLeg, ArbLeg]
    contracts: int
    cost: float          # total cost incl. fees for `contracts` hedged pairs
    payout: float        # guaranteed payout regardless of outcome
    profit: float        # payout - cost
    roi: float           # profit / cost
    match_score: float   # confidence the two markets are the same outcome

    @property
    def is_arbitrage(self) -> bool:
        return self.profit > 0


def _evaluate(
    a: Quote, a_side: str, a_price: float, a_fee: FeeModel,
    b: Quote, b_side: str, b_price: float, b_fee: FeeModel,
    contracts: int, match_score: float,
) -> Opportunity:
    cost = (a_price + b_price) * contracts
    cost += a_fee(a_price, contracts) + b_fee(b_price, contracts)
    payout = PAYOUT * contracts
    profit = payout - cost
    roi = profit / cost if cost > 0 else 0.0
    legs = (
        ArbLeg(a.source, a.market_id, a.title, a_side, a_price, a.url),
        ArbLeg(b.source, b.market_id, b.title, b_side, b_price, b.url),
    )
    return Opportunity(legs, contracts, cost, payout, profit, roi, match_score)


def find_opportunity(
    a: Quote,
    b: Quote,
    match_score: float = 1.0,
    contracts: int = 1,
    a_fee: FeeModel = zero_fee,
    b_fee: FeeModel = zero_fee,
    flip_b: bool = False,
) -> Optional[Opportunity]:
    """Return the more profitable of the two hedge directions, or None.

    The hedge that guarantees a $1 payout is "buy YES on one side and NO on the
    other". We evaluate both assignments and return whichever costs less.

    ``flip_b=True`` means B phrases the event with inverted wording, so B's
    "YES" corresponds to A's "NO". Use it when the same outcome is listed with
    opposite polarity on the two venues.

    The returned Opportunity may have ``is_arbitrage == False``; callers decide
    whether to keep it based on profit/ROI thresholds.
    """
    if not a.tradable or not b.tradable:
        return None

    if flip_b:
        b_yes_ask, b_no_ask = b.no_ask, b.yes_ask
        b_yes_label, b_no_label = "NO", "YES"
    else:
        b_yes_ask, b_no_ask = b.yes_ask, b.no_ask
        b_yes_label, b_no_label = "YES", "NO"

    # Direction 1: YES on A hedged with the opposing side on B.
    d1 = _evaluate(
        a, "YES", a.yes_ask, a_fee,
        b, b_no_label, b_no_ask, b_fee,
        contracts, match_score,
    )
    # Direction 2: NO on A hedged with the opposing side on B.
    d2 = _evaluate(
        a, "NO", a.no_ask, a_fee,
        b, b_yes_label, b_yes_ask, b_fee,
        contracts, match_score,
    )
    return max((d1, d2), key=lambda o: o.profit)
