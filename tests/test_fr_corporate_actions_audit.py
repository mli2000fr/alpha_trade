from decimal import Decimal

from service.fr.corporate_actions_audit import price_jump_status, split_ratio


def test_fr_split_ratio_and_economic_jump():
    assert split_ratio("10.000000/1.000000") == Decimal(10)
    assert split_ratio("1/100") == Decimal("0.01")
    assert split_ratio("0/1") is None
    assert split_ratio("invalid") is None
    status, deviation = price_jump_status(Decimal(10), Decimal(310), Decimal(31))
    assert status == "PLAUSIBLE"
    assert deviation == 0
    assert price_jump_status(Decimal(10), Decimal(310), Decimal(100))[0] == "PRICE_RATIO_MISMATCH"
