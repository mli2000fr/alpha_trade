"""SL7/TP15 cent-rounding regression; synthetic price, not an observed issuer claim."""
from types import SimpleNamespace

import pytest

from scripts.research import us_winner_2020_cent_repair_20261023 as correction
from scripts.research import us_winner_cent_qualification_20261024 as qualification


@pytest.mark.parametrize('quantity', [3, 6, 12, 24, 41, 48])
def test_tp15_preserves_exact_first_fill_instead_of_notional_round_trip(quantity):
    raw = dict(filled_qty=str(quantity),filled_avg_price='52.7')
    parent = dict(booked_quantity=0)
    intent = SimpleNamespace(qty=quantity,limit_price=52.71)
    original = quantity*float(raw['filled_avg_price'])/quantity
    canonical = correction.initial_fill_price(raw,parent,intent)
    assert canonical == 52.7
    assert original != canonical
    assert round(canonical*1.15,2) == 60.60
    assert round(original*1.15,2) == 60.61
    mismatch = dict(same_time_reason=True,scalar_price=60.60,actual_price=60.61,actual_reason='TP',
        fills=[dict(tp=60.61,canonical_tp=60.60,stop=49.01,canonical_stop=49.01,
                    native_price=original,raw_average=raw['filled_avg_price'])])
    assert qualification.explained(mismatch)


def test_numeric_cent_pattern_alone_does_not_authorize_a_waiver():
    assert qualification.cent_error('60.6 != 60.61')
    assert not qualification.explained(dict(same_time_reason=True,scalar_price=60.60,
        actual_price=60.61,actual_reason='TP',fills=[]))
