"""Provider recovery and scoped exclusions, no provider/broker/production SQL."""
from datetime import UTC, date, datetime, timedelta
from dataclasses import replace
import json
import logging

import pandas as pd
import pytest
import requests

from backtesting.winner_intraday_recovery import RecoveringIntradaySource, qualified_frame, rows_from_payload
from common.winner_pyramiding import WinnerPyramidingConfig, regular_bounds

pytestmark=pytest.mark.usefixtures('isolated_winner_config')
DAY=date(2026,10,19)
NOW=datetime(2026,11,1,tzinfo=UTC)


def bars(day=DAY):
    opening,closing=regular_bounds(day)
    return pd.DataFrame(dict(symbol='AAA', timestamp=pd.date_range(opening,closing,freq='5min',inclusive='left'),
                             open=100.,high=101.,low=99.,close=100.,volume=1000.))


def payload(frame):
    return [dict(timestamp=int(r.timestamp.timestamp()),**{k:getattr(r,k) for k in ('open','high','low','close','volume')})
            for r in frame.itertuples()]


def yahoo_payload(frame):
    return dict(chart=dict(error=None,result=[dict(meta=dict(symbol='AAA',currency='USD',dataGranularity='5m'),
        timestamp=[int(t.timestamp()) for t in frame.timestamp],indicators=dict(quote=[{
            k:frame[k].tolist() for k in ('open','high','low','close','volume')}]))]))


def source(tmp_path,fetcher,frame=None,day=DAY,**kwargs):
    frame=bars(day).drop(index=10) if frame is None else frame
    def base(d,ss):return frame.copy() if d==day and 'AAA' in ss else pd.DataFrame()
    base.receipts=[]
    return RecoveringIntradaySource(base,date(2026,11,20),WinnerPyramidingConfig(horizon_sessions=1),
        cache_dir=tmp_path,fetcher=fetcher,now=lambda:NOW,**kwargs)


def audit(day=DAY):
    return dict(gaps=[dict(symbol='AAA',date=str(day),expected_bars=78,qualified_bars=77,missing_bars=1)],
                symbols_checked=1)


def test_repair_order_and_cache_retains_provider_identity_and_original_sip(tmp_path):
    calls=[]
    def fetch(p,s,d):
        calls.append(p)
        if p=='alpaca_sip':return []
        return yahoo_payload(bars())
    recovery=source(tmp_path,fetch)
    report=recovery.prepare(audit())
    assert calls==['alpaca_sip','yahoo'] and report['repaired_sessions']==1
    result=recovery(DAY,['AAA'])
    assert len(result)==78 and result.data_source.value_counts().to_dict()=={'alpaca_sip':77,'yahoo':1}
    assert report['excluded_symbols']==[] and recovery.entry_allowed('AAA',DAY)
    assert report['recovery']['sql_modified'] is False
    other=source(tmp_path,lambda *a:pytest.fail('cache must avoid another API call'))
    other.prepare(audit())
    assert all(r['cache_hit'] for r in other.attempts)
    cache=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert cache['envelope']['observed_at']==NOW.isoformat()
    assert len(cache['sha256'])==64


def test_yahoo_error_continues_to_eodhd_and_no_fallback_can_overwrite_sip(tmp_path):
    calls=[]
    def fetch(p,s,d):
        calls.append(p)
        if p=='alpaca_sip':raise requests.Timeout('no token in archive')
        if p=='yahoo':raise ValueError('unavailable history')
        return payload(bars())
    recovery=source(tmp_path,fetch)
    assert recovery.prepare(audit())['missing_sessions']==0
    assert calls==['alpaca_sip','yahoo','eodhd']
    result=recovery(DAY,['AAA'])
    assert result.data_source.value_counts().to_dict()=={'alpaca_sip':77,'eodhd':1}


def test_all_errors_block_only_affected_entry_dates_then_allow_same_symbol(tmp_path,caplog):
    def failed(*a):raise requests.Timeout('https://example?api_token=secret')
    recovery=source(tmp_path,failed)
    report=recovery.prepare(audit())
    assert report['missing_sessions']==1 and report['excluded_symbols']==[]
    with caplog.at_level(logging.WARNING):
        assert not recovery.entry_allowed('AAA',DAY)
        assert not recovery.entry_allowed('AAA',DAY+timedelta(days=1))  # prior reference is incomplete
        assert recovery.entry_allowed('AAA',DAY+timedelta(days=2))
        assert recovery.entry_allowed('BBB',DAY)
        recovery.export(tmp_path)
    table=pd.read_csv(tmp_path/'entry-exclusions.csv')
    assert table.symbol.tolist()==['AAA','AAA']
    assert table.entry_date.tolist()==['2026-10-19','2026-10-20']
    assert 'Tableau' in caplog.text and '2026-10-19' in caplog.text
    assert 'secret' not in (tmp_path/'intraday-recovery.json').read_text()


def test_incompatible_adjustments_or_no_sip_anchors_are_not_accepted(tmp_path):
    wrong=bars();wrong.loc[:,['open','high','low','close']]*=.5
    recovery=source(tmp_path,lambda p,*a:[] if p=='alpaca_sip' else
        yahoo_payload(wrong) if p=='yahoo' else payload(wrong))
    assert recovery.prepare(audit())['missing_sessions']==1
    assert [r['status'] for r in recovery.attempts]==['RECEIVED','INCOMPATIBLE_PRICE_BASIS','INCOMPATIBLE_PRICE_BASIS']
    empty=source(tmp_path/'empty',lambda p,*a:[] if p=='alpaca_sip' else
        yahoo_payload(bars()) if p=='yahoo' else payload(bars()),frame=bars().iloc[:0])
    assert empty.prepare(audit())['missing_sessions']==1


