from __future__ import annotations

import math
from typing import Callable

# A fee model maps (price_per_contract, n_contracts) -> total fee in dollars.
FeeModel = Callable[[float, int], float]


def zero_fee(price: float, contracts: int) -> float:
    """No trading fee (e.g. Polymarket's current taker fee of 0)."""
    return 0.0


def flat_bps(bps: float) -> FeeModel:
    """Fee as basis points of notional (price * contracts).

    100 bps = 1%. Useful as a catch-all buffer for spread/gas/withdrawal costs.
    """

    def model(price: float, contracts: int) -> float:
        return (bps / 10_000.0) * price * contracts

    return model


def kalshi_fee(price: float, contracts: int) -> float:
    """Kalshi trading fee: ceil(0.07 * C * P * (1 - P)), rounded up to the cent.

    See https://kalshi.com/docs/fees. The fee peaks near P = 0.50 and falls to
    ~0 at the extremes, which is why a near-even arb can still be profitable.
    """
    raw_cents = 0.07 * contracts * price * (1.0 - price) * 100.0
    # Subtract a tiny epsilon so floating-point noise (e.g. 175.00000000000003)
    # doesn't spuriously round a whole-cent fee up to the next cent.
    return math.ceil(raw_cents - 1e-9) / 100.0


def build_fee_model(spec: dict) -> FeeModel:
    """Construct a fee model from a config dict, e.g. {"type": "kalshi"}."""
    kind = (spec or {}).get("type", "zero")
    if kind == "zero":
        return zero_fee
    if kind == "kalshi":
        return kalshi_fee
    if kind == "flat_bps":
        return flat_bps(float(spec.get("bps", 0)))
    raise ValueError(f"unknown fee model: {kind!r}")
