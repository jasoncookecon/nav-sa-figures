"""Offline tests for the Polymarket source using a stubbed HTTP session."""

from arbscanner.sources.polymarket import PolymarketSource


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _StubSession:
    """Returns canned Gamma markets and CLOB books regardless of params."""

    def __init__(self, gamma, books):
        self._gamma = gamma
        self._books = books
        self.get_calls = 0
        self.post_calls = 0

    def get(self, url, params=None, timeout=None):
        self.get_calls += 1
        # First page returns the markets; subsequent pages return empty.
        if (params or {}).get("offset", 0) == 0:
            return _Resp(self._gamma)
        return _Resp([])

    def post(self, url, json=None, timeout=None):
        self.post_calls += 1
        return _Resp(self._books)


_GAMMA = [
    {
        "id": "M1",
        "slug": "fed-cuts-july",
        "question": "Will the Fed cut rates in July?",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.40", "0.60"]',
        "clobTokenIds": '["TY", "TN"]',
        "liquidity": "12345",
    }
]

_BOOKS = [
    {"asset_id": "TY", "asks": [{"price": "0.45", "size": "50"}, {"price": "0.42", "size": "100"}]},
    {"asset_id": "TN", "asks": [{"price": "0.55", "size": "200"}]},
]


def test_clob_best_ask_and_size_override_gamma():
    src = PolymarketSource(limit=10, session=_StubSession(_GAMMA, _BOOKS), use_clob=True)
    quotes = src.fetch_quotes()
    assert len(quotes) == 1
    q = quotes[0]
    # Best ask = lowest price level, with its size.
    assert q.yes_ask == 0.42
    assert q.yes_ask_size == 100
    assert q.no_ask == 0.55
    assert q.no_ask_size == 200
    assert q.title == "Will the Fed cut rates in July?"
    assert q.tradable


def test_use_clob_false_keeps_gamma_midprices():
    session = _StubSession(_GAMMA, _BOOKS)
    src = PolymarketSource(limit=10, session=session, use_clob=False)
    q = src.fetch_quotes()[0]
    assert q.yes_ask == 0.40
    assert q.no_ask == 0.60
    assert q.yes_ask_size is None
    assert session.post_calls == 0  # never touched the order book


def test_missing_asks_marks_side_untradable():
    books = [{"asset_id": "TY", "asks": [{"price": "0.42", "size": "100"}]}]  # TN absent
    src = PolymarketSource(limit=10, session=_StubSession(_GAMMA, books), use_clob=True)
    q = src.fetch_quotes()[0]
    assert q.yes_ask == 0.42
    assert q.no_ask is None  # no book for the No token
    assert not q.tradable


class _PagingSession:
    """Serves Gamma markets in fixed-size pages keyed by the offset param."""

    def __init__(self, all_markets, page):
        self._all = all_markets
        self._page = page

    def get(self, url, params=None, timeout=None):
        off = (params or {}).get("offset", 0)
        return _Resp(self._all[off : off + self._page])

    def post(self, url, json=None, timeout=None):
        return _Resp([])  # no CLOB books needed for this test


def _mk_market(i):
    return {
        "id": f"M{i}",
        "slug": f"m{i}",
        "question": f"Market {i}?",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.50", "0.50"]',
        "clobTokenIds": f'["Y{i}", "N{i}"]',
    }


def test_gamma_pagination_fetches_all_pages():
    # 250 markets served 100 at a time must all come back (not just page 1).
    markets = [_mk_market(i) for i in range(250)]
    src = PolymarketSource(
        limit=1000, session=_PagingSession(markets, page=100),
        use_clob=False, gamma_page=100,
    )
    quotes = src.fetch_quotes()
    assert len(quotes) == 250


def test_clob_failure_falls_back_to_gamma():
    class _Boom(_StubSession):
        def post(self, url, json=None, timeout=None):
            raise RuntimeError("clob down")

    src = PolymarketSource(limit=10, session=_Boom(_GAMMA, _BOOKS), use_clob=True)
    q = src.fetch_quotes()[0]
    # Falls back to Gamma mid-prices instead of dropping the source.
    assert q.yes_ask == 0.40
    assert q.no_ask == 0.60
