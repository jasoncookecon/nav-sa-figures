from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

try:  # rapidfuzz is optional; we fall back to a Jaccard token overlap.
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None

from .models import Quote

_STOPWORDS = {
    "will", "the", "a", "an", "to", "be", "of", "in", "on", "by",
    "for", "at", "is", "are", "and", "or", "this", "that",
}


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, and drop filler words for comparison."""
    text = title.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    tokens = [t for t in text.split() if t and t not in _STOPWORDS]
    return " ".join(tokens)


def similarity(a: str, b: str) -> float:
    """Title similarity in [0, 1]. Uses rapidfuzz when available."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if fuzz is not None:
        return fuzz.token_set_ratio(na, nb) / 100.0
    sa, sb = set(na.split()), set(nb.split())
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


@dataclass
class MatchPair:
    a: Quote
    b: Quote
    score: float
    flip_b: bool = False


def match_quotes(
    group_a: list[Quote],
    group_b: list[Quote],
    threshold: float = 0.85,
    manual_map: Optional[dict[str, str]] = None,
) -> list[MatchPair]:
    """Greedily pair markets across two sources by title similarity.

    Each market in ``group_b`` is used at most once. ``manual_map`` forces a
    pairing by mapping a ``market_id`` in A to a ``market_id`` in B, overriding
    similarity entirely — the escape hatch for events the matcher misses or
    gets wrong (the single most error-prone part of cross-market arbitrage).
    """
    pairs: list[MatchPair] = []
    used_b: set[str] = set()
    manual_map = manual_map or {}
    b_by_id = {q.market_id: q for q in group_b}

    for qa in group_a:
        forced = manual_map.get(qa.market_id)
        if forced and forced in b_by_id and forced not in used_b:
            pairs.append(MatchPair(qa, b_by_id[forced], 1.0))
            used_b.add(forced)
            continue

        best_q: Optional[Quote] = None
        best_s = 0.0
        for qb in group_b:
            if qb.market_id in used_b:
                continue
            s = similarity(qa.title, qb.title)
            if s > best_s:
                best_s, best_q = s, qb

        if best_q is not None and best_s >= threshold:
            pairs.append(MatchPair(qa, best_q, best_s))
            used_b.add(best_q.market_id)

    return pairs
