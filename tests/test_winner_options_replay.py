"""Same options rules as production, before risk, using actual archive receipts."""
from datetime import UTC, date, datetime
from dataclasses import replace

import pandas as pd
import pytest
from sqlalchemy import create_engine, event, text

from backtesting.winner_data import HistoricalOptionsSource
from service.options_directional.config import OptionsFilterConfig
from service.options_directional.features import select_top
from service.options_directional.history import read_options_evidence

DAY=date(2026,10,16)
CUTOFF=datetime(2026,10,19,13,29,59,tzinfo=UTC)


def database():
    engine=create_engine('sqlite://')
    rows=[];prices=[]
    for i,symbol in enumerate(['AAA','BBB','CCC','DDD','EEE']):
        prices.append(dict(symbol=symbol,date=DAY,close=100.,is_filled=0,data_source='eodhd_eod'))
        for side in ['CALL','PUT']:
            value=1000-200*i if side=='CALL' else 10+200*i
            rows.append(dict(id=len(rows)+1,underlying_symbol=symbol,
                contract_symbol=f'{symbol}261106{side[0]}00100000',expiration_date='2026-11-06',strike=100.,
                option_type=side,observed_at='2026-10-16 21:00:00',available_at='2026-10-16 21:01:00',
                provider_timestamp='2026-10-16 19:59:00',open_interest=value,payload_hash=side+symbol,
                provider='alpaca',feed='indicative',bar_timestamp='2026-10-16 19:30:00',volume=value,
                provenance_status='qualified',timeframe='30Min'))
    pd.DataFrame(rows).to_sql('stock_option_snapshots',engine,index=False)
    pd.DataFrame(rows).to_sql('stock_option_bars_delayed',engine,index=False)
    pd.DataFrame(prices).to_sql('stock_bars_daily',engine,index=False)
    oracle=pd.DataFrame([dict(symbol=s,proba_extreme=1-i*.01,rank=i+1) for i,s in enumerate(['AAA','BBB','CCC','DDD','EEE'])])
    return engine,oracle


def test_historical_selection_identical_to_pipeline_feature_selection():
    engine,oracle=database();statements=[]
    event.listen(engine,'before_cursor_execute',lambda conn,cursor,sql,*a:statements.append(sql))
    cfg=OptionsFilterConfig(enabled=True,oracle_top_n=4)
    with engine.connect() as conn:
        features,_=read_options_evidence(conn,['AAA','BBB','CCC','DDD'],DAY,CUTOFF)
        expected=select_top(oracle.to_dict('records'),features,cfg)
        result=HistoricalOptionsSource(conn,cfg)(DAY,oracle,CUTOFF)
    assert result['rows']==expected and result['selected']==['AAA','BBB']
    assert result['incomplete'] is False and result['covered']==4
    assert all(sql.lstrip().startswith('SELECT') for sql in statements)


def test_missing_or_future_oi_cannot_be_filled_with_rank_five():
    engine,oracle=database()
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_option_snapshots SET observed_at='2026-10-20 00:00:00' WHERE underlying_symbol='AAA'"))
    with engine.connect() as conn:
        result=HistoricalOptionsSource(conn,OptionsFilterConfig(enabled=True,oracle_top_n=4))(DAY,oracle,CUTOFF)
    assert result['incomplete'] is True and result['selected']==[]
    assert result['covered']==3 and 'EEE' not in [r['symbol'] for r in result['rows']]
    assert result['rows'][0]['reason']=='MISSING_OR_STALE_OPTIONS'


def test_no_options_snapshot_is_incomplete_not_a_volume_only_fallback():
    engine,oracle=database()
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM stock_option_snapshots'))
    with engine.connect() as conn:
        result=HistoricalOptionsSource(conn,OptionsFilterConfig(enabled=True,oracle_top_n=4))(DAY,oracle,CUTOFF)
    assert result['incomplete'] and not result['selected'] and not result['covered']


@pytest.mark.usefixtures('isolated_winner_config')
def test_filter_is_applied_before_any_risk_or_winner_buy_and_uses_preopen_cutoff():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,_=fixture(symbols=('AAA','BBB'),market_data_delay_seconds=900)
    calls=[]
    def selection(day,oracle,cutoff):
        calls.append((day,oracle.symbol.tolist(),cutoff))
        return dict(incomplete=False,selected=['BBB'])
    result=BacktestEngine(cfg).run(**args,winner_selection_source=selection)
    buys=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert buys.symbol.tolist()==['BBB']
    assert calls[0][1]==['AAA','BBB'] and calls[0][2].isoformat()=='2026-10-19T13:29:59+00:00'


@pytest.mark.usefixtures('isolated_winner_config')
def test_unqualified_filter_session_cannot_be_reported_complete():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,_=fixture()
    result=BacktestEngine(cfg).run(**args,winner_selection_source=lambda *a:dict(incomplete=True,selected=[]))
    meta=result.tracker_snapshot['winner_replay']
    assert meta['status']=='INCOMPLETE_COVERAGE'
    assert any(gap['reason']=='OPTIONS_COHORT_INCOMPLETE' for gap in meta['coverage_gaps'])
    assert not result.trade_events_df.event.eq('BUY_FILL').any()
