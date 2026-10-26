"""Synthetic11.90/TP15 case; observed issuer remains diagnosis-owned."""
from types import SimpleNamespace
import pytest

from scripts.research import us_winner_2020_cent_repair_20261023 as correction
from scripts.research import us_winner_cent_qualification_20261024 as qualification


@pytest.mark.parametrize('quantity',[13,26,47,52])
def test_exact_first_fill_keeps_tp1368_without_loosening_audit(quantity):
    raw=dict(filled_qty=str(quantity),filled_avg_price='11.9')
    recovered=correction.initial_fill_price(raw,dict(booked_quantity=0),SimpleNamespace(qty=quantity,limit_price=11.91))
    recomputed=quantity*float(raw['filled_avg_price'])/quantity
    assert recovered==11.9 and recomputed!=recovered
    assert round(recovered*1.15,2)==13.68
    assert round(recomputed*1.15,2)==13.69
    assert qualification.explained(dict(same_time_reason=True,scalar_price=13.68,actual_price=13.69,
        actual_reason='TP_GAP_CAPPED',fills=[dict(tp=13.69,canonical_tp=13.68,stop=None,
            canonical_stop=None,native_price=recomputed,raw_average='11.9')]))
