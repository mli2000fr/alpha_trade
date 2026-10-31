"""Automatic factor reconstruction is local, causal by source and replay-only."""
from datetime import UTC, date, datetime, timedelta
from dataclasses import replace
import gzip
import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, event

from backtesting.winner_data import HistoricalFactorSource
from database.risk_factor_inputs import snapshots
from database.market_cap_snapshots import snapshots as cap_table
from risk_management.config import RiskConfig
from risk_management.factor_inputs import expected_sessions

DAY=date(2021,7,2)
NOW=datetime(2021,7,6,14,0,30,tzinfo=UTC)
SYMBOLS=[f'S{i}' for i in range(25)]
pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def database(day=DAY):
    engine=create_engine('sqlite://')
    snapshots.create(engine);cap_table.create(engine)
    sessions=expected_sessions(day)
    k=np.arange(len(sessions),dtype=float)
    prices={'SPY':100*np.exp(.0002*k+.01*np.sin(k/6)),
        'IWM':100*np.exp(.0001*k+.02*np.sin(k/9)),
        'MTUM':100*np.exp(.0003*k+.015*np.cos(k/7))}
    prices.update({s:100*np.exp((i-12)*.0001*k+.04*np.sin(k/(3+i%5)+i)+.007*np.cos(k/2))
        for i,s in enumerate(SYMBOLS)})
    close=pd.DataFrame(prices,index=pd.to_datetime(sessions))
    bars=pd.DataFrame([dict(symbol=s,date=d,open=p,close=p,high=p*1.01,low=p*.99,
        volume=1e6,is_filled=0,data_source='alpaca_sip',data_adjustment='split')
        for s in close for d,p in close[s].items()])
    bars.assign(date=bars.date.dt.date).to_sql('stock_bars_daily',engine,index=False)
    caps=[dict(symbol=s,observation_date=day-timedelta(days=1),available_date=day,
        computed_at=datetime.combine(day-timedelta(days=1),datetime.min.time())+timedelta(hours=22),
        source='SEC_X_CLOSE',market_cap=1e9*(i+1),currency='USD',
        source_record_id=i+1,source_trade_date=day-timedelta(days=2),source_available_date=day,
        run_id='caps-known',input_hash=str(i),details_json='{}') for i,s in enumerate(SYMBOLS)]
    with engine.begin() as conn:
        conn.execute(cap_table.insert(),caps)
    return engine,close,bars,caps


def source(conn,close,tmp_path):
    return HistoricalFactorSource(conn,close,universe=SYMBOLS,start=close.index.min().date(),end=DAY,output=tmp_path)


def test_missing_snapshot_is_computed_once_and_never_backdated_or_written_to_sql(tmp_path):
    engine,close,_,_=database()
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda conn,cursor,sql,*a:statements.append(sql))
    with engine.connect() as conn:
        provider=source(conn,close,tmp_path)
        ctx=provider(DAY,['S0'],NOW,RiskConfig())
        again=provider(DAY,['S1'],NOW+timedelta(minutes=5),RiskConfig())
        assert ctx['qualified'] and again['qualified']
        assert ctx['evidence_kind']=='RECONSTRUCTED_HISTORICAL_INPUTS'
        assert ctx['observed_at'].year>=2026 and ctx['input_available_at']<NOW
        assert len(provider.reconstruction.receipts)==1
        assert len(provider.receipts)==2
        assert provider(DAY,['S0'],NOW+timedelta(minutes=10),RiskConfig())['captured_at']==NOW+timedelta(minutes=10)
    assert all(s.lstrip().startswith('SELECT') for s in statements)
    path=tmp_path/'factor-reconstructions/2021-07-02.json.gz'
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        archived=json.load(stream)
    assert archived['receipt']['qualified_symbols']==25
    assert len(archived['inputs'])==25
    assert all(r['evidence_kind']=='RECONSTRUCTED_HISTORICAL_INPUTS' for r in archived['inputs'])


