from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from service.market.new_entry_data_guard import check_new_entry_data, entry_sessions, validate_entry_bars, validate_entry_prices

NOW = datetime(2026,10,9,6,tzinfo=timezone.utc)  # 8h Paris: Oct 8 is still the signal day.


def bars():
    sessions = entry_sessions(date(2026,10,8), now=NOW)
    frame = pd.DataFrame({'symbol': ['GOOD']*len(sessions), 'date': sessions,
        'open': 10., 'high': 12., 'low': 9., 'close': 11., 'volume': 1000,
        'is_filled': 0, 'data_source': 'eodhd_eod', 'data_adjustment': 'split',
        'ingested_at': '2026-10-08 22:00:00', 'last_updated': '2026-10-08 22:00:00'})
    return frame, sessions


def test_overnight_signal_and_us_holiday_half_day_closes():
    assert entry_sessions(date(2026,10,8), now=NOW)[-1] == date(2026,10,8)
    with pytest.raises(ValueError, match='dernière séance'):
        entry_sessions(date(2026,10,7), now=NOW)
    # July 3 holiday, then weekend: July 2 signal is valid on July 6 pre-open.
    assert entry_sessions(date(2026,7,2), now=datetime(2026,7,6,8,tzinfo=timezone.utc))[-1] == date(2026,7,2)
    # Black Friday closes 18h UTC. Still unavailable at 18:10, available at 18:15.
    with pytest.raises(ValueError):
        entry_sessions(date(2026,11,27), now=datetime(2026,11,27,18,10,tzinfo=timezone.utc))
    assert entry_sessions(date(2026,11,27), now=datetime(2026,11,27,18,15,tzinfo=timezone.utc))[-1] == date(2026,11,27)


def test_complete_real_bars_pass_missing_symbol_rejected():
    frame, sessions = bars()
    assert validate_entry_bars(frame, ['GOOD', 'MISSING'], sessions, now=NOW) == {
        'MISSING': 'MISSING_OR_DUPLICATE_SESSIONS'}


@pytest.mark.parametrize('column,value,reason', [
    ('close', float('nan'), 'INVALID_OHLCV'), ('volume', 0, 'INVALID_OHLCV'),
    ('high', 8., 'INCONSISTENT_OHLC'), ('is_filled', 1, 'SYNTHETIC_OR_UNKNOWN_BAR'),
    ('is_filled', None, 'SYNTHETIC_OR_UNKNOWN_BAR'),
    ('data_adjustment', 'all', 'UNQUALIFIED_PRICE_SOURCE_OR_ADJUSTMENT'),
    ('data_source', '', 'UNQUALIFIED_PRICE_SOURCE_OR_ADJUSTMENT'),
    ('ingested_at', '2026-10-10 00:00:00', 'BAR_NOT_YET_AVAILABLE'),
])
def test_bad_data_rejects_only_new_candidate(column, value, reason):
    frame, sessions = bars()
    frame.loc[frame.index[-1], column] = value
    assert validate_entry_bars(frame, ['GOOD'], sessions, now=NOW) == {'GOOD': reason}


def test_missing_duplicate_and_metadata_fail_closed():
    frame, sessions = bars()
    for bad in (frame.iloc[:-1], pd.concat([frame, frame.iloc[-1:]])):
        assert validate_entry_bars(bad, ['GOOD'], sessions, now=NOW)['GOOD'] == 'MISSING_OR_DUPLICATE_SESSIONS'
    assert validate_entry_bars(frame.drop(columns='is_filled'), ['GOOD'], sessions, now=NOW)['GOOD'] == 'BAR_METADATA_MISSING'
    assert check_new_entry_data(None, [], date(2026,10,8), now=NOW) == {}


def test_sizing_inputs_require_finite_positive_atr_adv_and_current_dates():
    from risk_management.models import PriceInfo
    day = date(2026,10,8)
    assert validate_entry_prices({'GOOD': PriceInfo('GOOD', 11., 1., day, day, 1000.)}, ['GOOD'], day) == {}
    for value in (None, 0, float('inf'), float('nan')):
        assert validate_entry_prices({'GOOD': PriceInfo('GOOD', 11., 1., day, day, value)}, ['GOOD'], day)['GOOD'] == 'PRICE_ATR_ADV_INVALID'
    assert validate_entry_prices({'GOOD': PriceInfo('GOOD', 11., 1., day, date(2026,10,7), 1000.)}, ['GOOD'], day)


def test_sql_failure_and_other_market_never_allow_entry():
    engine = MagicMock()
    engine.connect.side_effect = RuntimeError('DB offline')
    rejected = check_new_entry_data(engine, ['GOOD'], date(2026,10,8), now=NOW, raw_config={})
    assert 'DB offline' in rejected['GOOD']
    engine.connect.side_effect = None
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = 'alpha_trade_fr'
    assert 'alpha_trade' in check_new_entry_data(engine, ['GOOD'], date(2026,10,8), now=NOW, raw_config={})['GOOD']


def test_executor_rechecks_before_reserving_or_sending_entry(monkeypatch):
    from execution_engine.executor import ProductionExecutor
    from execution_engine.config import ExecutionConfig
    from execution_engine.models import OrderIntent
    repo, broker = MagicMock(), MagicMock()
    repo.acquire_execution_lock.return_value = True
    target = SimpleNamespace(symbol='GOOD', sector='Tech', risk_run_id='risk-1', trade_date=date(2026,10,8),
        target_notional=110., target_shares=10, entry_price=11., price_asof_date=date(2026,10,8),
        previous_close=11., initial_risk_dollars=7., risk_budget_dollars=10., target_weight=.1,
        stop_price_initial=10., risk_per_share=1.)
    repo.load_portfolio_targets.return_value = [target]
    repo.load_previous_closes_asof.return_value = {}
    intent = OrderIntent(intent_id='entry-1',risk_run_id='risk-1',exec_run_id='exec-1',symbol='GOOD',side='buy',
        qty=10,order_type='market',limit_price=None,trail_percent=None,broker_mode='paper',parent_intent_id=None,
        intent_role='entry',idempotency_key='entry-1',decision_price=11.)
    cfg = ExecutionConfig(dry_run=False, allow_outside_rth=True, inter_order_delay_ms=0)
    executor = ProductionExecutor(cfg, repo, broker, MagicMock())
    broker.get_account_snapshot.return_value = {'equity': 10000.,'cash':10000.,'buying_power':10000.,
                                               'non_marginable_buying_power':10000.,'daytrade_count':0}
    broker.list_recent_orders.return_value = []
    monkeypatch.setattr('execution_engine.executor.build_entry_intents', lambda *a, **kw: [intent])
    monkeypatch.setattr('service.market.new_entry_data_guard.check_new_entry_data', lambda *a, **kw: {'GOOD':'MISSING_SESSIONS'})
    metrics = executor.execute_run(risk_run_id='risk-1', trade_date=date(2026,10,8))
    assert metrics['new_entry_data_rejected'] == 1
    broker.submit_order.assert_not_called()
