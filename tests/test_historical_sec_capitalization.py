"""SEC reconstruction uses individual facts and raw prices, never mapped aggregates."""
from datetime import UTC,date,datetime,timedelta
from pathlib import Path
import json

import pandas as pd
import pytest
from sqlalchemy import event

from backtesting.historical_sec_capitalization import share_facts,select_shares,HistoricalSecCapitalizations
from common.winner_pyramiding import regular_bounds
from tests.test_winner_factor_reconstruction import database,DAY,NOW,SYMBOLS

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def payload(cik='0000000001',*,end='2021-06-01',filed='2021-06-10',value=1000000):
    return dict(cik=int(cik),facts={'dei':{'EntityCommonStockSharesOutstanding':{'units':{'shares':[
        dict(end=end,filed=filed,val=value,accn='0000000001-21-000001',form='10-Q')]}}}})


def test_all_measurements_are_retained_then_latest_public_value_is_selected():
    p=payload()
    rows=p['facts']['dei']['EntityCommonStockSharesOutstanding']['units']['shares']
    rows.extend([dict(rows[0],end='2020-06-01',val=900),
        dict(rows[0],end='2021-06-20',filed='2021-06-30',val=1200000,accn='0000000001-21-000002'),
        dict(rows[0],end='2021-06-20',filed='2022-01-01',val=500,accn='0000000001-22-000001')])
    facts=share_facts(p,'0000000001')
    assert len(facts)==4
    chosen=select_shares(facts,DAY,NOW)
    assert chosen['value']==1200000 and chosen['end']==date(2021,6,20)


def test_filing_date_alone_never_becomes_an_invented_early_publication_time():
    facts=share_facts(payload(filed='2021-07-02'),'1')
    with pytest.raises(ValueError,match='NO_PUBLIC'):
        select_shares(facts,DAY,datetime(2021,7,2,23,tzinfo=UTC))
    assert select_shares(facts,DAY,NOW)['available_at']==datetime(2021,7,3,4,tzinfo=UTC)


def test_known_split_and_conflicting_share_values_are_rejected():
    facts=share_facts(payload(),'1')
    with pytest.raises(ValueError,match='KNOWN_SPLIT'):
        select_shares(facts,DAY,NOW,split_dates=[date(2021,6,15)])
    assert select_shares(facts,DAY,NOW,split_dates=[date(2021,7,15)])['value']>0
    with pytest.raises(ValueError,match='AMBIGUOUS'):
        select_shares(facts+[dict(facts[0],value=2e6)],DAY,NOW)
    with pytest.raises(ValueError,match='CIK_MISMATCH'):
        share_facts(payload(),'2')


def local_sources(engine,root):
    root.mkdir();(root/'companyfacts').mkdir()
    mapping={}
    for i,s in enumerate(SYMBOLS):
        cik=str(i+1).zfill(10);mapping[str(i)]=dict(ticker=s,cik_str=i+1)
        (root/'companyfacts'/('CIK'+cik+'.json')).write_text(json.dumps(payload(cik,value=(i+1)*1e6)),encoding='utf-8')
    (root/'company_tickers.json').write_text(json.dumps(mapping),encoding='utf-8')
    pd.DataFrame([dict(local_symbol=s,instrument_id=i+1,instrument_type='equity',currency='USD',
        mapping_status='mapped',market_code='US_EQ',display_name='Synthetic Company '+s)
        for i,s in enumerate(SYMBOLS)]).to_sql('instruments',engine,index=False)
    pd.DataFrame([dict(symbol=s,instrument_id=i+1,company_name='Synthetic Company '+s)
        for i,s in enumerate(SYMBOLS)]).to_sql('stock_metadata',engine,index=False)
    pd.DataFrame(columns=['symbol','ex_date','ca_type','provider']).to_sql('corporate_actions_events',engine,index=False)
    closing=regular_bounds(DAY)[1]
    pd.DataFrame([dict(symbol=s,trade_date=DAY,bar_timestamp=(closing-timedelta(minutes=5)).replace(tzinfo=None).isoformat(' '),
        bar_end_timestamp=closing.replace(tzinfo=None).isoformat(' '),interval_code='5m',data_source='alpaca_sip',
        provider='alpaca',market_code='US_EQ',session_tag='regular',data_adjustment='raw',is_filled=0,
        open=100.,high=101.,low=99.,close=100.,volume=1000.,payload_hash='raw-'+s) for s in SYMBOLS]
        ).to_sql('stock_bars_intraday',engine,index=False)


def test_raw_close_is_used_and_reconstruction_cannot_be_served_as_live_observation(tmp_path):
    from risk_management.factor_inputs import select_caps
    engine,_,_,_=database()
    root=tmp_path/'sec';local_sources(engine,root)
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda c,cursor,sql,*a:statements.append(sql))
    with engine.connect() as conn:
        source=HistoricalSecCapitalizations(conn,SYMBOLS,root=root)
        rows=source.reconstruct(DAY,NOW,SYMBOLS)
    assert len(rows)==25
    assert rows[0]['market_cap']==100e6
    assert rows[0]['computed_at']>NOW and rows[0]['input_available_at']<NOW
    assert select_caps(rows,DAY,NOW)=={}
    assert len(select_caps(rows,DAY,NOW,allow_reconstructed=True))==25
    assert all(s.lstrip().startswith('SELECT') for s in statements)
    assert not any('stock_fundamentals_daily' in s for s in statements)


def test_missing_raw_close_is_rejected_instead_of_using_adjusted_daily(tmp_path):
    from sqlalchemy import text
    engine,_,_,_=database();root=tmp_path/'sec';local_sources(engine,root)
    with engine.begin() as conn:conn.execute(text("DELETE FROM stock_bars_intraday WHERE symbol='S0'"))
    with engine.connect() as conn:
        source=HistoricalSecCapitalizations(conn,SYMBOLS,root=root)
        rows=source.reconstruct(DAY,NOW,SYMBOLS)
    assert len(rows)==24
    assert source.receipts[-1]['rejected_symbols']['S0']=='RAW_REGULAR_CLOSE_MISSING_OR_DUPLICATE'


def test_factor_reconstruction_uses_public_sec_facts_when_observed_caps_are_absent(tmp_path):
    from database.market_cap_snapshots import snapshots
    from backtesting.winner_data import HistoricalFactorSource
    from risk_management.config import RiskConfig
    engine,close,_,_=database();root=tmp_path/'sec';local_sources(engine,root)
    with engine.begin() as conn:conn.execute(snapshots.delete())
    with engine.connect() as conn:
        source=HistoricalFactorSource(conn,close,universe=SYMBOLS,start=close.index.min().date(),end=DAY)
        source.reconstruction.sec=HistoricalSecCapitalizations(conn,SYMBOLS,root=root)
        result=source(DAY,['S0'],NOW,RiskConfig())
    assert result['qualified'] and result['evidence_kind']=='RECONSTRUCTED_HISTORICAL_INPUTS'
    assert source.reconstruction.receipts[0]['sec_reconstructed_cap_symbols']==25
