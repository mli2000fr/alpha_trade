import json

import pandas as pd
import pytest

from scripts.research.us_oracle_barrier_grid_summary import summarize, verify_trade_contract


def trade_fixture():
    calendar = pd.bdate_range('2025-02-03', periods=25)
    trade = pd.DataFrame([dict(entry_price=100., replay_initial_stop_price=93.,
        replay_take_profit_price=120., entry_date=calendar[0], exit_date=calendar[20],
        exit_reason='expiry_open', exit_price=105.)])
    return trade, calendar


def test_empty_trade_contract_is_valid():
    assert verify_trade_contract(pd.DataFrame(), .20, .07, pd.DatetimeIndex([])) == {
        'trades': 0, 'expiry_exits': 0, 'exceeding_stop_on_gap': 0}


def test_expiry_contract_counts_entry_as_first_session():
    trade, calendar = trade_fixture()
    assert verify_trade_contract(trade, .20, .07, calendar) == {
        'trades': 1, 'expiry_exits': 1, 'exceeding_stop_on_gap': 0}


@pytest.mark.parametrize('column,value,message', [
    ('replay_initial_stop_price', 90., 'Executed SL'),
    ('replay_take_profit_price', 110., 'Executed TP'),
    ('exit_date', pd.Timestamp('2025-03-04'), 'past the 21st'),
    ('exit_date', pd.Timestamp('2025-02-28'), 'Expiry does not'),
    ('exit_date', pd.Timestamp('2025-02-02'), 'outside session'),
])
def test_unqualified_trade_contract_is_rejected(column, value, message):
    trade, calendar = trade_fixture()
    trade.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        verify_trade_contract(trade, .20, .07, calendar)


def test_gap_loss_is_not_capped_to_configured_stop():
    trade, calendar = trade_fixture()
    trade.loc[0, 'exit_date'] = calendar[2]
    trade.loc[0, 'exit_reason'] = 'stop_loss'
    trade.loc[0, 'exit_price'] = 85.
    assert verify_trade_contract(trade, .20, .07, calendar)['exceeding_stop_on_gap'] == 1
    assert trade.exit_price.iloc[0] == 85.


def test_missing_audit_columns_are_not_silently_accepted():
    trade, calendar = trade_fixture()
    with pytest.raises(ValueError, match='Missing trade audit columns'):
        verify_trade_contract(trade.drop(columns='replay_take_profit_price'), .20, .07, calendar)


@pytest.mark.parametrize('status,verified', [('RUNNING', False), ('VERIFYING_INPUTS', False),
                                           ('COMPLETED', False), ('PARTIAL_FAILED', True)])
def test_final_summary_rejects_unfinished_or_unverified_grid(tmp_path, status, verified):
    (tmp_path/'report.json').write_text(json.dumps(dict(status=status,
        input_hashes_verified_after_all_runs=verified)), encoding='utf-8')
    with pytest.raises(ValueError, match='Grid not complete or not hash-verified'):
        summarize(tmp_path)
