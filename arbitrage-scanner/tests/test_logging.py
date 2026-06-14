import csv

from arbscanner.arbitrage import find_opportunity
from arbscanner.models import Quote
from arbscanner.opportunity_logger import FIELDNAMES, append_opportunities


def _opp():
    a = Quote(source="A", market_id="A1", title="Will it rain?", yes_ask=0.40, no_ask=0.62)
    b = Quote(source="B", market_id="B1", title="Will it rain?", yes_ask=0.55, no_ask=0.45)
    return find_opportunity(a, b, match_score=0.91)


def test_writes_header_once_and_appends(tmp_path):
    path = tmp_path / "log.csv"
    assert append_opportunities(str(path), [_opp()], scan_time="2026-06-14T00:00:00+00:00") == 1
    assert append_opportunities(str(path), [_opp()], scan_time="2026-06-14T00:01:00+00:00") == 1

    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2  # header written only once
    assert list(rows[0].keys()) == FIELDNAMES
    assert rows[0]["scan_time"] == "2026-06-14T00:00:00+00:00"
    assert rows[1]["scan_time"] == "2026-06-14T00:01:00+00:00"
    assert rows[0]["a_side"] == "YES"
    assert rows[0]["b_side"] == "NO"
    assert abs(float(rows[0]["total_profit"]) - 0.15) < 1e-6
    assert rows[0]["match_score"] == "0.9100"


def test_empty_writes_nothing(tmp_path):
    path = tmp_path / "log.csv"
    assert append_opportunities(str(path), []) == 0
    assert not path.exists()


def test_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "log.csv"
    assert append_opportunities(str(path), [_opp()], scan_time="t") == 1
    assert path.exists()
