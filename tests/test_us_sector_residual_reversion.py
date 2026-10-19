import numpy as np
import pandas as pd
import pytest
from scripts.research.us_sector_residual_reversion import assign_etf,etf_grid,supported_history,common_reason,compare_dates


@pytest.mark.parametrize('industry,etf',[
    ('Semiconductors','XLK'),('Energy','XLE'),('Pharmaceuticals','XLV'),
    ('Insurance','XLF'),('Metals & Mining','XLB'),('Industrial Conglomerates','XLI'),
    ('Transportation Infrastructure','XLI'),('Real Estate','XLRE'),('Utilities','XLU')])
def test_fixed_research_mapping(industry,etf):
    assert assign_etf(industry)==(etf,'CURRENT_PROXY_NOT_PIT')


@pytest.mark.parametrize('industry',['Retail','Consumer Products','Communications','Building','Construction','Distributors','Packaging'])
def test_ambiguous_industries_not_silently_assigned(industry):
    assert assign_etf(industry)==(None,'AMBIGUOUS_INDUSTRY')


@pytest.mark.parametrize('industry',[None,np.nan,'','Commodities Focused'])
def test_missing_or_unknown_no_spy_fallback(industry):
    assert assign_etf(industry)[0] is None


def data():
    days=pd.bdate_range('2024-01-01',periods=100)
    f=pd.DataFrame(dict(date=days,open=100.,high=101.,low=99.,close=100.,adj_close=100.,volume=100000.,
        is_filled=0,instrument_id='ETF_SYMBOL:XLK',data_source='alpaca_sip',data_adjustment='split'))
    return days,f


@pytest.mark.parametrize('source',['alpaca_iex','yahoo','unknown'])
def test_unqualified_source_rejected(source):
    days,f=data();f.loc[65,'data_source']=source
    g=etf_grid(f,days)
    assert not g.daily_good.iloc[65]
    assert not supported_history(g).iloc[65:].any()


def test_adjusted_shock_not_patched_and_shared_path_rejected():
    days,f=data();f.loc[75:,['open','high','low','close','adj_close']]*=2
    g=etf_grid(f,days)
    assert g.unqualified_etf_shock.iloc[75]
    assert g.close.iloc[75]==200
    _,plain=data();spy=etf_grid(plain,days)
    assert common_reason(spy,spy,g,70).startswith('SECTOR:')


def test_known_adjustment_factor_not_false_shock():
    days,f=data();f.loc[:74,['open','high','low','close']]*=2
    g=etf_grid(f,days)
    assert not g.unqualified_etf_shock.any()
    assert np.allclose(g.close,100)


def test_prefix_shared_support_not_changed_by_future():
    days,f=data();a=supported_history(etf_grid(f,days))
    f.loc[80,'data_source']='alpaca_iex'
    b=supported_history(etf_grid(f,days))
    pd.testing.assert_series_equal(a.iloc[:80],b.iloc[:80])


def test_common_date_comparison_does_not_fill_missing_arm_with_zero():
    days=pd.bdate_range('2024-01-01',periods=100)
    f=pd.DataFrame(dict(date=[days[0],days[0],days[1]],arm=['SPY','SECTOR_ETF','SPY'],net=[.01,.03,.99],
        scope='FULL_TRADABLE',year=2024,policy='OU_DYNAMIC',independent=True))
    r=compare_dates(f,days)
    assert r[0]['common_dates']==1
    assert r[0]['delta']==pytest.approx(.02)


def test_day_with_only_sector_does_not_count_as_matched():
    days=pd.bdate_range('2024-01-01',periods=100)
    f=pd.DataFrame(dict(date=[days[0],days[1]],arm=['SPY','SECTOR_ETF'],net=[.01,.03],
        scope='FULL_TRADABLE',year=2024,policy='OU_DYNAMIC',independent=True))
    assert compare_dates(f,days)==[]
