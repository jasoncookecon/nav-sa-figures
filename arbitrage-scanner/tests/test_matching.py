from arbscanner.matching import match_quotes, normalize_title, similarity
from arbscanner.models import Quote


def test_normalize_strips_stopwords_and_punctuation():
    assert normalize_title("Will the Fed cut rates in July?") == "fed cut rates july"


def test_identical_meaning_scores_high():
    s = similarity(
        "Will the Fed cut rates in July?",
        "Fed to cut rates in July",
    )
    assert s >= 0.8


def test_unrelated_titles_score_low():
    s = similarity(
        "Will it rain in Seattle tomorrow?",
        "Who will win the Super Bowl?",
    )
    assert s < 0.5


def _q(src, mid, title):
    return Quote(source=src, market_id=mid, title=title, yes_ask=0.5, no_ask=0.5)


def test_match_quotes_pairs_best_candidate():
    a = [_q("kalshi", "K1", "Will the Fed cut rates in July?")]
    b = [
        _q("poly", "P1", "Who wins the Super Bowl?"),
        _q("poly", "P2", "Fed cuts rates in July"),
    ]
    pairs = match_quotes(a, b, threshold=0.55)
    assert len(pairs) == 1
    assert pairs[0].b.market_id == "P2"


def test_manual_map_overrides_similarity():
    a = [_q("kalshi", "K1", "totally different wording xyz")]
    b = [_q("poly", "P9", "nothing alike abc")]
    pairs = match_quotes(a, b, threshold=0.99, manual_map={"K1": "P9"})
    assert len(pairs) == 1
    assert pairs[0].score == 1.0


def test_each_b_used_at_most_once():
    a = [
        _q("kalshi", "K1", "Fed cuts rates in July"),
        _q("kalshi", "K2", "Fed cuts rates in July"),
    ]
    b = [_q("poly", "P1", "Fed cuts rates in July")]
    pairs = match_quotes(a, b, threshold=0.55)
    assert len(pairs) == 1
