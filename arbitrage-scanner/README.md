# Prediction-Market Arbitrage Scanner

A **read-only** scanner that watches multiple prediction markets, matches
contracts that represent the same real-world outcome, and reports
**arbitrage opportunities** after fees.

It deliberately **does not place trades**. The goal of this first phase is to
answer one question honestly: *do real, executable arbitrage opportunities
actually show up often enough to be worth building an execution engine for?*

> ⚠️ This is a feasibility / research tool. Read [Caveats](#caveats-read-this)
> before you trust any number it prints, and never commit account keys.

---

## Why "scanner first"

The hard parts of automated cross-market arbitrage are **not** the math:

1. **Matching** — "Will the Fed cut rates in July?" on one venue vs. "Fed July
   rate decision: Cut" on another. Getting this wrong means you buy two
   *different* bets and lose. This is the #1 failure mode.
2. **Speed** — edges vanish in seconds; a half-filled hedge is naked risk.
3. **Thin liquidity** — an edge that only clears $20 isn't worth the effort.
4. **Resolution-rule risk** — two markets can look identical but settle
   differently (timing, "void" conditions).

A scanner exposes all four *without* risking a cent. If genuine, persistent,
liquid edges show up here, an execution layer is justified. If they don't,
you've saved yourself from building one.

## What it does

```
sources (Kalshi, Polymarket, …)
        │  fetch normalized Yes/No quotes (prices in dollars, 0..1)
        ▼
   matching  ──►  pair markets by title similarity (rapidfuzz) + manual overrides
        ▼
  arbitrage  ──►  cost of hedged pair (YES@A + NO@B) vs. $1 payout, minus fees
        ▼
   scanner   ──►  filter by min profit / ROI, sort, print
```

## Install

```bash
cd arbitrage-scanner
python -m venv .venv && source .venv/bin/activate
pip install -e .          # or: pip install -r requirements.txt
```

## Run

```bash
# single scan with default sources (Kalshi + Polymarket), verbose fetch logs
arbscanner --once -v

# use a config file and loop every 30s
cp config.example.yaml config.yaml
arbscanner -c config.yaml --interval 30
```

Output is a table of opportunities sorted by ROI, e.g.:

```
ROI    Profit/ct  Match  Leg A                              Leg B
3.1%   $0.030     91%    kalshi:YES 0.41 Fed cuts in July   polymarket:NO 0.56 Fed cuts rate…
```

## Configuration

See [`config.example.yaml`](config.example.yaml). Key knobs:

| Setting | Meaning |
| --- | --- |
| `sources[].type` | `kalshi` or `polymarket` |
| `sources[].fees` | `{type: kalshi}`, `{type: flat_bps, bps: N}`, or `{type: zero}` |
| `scan.match_threshold` | 0..1 title similarity to call two markets "the same" |
| `scan.contracts` | position size used for profit/fee math |
| `scan.min_profit` / `min_roi` | thresholds below which opportunities are hidden |
| `manual_map` | force/override contract pairings the matcher gets wrong |

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Tests cover the pure logic — arbitrage math, fee models, and title matching —
with no network calls, so they run anywhere.

## Architecture

```
src/arbscanner/
  models.py            # Quote dataclass (normalized Yes/No quote)
  fees.py              # fee models: zero, flat_bps, kalshi
  arbitrage.py         # hedge math -> Opportunity
  matching.py          # title normalization + fuzzy matching + manual map
  scanner.py           # orchestration: fetch -> match -> detect -> filter
  cli.py               # argparse entrypoint + table output
  sources/
    base.py            # MarketSource interface
    kalshi.py          # Kalshi public market-data feed
    polymarket.py      # Polymarket Gamma API
```

Adding a venue = implement `MarketSource.fetch_quotes()` returning `Quote`s and
register it in `cli.SOURCE_REGISTRY`.

## Caveats (read this)

- **Polymarket prices are approximate.** The Gamma API returns summary/mid
  prices, not the live order-book ask. Reported edges are *optimistic*; an
  execution layer must pull the real CLOB book (best ask + size) first.
- **Matching is heuristic.** Always sanity-check a pair before trusting it, and
  use `manual_map` for anything important. Identical wording ≠ identical
  resolution rules.
- **Fees/slippage are modeled, not exact.** Withdrawal costs, gas, and partial
  fills are not yet captured.
- **No execution, by design.** See the roadmap below.

## Roadmap (phase 2+, only if phase 1 proves it out)

1. Pull real order-book depth (Kalshi + Polymarket CLOB) for true asks & size.
2. Persist scans to spot how long edges actually survive (the make-or-break
   metric).
3. Alerting (Discord/Telegram/email) on qualifying edges.
4. **Execution** — only on venues with official, ToS-compliant trading APIs
   (Kalshi, Polymarket). Requires authenticated keys, atomic two-leg fills,
   pre-funded balances per venue, and hard risk limits. Traditional sportsbooks
   are intentionally excluded: most prohibit automated betting in their ToS.

## Legal / responsible use

Automated trading via **official public APIs** (Kalshi, Polymarket) is
supported by those venues. Automating sites that prohibit bots in their terms
of service is not supported here. Check your jurisdiction's rules on prediction
markets, and never commit API keys or account credentials.

---

## Moving this into its own repo

This project currently lives in a subfolder of another repository. To give it
its own standalone repo with history preserved:

**Option A — GitHub UI (simplest):** create a new empty repo on github.com,
then locally:

```bash
git subtree split -P arbitrage-scanner -b arb-scanner-only
git push https://github.com/<you>/prediction-market-arb-scanner.git arb-scanner-only:main
```

**Option B — fresh history:** copy the `arbitrage-scanner/` folder into a new
empty directory, then `git init && git add . && git commit && git remote add
origin … && git push -u origin main`.

Either way the contents of `arbitrage-scanner/` become the root of the new repo.
