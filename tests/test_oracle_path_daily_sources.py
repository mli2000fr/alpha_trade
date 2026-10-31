"""Regression: Oracle path label loading follows the feature provider preference."""
import pandas as pd
import pytest
from sqlalchemy import create_engine

from modelFactory.oracle_path.labels import load_bars
from tests.test_oracle_path import bars


@pytest.mark.parametrize('preferred,expected',[('eodhd','eodhd_eod'),('alpaca_sip','alpaca_sip')])
def test_label_loader_selects_whole_preferred_rows(monkeypatch,preferred,expected):
    eod=bars('A',n=3).assign(data_source='eodhd_eod')
    sip=eod.assign(data_source='alpaca_sip',open=102.,high=105.,low=101.,close=103.,adj_close=103.,volume=2222)
    engine=create_engine('sqlite://')
    pd.concat([eod,sip]).to_sql('stock_bars_daily',engine,index=False)
    monkeypatch.setattr('common.daily_bar_sources.load_config',lambda:{'market_data':{'daily_bars_preferred_source':preferred}})
    try:
        actual=load_bars(engine,['A'],'2020-01-01','2020-02-01')
        assert len(actual)==3 and not actual.duplicated(['symbol','date']).any()
        assert actual.data_source.eq(expected).all()
        assert actual.close.eq(100. if expected=='eodhd_eod' else 103.).all()
        assert actual.volume.eq(1000 if expected=='eodhd_eod' else 2222).all()
    finally:engine.dispose()


def test_label_loader_keeps_available_alternate_and_never_fills_missing_day(monkeypatch):
    eod=bars('A',n=4).assign(data_source='eodhd_eod')
    sip=eod.assign(data_source='alpaca_sip')
    engine=create_engine('sqlite://')
    pd.concat([eod.iloc[[0]],sip.iloc[[0,2]]]).to_sql('stock_bars_daily',engine,index=False)
    monkeypatch.setattr('common.daily_bar_sources.load_config',lambda:{})
    try:
        actual=load_bars(engine,['A'],'2020-01-01','2020-02-01')
        assert actual.date.tolist()==eod.date.iloc[[0,2]].tolist()
        assert actual.data_source.tolist()==['eodhd_eod','alpaca_sip']
    finally:engine.dispose()


def test_real_same_provider_duplicates_still_fail(monkeypatch):
    f=bars('A',n=2).assign(data_source='eodhd_eod')
    engine=create_engine('sqlite://')
    pd.concat([f,f.iloc[:1]]).to_sql('stock_bars_daily',engine,index=False)
    monkeypatch.setattr('common.daily_bar_sources.load_config',lambda:{})
    try:
        with pytest.raises(ValueError,match='ambiguous duplicates'):
            load_bars(engine,['A'],'2020-01-01','2020-02-01')
    finally:engine.dispose()
