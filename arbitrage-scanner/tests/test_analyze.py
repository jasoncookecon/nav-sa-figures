from arbscanner.analyze import build_report, summarize


def _row(scan_time, a_id="A1", b_id="B1", roi="0.03", size="500", title="Fed cuts in July"):
    return {
        "scan_time": scan_time,
        "roi": roi,
        "available_size": size,
        "a_source": "kalshi", "a_market_id": a_id, "a_title": title,
        "b_source": "poly", "b_market_id": b_id,
    }


def test_summarize_groups_by_pair_and_tracks_span():
    rows = [
        _row("2026-06-14T00:00:00+00:00", roi="0.02", size="500"),
        _row("2026-06-14T00:05:00+00:00", roi="0.04", size="800"),  # same pair, later
        _row("2026-06-14T00:00:00+00:00", a_id="A2", b_id="B2", roi="0.01"),  # other pair
    ]
    edges = {e.key: e for e in summarize(rows)}
    assert len(edges) == 2

    persistent = edges[("kalshi", "A1", "poly", "B1")]
    assert persistent.count == 2
    assert persistent.span_seconds == 300  # five minutes
    assert abs(persistent.max_roi - 0.04) < 1e-9
    assert persistent.max_size == 800

    fleeting = edges[("kalshi", "A2", "poly", "B2")]
    assert fleeting.count == 1
    assert fleeting.span_seconds == 0


def test_report_counts_persistent_edges():
    rows = [
        _row("2026-06-14T00:00:00+00:00"),
        _row("2026-06-14T00:05:00+00:00"),
        _row("2026-06-14T00:00:00+00:00", a_id="A2", b_id="B2"),
    ]
    report = build_report(rows, top=10)
    assert "Distinct edges (market pairs): 2" in report
    assert "Edges seen in >1 scan: 1" in report


def test_missing_size_is_tolerated():
    rows = [_row("2026-06-14T00:00:00+00:00", size="")]
    edges = summarize(rows)
    assert edges[0].max_size is None
    # report should still render without raising
    assert "Distinct edges" in build_report(rows)


def test_empty_log():
    assert "nothing to analyze" in build_report([])
