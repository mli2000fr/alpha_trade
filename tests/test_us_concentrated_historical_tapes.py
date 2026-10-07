import pandas as pd
import pytest

from scripts.research.us_concentrated_historical_tapes import (
    decision_rows, apply_overlay, path_flags, verify_hashes, digest, atomic_json,
)


def test_checkpoint_retries_windows_lock_and_keeps_previous_until_replace(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from scripts.research import us_concentrated_historical_tapes as module
    target = tmp_path/'progress.json'
    target.write_text('{"completed_dates": 281}')
    original = Path.replace
    calls, sleeps = [], []

    def locked_then_ok(temporary, destination):
        calls.append(temporary)
        if len(calls) < 3:
            assert json.loads(target.read_text())['completed_dates'] == 281
            raise PermissionError('simulated Windows reader lock')
        return original(temporary, destination)

    monkeypatch.setattr(Path, 'replace', locked_then_ok)
    monkeypatch.setattr(module.time, 'sleep', sleeps.append)
    atomic_json(target, {'completed_dates': 282})
    assert json.loads(target.read_text())['completed_dates'] == 282
    assert len(calls) == 3 and len(sleeps) == 2
    assert not list(tmp_path.glob('*.tmp'))
    assert not list(tmp_path.glob('.*.tmp'))


def test_checkpoint_permanent_lock_preserves_previous_and_raises(tmp_path, monkeypatch):
    from pathlib import Path
    from scripts.research import us_concentrated_historical_tapes as module
    target = tmp_path/'progress.json'
    target.write_text('previous checkpoint')
    calls = []

    def always_locked(temporary, destination):
        calls.append(temporary)
        raise PermissionError('permanent access denied')

    monkeypatch.setattr(Path, 'replace', always_locked)
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    with pytest.raises(PermissionError, match='permanent access denied'):
        atomic_json(target, {'completed_dates': 282})
    assert len(calls) == 20
    assert target.read_text() == 'previous checkpoint'
    assert not list(tmp_path.glob('.*.tmp'))


def candidates():
    return pd.DataFrame({'date': ['2025-01-02'] * 2, 'symbol': ['B', 'A'],
        'proba_extreme': [.7, .7], 'fold_start': ['2024-01-08'] * 2,
        'ORACLE_TOP20': [True, True], 'ORACLE_TOP10': [True, True],
        'INTERSECTION_ORACLE_TOP10': [True, True], 'future_return': [-.9, 5.]})


def test_decision_allowlist_excludes_future_and_ties_are_deterministic():
    result = decision_rows(candidates())
    assert 'future_return' not in result
    assert result.symbol.tolist() == ['A', 'B']
    assert result.oracle_rank.tolist() == [1, 2]


def test_duplicate_candidate_rejected():
    frame = candidates()
    with pytest.raises(ValueError, match='Duplicate'):
        decision_rows(pd.concat([frame, frame]))


def test_overlay_only_research_copy_and_exact_target():
    frame = pd.DataFrame({'symbol': ['BAND'], 'date': pd.to_datetime(['2026-06-18']), 'volume': [0]})
    overlay = pd.DataFrame({'symbol': ['BAND'], 'date': ['2026-06-18'],
                            'original_volume': [0], 'replacement_volume': [1997781]})
    corrected = apply_overlay(frame, overlay)
    assert frame.volume.iloc[0] == 0
    assert corrected.volume.iloc[0] == 1997781
    with pytest.raises(ValueError, match='Overlay'):
        apply_overlay(corrected, overlay)


def test_resume_file_integrity(tmp_path):
    file = tmp_path/'data'
    file.write_text('original')
    hashes = {'data': digest(file)}
    verify_hashes(tmp_path, hashes)
    file.write_text('changed')
    with pytest.raises(ValueError, match='Source changed'):
        verify_hashes(tmp_path, hashes)


def test_path_flags_preserve_missing_data_and_no_free_terminal_exit():
    days = pd.date_range('2025-01-02', periods=3)
    bars = pd.DataFrame({'open': [100., 100.], 'high': [101., 101.],
        'low': [99., 99.], 'close': [100., 100.], 'volume': [1., 1.],
        'is_filled': [0., 0.], 'instrument_id': [1., 1.]}, index=days[:2])
    flags = path_flags({'execution_date': days[0], 'replay_exit_date': pd.NaT}, bars, days)
    assert 'MISSING_ACTUAL_PATH_BAR' in flags
    assert 'OPEN_AT_TERMINAL_LIQUIDATION_NOT_TAPED' in flags


def test_gap_exit_and_posthumous_watcher_are_not_silently_certified():
    days = pd.date_range('2025-01-02', periods=3)
    bars = pd.DataFrame({'open': [100., 80., 100.], 'high': [101., 95., 101.],
        'low': [99., 75., 99.], 'close': [100., 90., 100.], 'volume': 1.,
        'is_filled': 0., 'instrument_id': 1.}, index=days)
    flags = path_flags({'execution_date': days[0], 'replay_exit_date': days[1],
        'replay_exit_price': 95., 'replay_exit_reason': 'initial_stop', 'side': 'buy',
        'watcher_transition_effective_date': days[2]}, bars, days)
    assert 'OPEN_GAP_EXIT_PRICE_REQUIRES_RECONCILIATION' in flags
    assert 'WATCHER_TRANSITION_AFTER_EXIT_REQUIRES_RECONCILIATION' in flags


@pytest.mark.parametrize('side', ['buy', 'sell'])
def test_historical_assembler_uses_real_pipeline_and_unit_notional_is_not_approval(side):
    from scripts.research.us_concentrated_historical_tapes import assemble_day
    from scripts.research.us_concentrated_contract_audit import frozen_configs
    days = pd.bdate_range('2025-01-02', periods=22)
    bars = pd.DataFrame({'open': 100., 'high': 101., 'low': 99., 'close': 100.,
        'volume': 100000., 'is_filled': 0., 'instrument_id': 1.}, index=days)
    bars.loc[days[-1], 'high'] = 107.
    bars.loc[days[-1], 'low'] = 93.
    matrices = {name: bars[[name]].rename(columns={name: 'TEST'}) for name in ('open', 'high', 'low')}
    atr = pd.DataFrame({'TEST': 2.}, index=days)
    counts = pd.DataFrame({'TEST': 20.}, index=days)
    frame = pd.DataFrame({'date': [days[-2]], 'symbol': ['TEST'], 'side': [side],
        'proba_extreme': [.9], 'oracle_rank': [1], 'ORACLE_TOP20': [True],
        'ORACLE_TOP10': [True], 'INTERSECTION_ORACLE_TOP10': [True]})
    _, execution = frozen_configs()
    audit, tape, orders, events = assemble_day(frame, {'TEST': bars}, matrices['open'],
        matrices['high'], matrices['low'], atr, counts, execution)
    assert audit.entry_status.tolist() == ['UNIT_PROBE_READY']
    assert tape.filled_qty.tolist() == [1.]
    assert tape.execution_date.iloc[0] == days[-1]
    assert tape.replay_exit_reason.iloc[0] == 'initial_stop'  # both touch: conservative stop first
    assert tape.ORACLE_TOP10.iloc[0]
    assert tape.quantity_scope.iloc[0] == 'ONE_UNIT_NOT_PORTFOLIO_APPROVED'
    assert not orders.empty and not events.empty
    matrices['open'].loc[days[-1], 'TEST'] = 105.
    audit, tape, _, _ = assemble_day(frame, {'TEST': bars}, matrices['open'],
        matrices['high'], matrices['low'], atr, counts, execution)
    assert audit.entry_status.tolist() == ['ENTRY_GAP_EXCEEDS_3PCT']
    assert tape.empty
