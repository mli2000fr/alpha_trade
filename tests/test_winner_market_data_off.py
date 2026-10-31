"""No unnecessary data dependency; fills, protections and horizon stay active."""
from copy import deepcopy
from datetime import datetime,timedelta
from unittest.mock import Mock

import pytest

from execution_engine.winner_market import NativeWinnerMarket
from test_winner_runtime import setup,tick,NOW

pytestmark=pytest.mark.usefixtures('isolated_winner_config')


def held(**policy):
    cfg,store,repo,broker=setup(**policy)
    tick(cfg,store,repo,broker)
    return cfg,store,repo,broker


def test_held_no_trailing_no_add_does_not_call_market_or_risk():
    cfg,store,repo,broker=held(trailing_stop_pct=None,reinforcement_enabled=False)
    before=deepcopy(store.rows()[0]['state'])
    market=Mock(side_effect=AssertionError('No intraday call'))
    risk=Mock(side_effect=AssertionError('No extra buy approval'))
    result=tick(cfg,store,repo,broker,now=NOW+timedelta(minutes=5),source=market,guard=risk)
    after=store.rows()[0]['state']
    market.assert_not_called();risk.assert_not_called()
    assert not result['winner_entries_blocked'] and not result['winner_failures']
    assert after['lots']==before['lots'] and after['due_open']==before['due_open']
    assert len(broker.calls)==1


def test_market_adapter_also_skips_bars_and_quotes_for_inactive_held_signals(monkeypatch):
    cfg,store,_,_=held(trailing_stop_pct=None,reinforcement_enabled=False)
    bars=Mock(side_effect=AssertionError('No five-minute download'))
    quotes=Mock(side_effect=AssertionError('No live quote'))
    monkeypatch.setattr('service.alpaca.intraday_bars.fetch_intraday',bars)
    monkeypatch.setattr('service.market.live_quotes.fetch_latest_quotes',quotes)
    snapshot=NativeWinnerMarket(None,'default',cfg)(store.rows()[0]['state'],NOW)
    assert snapshot['market_data_required'] is False and snapshot['bars']==[]
    assert snapshot['feed'] is None and snapshot['ask'] is None and snapshot['bid'] is None
    bars.assert_not_called();quotes.assert_not_called()


@pytest.mark.parametrize('policy', [dict(trailing_stop_pct=.15,reinforcement_enabled=False),
    dict(trailing_stop_pct=None,reinforcement_enabled=True)])
def test_needed_trailing_or_add_data_are_not_bypassed(monkeypatch,policy):
    cfg,store,_,_=held(**policy)
    bars=Mock(side_effect=ValueError('LIVE_DATA_STILL_REQUIRED'))
    monkeypatch.setattr('service.alpaca.intraday_bars.fetch_intraday',bars)
    with pytest.raises(ValueError,match='LIVE_DATA_STILL_REQUIRED'):
        NativeWinnerMarket(None,'default',cfg)(store.rows()[0]['state'],NOW)
    bars.assert_called_once()


def test_initial_confirmation_is_still_required_when_trailing_and_add_are_off(monkeypatch):
    cfg,store,_,_=setup(trailing_stop_pct=None,reinforcement_enabled=False)
    bars=Mock(side_effect=ValueError('INITIAL_CONFIRMATION_REQUIRED'))
    monkeypatch.setattr('service.alpaca.intraday_bars.fetch_intraday',bars)
    with pytest.raises(ValueError,match='INITIAL_CONFIRMATION_REQUIRED'):
        NativeWinnerMarket(None,'default',cfg)(store.rows()[0]['state'],NOW)
    bars.assert_called_once()


def test_horizon_exit_remains_active_without_trailing_or_any_market_data():
    cfg,store,repo,broker=held(trailing_stop_pct=None,reinforcement_enabled=False)
    due=datetime.fromisoformat(store.rows()[0]['state']['due_open'])
    market=Mock(side_effect=AssertionError('No intraday call for horizon exit'))
    result=tick(cfg,store,repo,broker,now=due+timedelta(minutes=1),source=market)
    assert result['winner_exits_submitted']==1 and broker.calls[-1].intent_role=='exit'
    market.assert_not_called()


def test_stop_fill_is_reconciled_without_intraday_or_new_order():
    cfg,store,repo,broker=held(trailing_stop_pct=None,reinforcement_enabled=False)
    lot=store.rows()[0]['state']['lots'][0]
    broker.orders[lot['stop_order_id']].update(status='filled',filled_qty=str(lot['remaining']),
        filled_avg_price=str(lot['stop']),filled_at=NOW.isoformat())
    broker.position_quantity=0
    market=Mock(side_effect=AssertionError('No market data to reconcile a stop'))
    tick(cfg,store,repo,broker,now=NOW+timedelta(minutes=5),source=market)
    market.assert_not_called()
    assert not store.rows() and store.rows(active_only=False)[0]['state']['status']=='CLOSED'
    assert len(broker.calls)==1
