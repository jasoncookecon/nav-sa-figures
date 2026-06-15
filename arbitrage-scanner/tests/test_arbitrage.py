from arbscanner.arbitrage import find_opportunity
from arbscanner.fees import flat_bps, kalshi_fee
from arbscanner.models import Quote


def q(source, yes_ask, no_ask):
    return Quote(
        source=source,
        market_id=source + "1",
        title="Will it rain?",
        yes_ask=yes_ask,
        no_ask=no_ask,
    )


def test_clear_arbitrage():
    a = q("A", yes_ask=0.40, no_ask=0.62)
    b = q("B", yes_ask=0.55, no_ask=0.45)
    # YES on A (0.40) + NO on B (0.45) = 0.85 < 1.0 -> arbitrage
    opp = find_opportunity(a, b)
    assert opp is not None
    assert opp.is_arbitrage
    assert abs(opp.cost - 0.85) < 1e-9
    assert abs(opp.profit - 0.15) < 1e-9
    assert opp.legs[0].side == "YES"
    assert opp.legs[1].side == "NO"


def test_no_arbitrage():
    # Both hedge directions cost > $1, so there is no edge:
    #   YES@A 0.55 + NO@B 0.50 = 1.05 ;  NO@A 0.50 + YES@B 0.55 = 1.05
    a = q("A", 0.55, 0.50)
    b = q("B", 0.55, 0.50)
    opp = find_opportunity(a, b)
    assert opp is not None
    assert not opp.is_arbitrage


def test_untradable_returns_none():
    a = q("A", None, 0.45)
    b = q("B", 0.55, 0.45)
    assert find_opportunity(a, b) is None


def test_fees_can_erase_arbitrage():
    a = q("A", 0.49, 0.55)
    b = q("B", 0.55, 0.49)
    # raw: YES A 0.49 + NO B 0.49 = 0.98 -> 0.02 profit before fees
    raw = find_opportunity(a, b)
    assert raw.is_arbitrage
    heavy = flat_bps(300)  # 3% of notional on each leg
    withfee = find_opportunity(a, b, a_fee=heavy, b_fee=heavy)
    assert not withfee.is_arbitrage


def test_contracts_scale_profit_linearly():
    a = q("A", 0.40, 0.62)
    b = q("B", 0.55, 0.45)
    one = find_opportunity(a, b, contracts=1)
    ten = find_opportunity(a, b, contracts=10)
    assert abs(ten.profit - one.profit * 10) < 1e-9


def test_flip_polarity_picks_a_hedge():
    a = q("A", yes_ask=0.40, no_ask=0.62)
    b = q("B", yes_ask=0.45, no_ask=0.55)  # B-YES corresponds to A-NO
    opp = find_opportunity(a, b, flip_b=True)
    assert opp is not None


def test_kalshi_fee_formula():
    # 0.07 * 100 * 0.5 * 0.5 = 1.75
    assert abs(kalshi_fee(0.5, 100) - 1.75) < 1e-9
    # tiny raw fee still rounds up to a full cent
    assert abs(kalshi_fee(0.5, 1) - 0.02) < 1e-9