def test_qualified_archive_is_used_before_reconstruction(tmp_path):
    engine,close,_,_=database()
    # Use genuine matching historical values, first reconstructed only as test setup.
    with engine.connect() as conn:
        p=source(conn,close,tmp_path)
        frame=p.reconstruction.inputs(DAY,NOW).copy()
    records=[dict(run_id='actual-2021',symbol=r.symbol,asof_date=DAY,
        observed_at=datetime(2021,7,2,22),universe_sha256='frozen',input_sha256=r.input_sha256,
        beta_126=r.beta_126,trend_score=r.trend_score,market_cap=r.market_cap,
        quality=r.quality,details_json=r.details_json) for r in frame.itertuples()]
    with engine.begin() as conn:
        conn.execute(snapshots.insert(),records)
    with engine.connect() as conn:
        p=source(conn,close,tmp_path)
        ctx=p(DAY,['S0'],NOW,RiskConfig())
    assert ctx['evidence_kind']=='ARCHIVED_OBSERVATIONS'
    assert not p.reconstruction.receipts


@pytest.mark.parametrize('future',[False,True])
def test_unusable_or_future_archive_does_not_prevent_valid_reconstruction(future,tmp_path):
    engine,close,_,_=database()
    with engine.begin() as conn:
        conn.execute(snapshots.insert(),dict(run_id='unusable',symbol='S0',asof_date=DAY,
            observed_at=datetime(2026,10,31) if future else datetime(2021,7,2,22),
            universe_sha256='old',input_sha256='unusable',quality='INCOMPLETE',details_json='{}'))
    with engine.connect() as conn:
        p=source(conn,close,tmp_path)
        result=p(DAY,['S0'],NOW,RiskConfig())
    assert result['qualified'] and result['evidence_kind']=='RECONSTRUCTED_HISTORICAL_INPUTS'
    assert len(p.reconstruction.receipts)==1


def test_no_historical_caps_reports_why_reconstruction_is_impossible(tmp_path):
    engine,close,_,_=database()
    with engine.begin() as conn:
        conn.execute(cap_table.delete())
    with engine.connect() as conn:
        p=source(conn,close,tmp_path)
        with pytest.raises(ValueError,match='Capitalisations historiques datées insuffisantes : 0/20'):
            p(DAY,['S0'],NOW,RiskConfig())
        with pytest.raises(ValueError):
            p(DAY,['S1'],NOW+timedelta(minutes=5),RiskConfig())
    assert len(p.reconstruction.receipts)==1
    assert p.reconstruction.receipts[0]['dated_cap_symbols']==0
    assert p.reconstruction.bars is None  # No expensive price load can repair missing cap history.


@pytest.mark.parametrize('hour,accepted',[(12,True),(14,False)])
def test_overnight_sources_are_accepted_but_later_intraday_updates_are_frozen_out(hour,accepted,tmp_path):
    engine,close,_,_=database()
    with engine.begin() as conn:
        conn.execute(cap_table.update().where(cap_table.c.symbol=='S0').values(
            computed_at=datetime(2021,7,6,hour),available_date=date(2021,7,6)))
    with engine.connect() as conn:
        p=source(conn,close,tmp_path)
        if accepted:
            assert p(DAY,['S0'],NOW,RiskConfig())['qualified']
        else:
            with pytest.raises(ValueError,match='missing='):
                p(DAY,['S0'],NOW,RiskConfig())


@pytest.mark.parametrize('fault',['future_cap','missing_cap','wrong_currency','missing_bar','missing_proxy'])
def test_missing_or_future_sources_are_not_neutralized(fault,tmp_path):
    engine,close,bars,_=database()
    with engine.begin() as conn:
        if fault=='future_cap':
            conn.execute(cap_table.update().where(cap_table.c.symbol=='S0').values(computed_at=datetime(2026,10,31)))
        elif fault=='missing_cap':
            conn.execute(cap_table.delete().where(cap_table.c.symbol=='S0'))
        elif fault=='wrong_currency':
            conn.execute(cap_table.update().where(cap_table.c.symbol=='S0').values(currency='EUR'))
        elif fault=='missing_bar':
            bars=bars.loc[~(bars.symbol.eq('S0')&bars.date.eq(bars.date.min()))]
            bars.assign(date=bars.date.dt.date).to_sql('stock_bars_daily',conn,index=False,if_exists='replace')
        else:
            close=close.drop(columns='IWM')
    with engine.connect() as conn:
        p=source(conn,close,tmp_path)
        with pytest.raises(ValueError,match='Facteurs historiques non qualifiés'):
            p(DAY,['S0'],NOW,RiskConfig())
    assert not p.receipts[0]['qualified']


