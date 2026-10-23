import pandas as pd
import pytest
from scripts.research.us_winner_bottom_rank_filter_audit_20261022 import event_cash


def test_scalar_cash_keeps_costs_and_open_quantity():
    e=pd.DataFrame([dict(event='BUY_FILL',symbol='A',quantity=3,price=100,costs=1),
        dict(event='SELL_FILL',symbol='A',quantity=2,price=110,costs=2),
        dict(event='FINANCING',symbol=None,quantity=None,price=None,costs=3)])
    cash,fees,positions=event_cash(e)
    assert cash==pytest.approx(3914)
    assert fees==3 and positions=={'A':1}


def test_scalar_audit_rejects_overselling_and_duplicate_position():
    e=pd.DataFrame([dict(event='SELL_FILL',symbol='A',quantity=2,price=100,costs=1)])
    with pytest.raises(AssertionError,match='Oversell'):event_cash(e)
    e=pd.DataFrame([dict(event='BUY_FILL',symbol='A',quantity=2,price=100,costs=1)]*2)
    with pytest.raises(AssertionError,match='Repeated buy'):event_cash(e)