def test_permission_failure_is_not_hammered_and_other_dates_keep_processing(tmp_path):
    count=[]
    def fetch(p,s,d):
        count.append(p)
        if p=='alpaca_sip':
            resp=requests.Response();resp.status_code=403
            raise requests.HTTPError(response=resp)
        return [] if p=='eodhd' else dict(chart=dict(error=dict(description='5m data must be within the last 60 days.'),result=None))
    recovery=source(tmp_path,fetch)
    recovery.prepare(audit())
    recovery.fetch('alpaca_sip','BBB',DAY)
    recovery.fetch('yahoo','BBB',date(2025,1,31))
    assert count.count('alpaca_sip')==1 and count.count('yahoo')==1
    assert recovery.attempts[-1]['status']=='OUTSIDE_PROVIDER_HISTORY'


def test_bad_grid_duplicate_and_wrong_yahoo_metadata_do_not_fill_a_gap(tmp_path):
    frame=bars()
    frame.loc[0,'timestamp']+=pd.Timedelta(seconds=1)
    frame.loc[1,'volume']=0
    frame.loc[2,'high']=float('inf')
    assert len(qualified_frame(frame,'AAA',DAY))==75
    with pytest.raises(ValueError,match='duplicate'):
        qualified_frame(pd.concat([bars(),bars().iloc[:1]]),'AAA',DAY)
    bad=yahoo_payload(bars());bad['chart']['result'][0]['meta']['currency']='EUR'
    with pytest.raises(ValueError,match='currency'):
        rows_from_payload('yahoo',bad,'AAA')


def test_yahoo_http_422_history_limit_is_remembered_and_no_secret_saved(tmp_path):
    calls=[]
    def fetch(p,s,d):
        calls.append((p,s))
        response=requests.Response();response.status_code=422
        response._content=json.dumps(dict(chart=dict(error=dict(description='5m data must be within the last 60 days.')))).encode()
        raise requests.HTTPError(response=response)
    recovery=source(tmp_path,fetch)
    assert recovery.fetch('yahoo','AAA',date(2025,1,31)).empty
    assert recovery.fetch('yahoo','BBB',date(2025,2,3)).empty
    assert calls==[('yahoo','AAA')]
    cached=source(tmp_path,lambda *a:pytest.fail('cached range error expected'))
    cached.fetch('yahoo','AAA',date(2025,1,31))
    assert cached.yahoo_floor==NOW.date()-timedelta(days=60)


def test_eodhd_repair_passes_verified_tls_session(monkeypatch):
    from contextlib import contextmanager
    from backtesting.winner_intraday_recovery import provider_payload
    sentinel=object()
    @contextmanager
    def session():yield sentinel
    monkeypatch.setattr('common.verified_http.verified_session',session)
    def fetch(symbol,**kwargs):
        assert kwargs['session'] is sentinel and kwargs['interval']=='5m'
        assert symbol=='AAA'
        return []
    monkeypatch.setattr('service.eodhd.clientEodhd.fetch_intraday',fetch)
    assert provider_payload('eodhd','AAA',DAY)==[]


def test_replay_future_gap_blocks_entry_then_same_ticker_can_enter_later(tmp_path):
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,raw=fixture(last=date(2026,10,23),horizon_sessions=1,entry_valid_sessions=10)
    bad_day=date(2026,10,20)
    raw[bad_day,'AAA']=raw[bad_day,'AAA'].drop(index=20)
    raw[date(2026,10,22),'AAA'].loc[1:,['open','close','high','low']]=[104.,104.,104.1,103.9]
    base=args['intraday_source'];base.receipts=[]
    recovery=RecoveringIntradaySource(base,cfg.end_date,cfg.exec_config.winner_pyramiding,
        cache_dir=tmp_path,fetcher=lambda *a:[],now=lambda:NOW)
    recovery.prepare(audit(bad_day))
    args['intraday_source']=recovery
    result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert buys.iloc[0].time.date()==date(2026,10,22)
    assert result.closed_trades_df.iloc[0].exit_reason=='HORIZON_OPEN'
    assert result.tracker_snapshot['winner_replay']['status']=='INCOMPLETE_COVERAGE'
    assert result.tracker_snapshot['winner_replay']['costs']>0
    assert ('AAA',date(2026,10,19)) in recovery.exclusions
    assert ('AAA',date(2026,10,22)) not in recovery.exclusions


def test_repaired_held_bar_replay_keeps_positions_and_stop_protections(tmp_path):
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,raw=fixture()
    day=cfg.end_date
    full=raw[day,'AAA'].copy()
    raw[day,'AAA']=full.drop(index=10)
    base=args['intraday_source'];base.receipts=[]
    recovery=RecoveringIntradaySource(base,day,cfg.exec_config.winner_pyramiding,
        cache_dir=tmp_path,fetcher=lambda p,*a:payload(full),now=lambda:NOW)
    assert recovery.prepare(audit(day))['repaired_sessions']==1
    args['intraday_source']=recovery
    result=BacktestEngine(cfg).run(**args)
    assert result.tracker_snapshot['winner_replay']['open_positions'][0]['qty']>0
    assert result.tracker_snapshot['winner_replay']['status']=='COMPLETED_EXPLORATORY'
