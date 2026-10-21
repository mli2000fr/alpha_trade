import pytest
from scripts.research import us_earnings_release_recalage as s


def proof(metric,values,table=0,exhibit='EX-99.1'):
    return dict(release_accession='A',exhibit_type=exhibit,table_index=table,metric=metric,reported_values=values)


def test_require_same_table_all_four_source_values():
    p=[proof('revenue',[120,100]),proof('operating',[18,10])]
    assert s.source_values(p)==(120,100,18,10)
    assert s.source_values([p[0],proof('operating',[18,10],table=1)]) is None
    assert s.source_values([p[0],proof('operating',[18,10],exhibit='EX-99.2')]) is None


def test_conflicting_rounded_table_values_never_pick_profitable_sign():
    p=[proof('revenue',[120,100]),proof('operating',[18,10]),proof('revenue',[120,100],table=1),proof('operating',[17,10],table=1)]
    assert s.source_values(p) is None


def test_pattern_uses_original_release_values_not_later_filing():
    assert s.accounting((120,100,18,10))[0]=='LONG'
    assert s.accounting((90,100,5,10))[0]=='SHORT'
    assert s.accounting(None)==('ABSTAIN',None,None)


def bars():
    return [dict(open=p,high=p,low=p,close=p,adj_close=p,volume=10,is_filled=0,instrument_id=i,data_source='Alpaca SIP',data_adjustment='ALL')
        for p,i in [(100,1),(105,1),(100,2),(106,2)]]


def test_reaction_relative_to_market_not_absolute_stock_direction():
    value,side,reason=s.price_reaction(bars())
    assert value==pytest.approx(-.01) and side=='SHORT' and reason is None


@pytest.mark.parametrize('field,value',[('is_filled',1),('volume',0),('instrument_id',3),('data_source','UNKNOWN')])
def test_missing_or_unqualified_bar_abstains(field,value):
    b=bars();b[1][field]=value
    assert s.price_reaction(b)[1]=='UNKNOWN'