def test_future_prices_do_not_change_reconstructed_features_or_hash(tmp_path):
    engine,close,bars,_=database()
    with engine.connect() as conn:
        baseline=source(conn,close,tmp_path).reconstruction.inputs(DAY,NOW)
    future=bars.loc[bars.date.eq(bars.date.max())].copy()
    future['date']=pd.Timestamp('2021-07-06')
    future.loc[:,['open','close','high','low']]*=1000
    future.assign(date=future.date.dt.date).to_sql('stock_bars_daily',engine,index=False,if_exists='append')
    later=tmp_path/'again';later.mkdir()
    with engine.connect() as conn:
        p=HistoricalFactorSource(conn,close,universe=SYMBOLS,start=close.index.min().date(),
            end=date(2021,7,6),output=later)
        changed=p.reconstruction.inputs(DAY,NOW)
    assert baseline.input_sha256.tolist()==changed.input_sha256.tolist()


def test_backtest_engine_automatically_reconstructs_then_runs_native_risk(tmp_path):
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    day=date(2026,10,16)
    engine,close,_,_=database(day)
    cfg,args,_=fixture(last=date(2026,10,19),symbols=('S0',),market_data_delay_seconds=930)
    cfg.risk_config=replace(cfg.risk_config,enable_factor_model=True,
        max_factor_concentration_pct=1.,factor_diversification_check_enabled=False)
    daily=pd.concat([close,close.iloc[[-1]].set_axis([pd.Timestamp(cfg.start_date)])])
    args.update(open_df=daily,close=daily,high=daily*1.01,low=daily*.99,volume=daily*100000.)
    with engine.connect() as conn:
        provider=HistoricalFactorSource(conn,daily,universe=SYMBOLS,start=close.index.min().date(),
            end=cfg.end_date,output=tmp_path)
        result=BacktestEngine(cfg).run(**args,winner_factor_source=provider)
    events=result.trade_events_df
    assert events.event.eq('BUY_FILL').sum()==1,events.get('reason').dropna().value_counts().to_dict()
    assert provider.receipts[0]['mode']=='RECONSTRUCTED_HISTORICAL_INPUTS'
    assert result.tracker_snapshot['winner_replay']['status']=='COMPLETED_EXPLORATORY'
    assert len(provider.reconstruction.receipts)==1


def test_reconstruction_cannot_authorize_live_risk_without_explicit_replay_adapter(tmp_path):
    from tests.test_winner_risk import data,context
    from tests.test_winner_runtime import NOW as LIVE_NOW
    from risk_management.models import FactorExposures
    from risk_management.factor_model import FactorCovariance
    from execution_engine.winner_risk import reapprove_campaign
    state,snap=data()
    cfg=replace(context()['risk_config'],enable_factor_model=True)
    factor=dict(qualified=True,asof_date=LIVE_NOW.date(),captured_at=LIVE_NOW,
        observed_at=LIVE_NOW+timedelta(days=1),input_available_at=LIVE_NOW-timedelta(days=1),
        evidence_kind='RECONSTRUCTED_HISTORICAL_INPUTS',snapshot_hash='reconstructed',
        exposures={'TEST':FactorExposures('TEST',LIVE_NOW.date(),.4,1.,1.)},
        covariance=FactorCovariance(np.eye(3),['market','size','momentum'],{'TEST':.05},LIVE_NOW.date()))
    ctx=context(cfg)|dict(factor_qualified=True,factor_asof_date=LIVE_NOW.date(),factor_context=factor)
    with pytest.raises(ValueError,match='restricted'):
        reapprove_campaign(state,0,10,snap,LIVE_NOW,'ENTRY',context=ctx)
    accepted=reapprove_campaign(state,0,10,snap,LIVE_NOW,'ENTRY',context=ctx,replay_reconstructed_factors=True)
    assert accepted['max_quantity']>0
    stricter=ctx|dict(risk_config=replace(cfg,max_portfolio_beta=.001))
    rejected=reapprove_campaign(state,0,10,snap,LIVE_NOW,'ENTRY',context=stricter,replay_reconstructed_factors=True)
    assert rejected['max_quantity']==0
