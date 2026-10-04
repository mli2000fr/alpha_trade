from copy import deepcopy
import pytest

from service.fr.provider_exploratory_13b import repair_prices,repair_dividend
from service.fr.economic_decision_13c import attribution


def test_price_repair_only_missing_no_input_mutation():
    rows={'2024-07-29':{'open':10,'close':11}}
    saved=deepcopy(rows)
    overlay={'prices':[{'symbol':'A.PA','date':'2024-07-30','bar':{'open':12,'close':13}}]}
    result=repair_prices(rows,'A.PA',overlay)
    assert rows==saved and result['2024-07-30']['open']==12
    with pytest.raises(ValueError,match='existing'):
        repair_prices(result,'A.PA',overlay)
    assert repair_prices(rows,'B.PA',overlay)==rows


def test_dividend_repair_preserves_provider_amount_and_date():
    row={'date':'2025-04-29','unadjustedValue':.36,'currency':'EUR','paymentDate':None}
    item={'symbol':'A.PA','date':row['date'],'cash':'0.36','payment_date':'2025-05-02'}
    result,source=repair_dividend(row,'A.PA',{'dividends':[item]})
    assert result['paymentDate']=='2025-05-02' and row['paymentDate'] is None
    assert result['date']==row['date'] and result['unadjustedValue']==row['unadjustedValue']
    assert source is item
    assert repair_dividend(row,'B.PA',{'dividends':[item]})[1] is None


@pytest.mark.parametrize('change',[{'cash':'0.60'},{'payment_date':'2025-04-28'}])
def test_dividend_conflicting_repair_rejected(change):
    row={'date':'2025-04-29','unadjustedValue':.36,'currency':'EUR'}
    item={'symbol':'A.PA','date':row['date'],'cash':'0.36','payment_date':'2025-05-02',**change}
    with pytest.raises(ValueError):
        repair_dividend(row,'A.PA',{'dividends':[item]})


def test_dividend_ambiguous_review_rejected():
    row={'date':'2025-04-29','unadjustedValue':.36,'currency':'EUR'}
    item={'symbol':'A.PA','date':row['date'],'cash':'0.36','payment_date':'2025-05-02'}
    with pytest.raises(ValueError,match='Ambiguous'):
        repair_dividend(row,'A.PA',{'dividends':[item,item]})


def test_concentration_subtraction_is_not_a_policy_backtest():
    result={'net_pnl':'70','gross_pnl':'80','ledger':{'trades':[
        {'uid':'A','net_pnl':'100'},{'uid':'B','net_pnl':'-30'}],'orders':[]}}
    audit=attribution(result,{'A':{'ticker':'A.PA'},'B':{'ticker':'B.PA'}})
    assert audit['net_minus_best_trade_eur_attribution_only']=='-30'
    assert audit['net_minus_best_symbol_eur_attribution_only']=='-30'
    assert audit['subtraction_is_not_a_replayed_policy'] is True
    assert audit['top_positive_symbol_share_of_positive_contributions']==1
