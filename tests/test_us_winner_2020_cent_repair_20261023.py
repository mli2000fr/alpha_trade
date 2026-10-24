from types import SimpleNamespace
import pytest
from scripts.research import us_winner_2020_cent_repair_20261023 as fix


@pytest.mark.parametrize('quantity',[12,48])
def test_exact_first_full_price_not_multiplied_and_divided(quantity):
    raw=dict(filled_qty=str(quantity),filled_avg_price='11.3');parent=dict(booked_quantity=0)
    p=fix.initial_fill_price(raw,parent,SimpleNamespace(qty=quantity,limit_price=11.31))
    assert p==11.3 and round(p*.95,2)==10.73
    assert round((quantity*11.3/quantity)*.95,2)==10.74


@pytest.mark.parametrize('qty,booked',[(11,0),(12,1)])
def test_unqualified_partial_fills_fail_closed(qty,booked):
    with pytest.raises(ValueError,match='first complete'):
        fix.initial_fill_price(dict(filled_qty=str(qty),filled_avg_price='11.3'),dict(booked_quantity=booked),
            SimpleNamespace(qty=12,limit_price=11.31))


@pytest.mark.parametrize('price',['nan','inf','0','-1','12'])
def test_bad_fill_prices_rejected(price):
    with pytest.raises(ValueError):fix.initial_fill_price(dict(filled_qty='12',filled_avg_price=price),
        dict(booked_quantity=0),SimpleNamespace(qty=12,limit_price=11.31))


def test_context_restores_runtime_even_after_error():
    old=fix.runtime.WinnerCampaignRuntime.book_buy
    with pytest.raises(RuntimeError):
        with fix.corrected_runtime():
            assert fix.runtime.WinnerCampaignRuntime.book_buy is fix.stable_book_buy
            raise RuntimeError('test')
    assert fix.runtime.WinnerCampaignRuntime.book_buy is old


def test_real_book_buy_passes_exact_price_to_native_add_fill(monkeypatch):
    captured=[]
    def add(state,**kwargs):
        captured.append(kwargs);state['lots'].append(dict(stop=round(kwargs['price']*.95,2)))
    monkeypatch.setattr(fix.runtime,'add_fill',add)
    intent=SimpleNamespace(intent_id='test',qty=12,limit_price=11.31)
    obj=SimpleNamespace(state=dict(parents={'test':dict(booked_quantity=0,booked_notional=0.)},lots=[]),
        broker=SimpleNamespace(actual_fill_time=lambda *_:'2020-01-01T14:45:00+00:00'),
        metrics=dict(winner_fills_reconciled=0),save=lambda:None)
    fix.stable_book_buy(obj,intent,dict(action='ENTRY'),dict(filled_qty='12',filled_avg_price='11.3'))
    assert captured[0]['price']==11.3
    assert obj.state['lots'][0]['stop']==10.73
    assert obj.metrics['winner_fills_reconciled']==1
    assert fix.runtime.add_fill is add
