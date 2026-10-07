import pandas as pd

from scripts.research.us_concentrated_replay_prepare import candidate_panel, inspect_paths


def test_missing_future_label_does_not_remove_selected_candidate():
    frame = pd.DataFrame(dict(date=pd.to_datetime(['2025-01-02']), symbol=['ABC'],
        oracle_exit_date=[pd.NaT], ORACLE_TOP20=[True], ORACLE_TOP10=[False],
        INTERSECTION_ORACLE_TOP10=[False], future_return=[float('nan')]))
    assert len(candidate_panel(frame,'2025-01-01','2026-09-30')) == 1


def test_next_open_and_h20_boundary_do_not_use_label_exit():
    sessions=pd.bdate_range('2025-01-02', periods=24)
    candidates=pd.DataFrame(dict(date=[sessions[0]],symbol=['ABC'],reserved_identity=[False]))
    bars=pd.DataFrame(dict(date=sessions,symbol='ABC',open=10.,adj_close=10.,
                           volume=100,is_filled=0,instrument_id=1))
    result=inspect_paths(candidates,bars,sessions).iloc[0]
    assert result.next_session_entry == sessions[1]
    assert result.diagnostic_h20_end == sessions[20]
    assert result['flags'] == ''
    assert not result.independently_certified


def test_missing_session_and_zero_volume_remain_visible():
    sessions=pd.bdate_range('2025-01-02', periods=24)
    candidates=pd.DataFrame(dict(date=[sessions[0]],symbol=['ABC'],reserved_identity=[False]))
    bars=pd.DataFrame(dict(date=sessions.delete(1),symbol='ABC',open=10.,adj_close=10.,
                           volume=0,is_filled=0,instrument_id=1))
    result=inspect_paths(candidates,bars,sessions).iloc[0]
    assert result.missing_session_bars == 1
    assert 'MISSING_OR_INVALID_NEXT_OPEN' in result['flags']
    assert 'ZERO_VOLUME_PATH' in result['flags']


def test_immature_path_is_not_dropped_or_certified():
    sessions=pd.bdate_range('2026-09-28',periods=3)
    candidates=pd.DataFrame(dict(date=[sessions[-1]],symbol=['ABC'],reserved_identity=[False]))
    bars=pd.DataFrame(dict(date=sessions,symbol='ABC',open=10.,adj_close=10.,
                           volume=100,is_filled=0,instrument_id=1))
    result=inspect_paths(candidates,bars,sessions).iloc[0]
    assert 'INCOMPLETE_OBSERVATION_CALENDAR' in result['flags']
    assert pd.isna(result.next_session_entry)
