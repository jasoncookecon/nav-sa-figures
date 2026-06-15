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

# log every opportunity to a timestamped CSV (great for an overnight run)
arbscanner --interval 30 --log opportunities.csv
```

### Measuring edge persistence

`--log FILE` (or `scan.log_file` in config) appends one row per opportunity per
scan, all sharing that scan's UTC timestamp. Let it run on a loop and you can
answer the question that actually decides feasibility: **how long does a given
edge survive?** Group rows by the market pair (`a_market_id` + `b_market_id`)
and look at the spread of `scan_time` values — an edge that appears in one scan
and is gone the next is not executable by hand; one that persists for minutes
across many dollars of size is worth building execution for.

Columns: `scan_time, roi, profit_per_contract, total_profit, cost, contracts,
match_score, available_size`, plus `a_*` / `b_*` leg details (source,
market_id, side, price, size, title, url).

Then summarize how long edges actually lasted:

```bash
arbscanner-analyze opportunities.csv --top 20            # rank by persistence
arbscanner-analyze opportunities.csv --sort roi          # rank by max ROI
```

It groups rows by market pair and reports, per edge: how many scans it appeared
in, the span between first and last sighting, max/mean ROI, and max executable
size. The headline number — *edges seen in >1 scan* — is your feasibility
signal. `available_size` / `maxSize` is populated only when **both** venues
expose order-book depth; today that's Polymarket (see roadmap for Kalshi).

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
  opportunity_logger.py # append opportunities to a timestamped CSV
  analyze.py           # edge-persistence stats over a logged CSV
  cli.py               # argparse entrypoint + table output
  sources/
    base.py            # MarketSource interface
    kalshi.py          # Kalshi public market-data feed
    polymarket.py      # Polymarket Gamma (listings) + CLOB (best ask + size)
```

Adding a venue = implement `MarketSource.fetch_quotes()` returning `Quote`s and
register it in `cli.SOURCE_REGISTRY`.

## Caveats (read this)

- **Polymarket now uses the real CLOB best ask + size** by default
  (`use_clob: true`). If the order-book call fails it falls back to Gamma
  mid-prices and logs a warning; with `use_clob: false` it uses mid-prices
  always (faster, but optimistic and sizeless).
- **Kalshi has no depth yet.** The Kalshi feed provides best bid/ask but not
  resting size, so `available_size` is blank for any pair involving Kalshi.
  Pulling Kalshi order-book depth (ideally only for matched pairs) is the next
  roadmap item.
- **Matching is heuristic.** Always sanity-check a pair before trusting it, and
  use `manual_map` for anything important. Identical wording ≠ identical
  resolution rules.
- **Fees/slippage are modeled, not exact.** Withdrawal costs, gas, and partial
  fills are not yet captured.
- **No execution, by design.** See the roadmap below.

## Roadmap (phase 2+, only if phase 1 proves it out)

1. ~~Polymarket CLOB best ask + size~~ ✅ done. Remaining: Kalshi order-book
   depth (per-market endpoint, ideally fetched only for matched pairs to keep
   request volume sane) so `available_size` covers Kalshi×Polymarket pairs.
2. ~~Persist scans + analyze edge persistence~~ ✅ done (`--log` +
   `arbscanner-analyze`). Next: chart persistence over a multi-day run.
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
