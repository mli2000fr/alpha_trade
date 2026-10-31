"""Wall-clock buys after delayed evidence; no invented real-time quotes."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pandas as pd
import pytest

from common.winner_delayed import delayed_snapshot, delayed_price_limit
from common.winner_pyramiding import WinnerPyramidingConfig, confirmed_breakout
from tests.test_winner_runtime import setup, tick, NOW, market
from tests.test_winner_risk import context
from execution_engine.winner_risk import reapprove_campaign


pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def evidence(state,now):
    policy=WinnerPyramidingConfig(**state['policy'])
    bars=market(state,now-timedelta(seconds=policy.market_data_delay_seconds))['bars']
    return delayed_snapshot(bars,policy,now) | dict(prior_session_high=99.,available_cash=4000.)


def native(state,version,quantity,snapshot,now,kind):
    ctx=context() | dict(standard_entry_quote_check_enabled=False,delayed_sip_allowed=True)
    return reapprove_campaign(state,version,quantity,snapshot,now,kind,context=ctx)


def test_real_risk_outbox_buy_protection_with_delayed_evidence():
    cfg,store,repo,broker=setup(market_data_delay_seconds=900,trailing_stop_pct=None)
    report=tick(cfg,store,repo,broker,source=evidence,guard=native)
    assert report['winner_buys_submitted']==1 and report['winner_protections_submitted']==1
    state=store.rows()[0]['state']
    approval=next(o['approval'] for o in state['operations'] if o['action']=='ENTRY')
    assert approval['realtime_sip_qualified'] is False and approval['delayed_sip_qualified'] is True
    assert approval['price_basis']=='bounded_delayed_sip_limit'
    assert approval['limit_price']==102.01
    assert approval['delayed_evidence']['ask'] is None
    assert state['first_fill_at']==NOW.isoformat()  # Actual broker fill, not old candle time.
    assert state['due_open'] and state['lots'][0]['stop_order_id']
    tick(cfg,store,repo,broker,source=evidence,guard=native)
    assert len(broker.calls)==1  # Restart/tick cannot duplicate initial buy.


def test_delayed_admission_cannot_be_relabelled_realtime_or_exceed_frozen_gap():
    from execution_engine.winner_plans import reserve_operation
    cfg,store,_,_=setup(market_data_delay_seconds=900)
    row=store.rows()[0];state=row['state'];snapshot=evidence(state,NOW)
    state['entry_policy']['max_entry_gap_pct']=.005
    assert delayed_price_limit(state,snapshot,NOW)==100.5
    approval=native(state,row['version'],1,snapshot,NOW,'ENTRY')
    assert approval['limit_price']==100.5
    forged=dict(approval,realtime_sip_qualified=True)
    with pytest.raises(ValueError,match='Preuve native SIP retardée'):
        reserve_operation(store,state,row['version'],action='ENTRY',quantity=1,approval=forged,now=NOW)


def test_old_frozen_policy_does_not_silently_accept_delayed_bars():
    cfg,store,_,_=setup()
    bars=evidence(store.rows()[0]['state'],NOW)['bars']
    policy=replace(cfg.winner_pyramiding,market_data_delay_seconds=900)
    shifted=[dict(b,timestamp=b['timestamp']-timedelta(minutes=15)) for b in bars]
    assert confirmed_breakout(shifted,99.,policy,now=NOW)
    assert not confirmed_breakout(shifted,99.,cfg.winner_pyramiding,now=NOW)


@pytest.mark.parametrize('change',[dict(feed='iex'),dict(ask=101.),dict(data_cutoff=NOW.isoformat()),
    dict(delayed_reference_price=999.),dict(received_at=(NOW-timedelta(minutes=5)).isoformat())])
def test_fake_or_stale_delayed_receipts_are_rejected(change):
    cfg,store,_,_=setup(market_data_delay_seconds=900)
    state=store.rows()[0]['state']
    with pytest.raises(ValueError):
        delayed_price_limit(state,evidence(state,NOW)|change,NOW)


def test_native_market_requests_only_entitled_range_and_never_latest_quotes(monkeypatch):
    from execution_engine.winner_market import NativeWinnerMarket
    from common.winner_pyramiding import regular_bounds
    cfg,store,_,_=setup(market_data_delay_seconds=900)
    state=store.rows()[0]['state'];calls=[]
    def fetch(symbol,**kw):
        calls.append(kw)
        assert kw['end_epoch'] <= (NOW-timedelta(minutes=15)).timestamp()
        if datetime.fromtimestamp(kw['end_epoch'],UTC).date()<NOW.date():
            opening,closing=regular_bounds(datetime.fromtimestamp(kw['start_epoch'],UTC).date())
            return [dict(timestamp=t.timestamp(),open=98.,high=99.,low=97.,close=98.,volume=1000.)
                for t in pd.date_range(opening,closing,freq='5min',inclusive='left')]
        return [dict(b,timestamp=b['timestamp'].timestamp(),volume=1000.) for b in evidence(state,NOW)['bars']]
    quote=Mock(side_effect=AssertionError('No latest SIP entitlement needed'))
    monkeypatch.setattr('service.alpaca.intraday_bars.fetch_intraday',fetch)
    monkeypatch.setattr('service.market.live_quotes.fetch_latest_quotes',quote)
    snapshot=NativeWinnerMarket(None,'default',cfg)(state,NOW)
    assert snapshot['market_data_mode']=='delayed_sip' and snapshot['ask'] is None
    assert len(calls)==2 and delayed_price_limit(state,snapshot,NOW)==102.01
    quote.assert_not_called()


def test_replay_waits_15_minutes_and_buys_at_later_price():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,raw=fixture(market_data_delay_seconds=900)
    # Delayed signal closes at102; by its availability the price is103.
    frame=raw[(cfg.start_date,'AAA')]
    frame.loc[frame.timestamp.ge(pd.Timestamp('2026-10-19T14:00:00Z')),
              ['open','close','high','low']]=[103.,103.,103.1,102.9]
    result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert len(buys)==1 and buys.iloc[0].price==103.
    assert buys.iloc[0].time>=pd.Timestamp('2026-10-19T14:00:00Z')


def test_replay_cannot_buy_above_delayed_limit():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,raw=fixture(market_data_delay_seconds=900)
    frame=raw[(cfg.start_date,'AAA')]
    frame.loc[frame.timestamp.ge(pd.Timestamp('2026-10-19T14:00:00Z')),
              ['open','close','high','low']]=[110.,110.,110.1,109.9]
    result=BacktestEngine(cfg).run(**args)
    assert not result.trade_events_df.event.eq('BUY_FILL').any()


def test_zero_confirmation_keeps_standard_no_quote_entry_despite_configured_delay():
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,_=fixture(market_data_delay_seconds=900,confirmation_bars=0,
                      standard_entry_quote_check_enabled=False)
    result=BacktestEngine(cfg).run(**args)
    buys=result.trade_events_df.loc[result.trade_events_df.event.eq('BUY_FILL')]
    assert len(buys)==1 and buys.iloc[0].time==pd.Timestamp('2026-10-19T13:30:00Z')
