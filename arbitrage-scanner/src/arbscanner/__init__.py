"""arbscanner: read-only cross-platform prediction-market arbitrage scanner.

This package fetches live binary-market quotes from multiple prediction
markets, matches contracts that represent the same real-world outcome, and
reports arbitrage opportunities after accounting for fees. It does NOT place
trades — it is a feasibility / monitoring tool by design.
"""

__version__ = "0.1.0"
