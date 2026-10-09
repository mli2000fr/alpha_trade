from datetime import UTC, date, datetime, timedelta
import json

import pytest

from common.market_calendar import get_market_calendar
from service.fr import prospective_window_16g as module


def protocol():
    return {'market_code': 'FR_EQ', 'calendar': 'XPAR',
        'status': 'PREPARATION_ONLY_NOT_RELEASED', 'pilot_symbols': list(module.PILOT),
        **{k: False for k in ('serving_allowed', 'orders_allowed', 'sql_writes',
                             'model_inference_allowed', 'model_refit_allowed')}}


def test_actual_xpar_full_window():
    calendar = get_market_calendar('FR_EQ', allow_us_weekday_fallback=False)
    sessions, decision, opening = module.window(calendar, date(2026, 9, 12), 21)
    assert len(sessions) == 21
    assert sessions[0] == date(2026, 9, 14)
    assert sessions[-1] == date(2026, 10, 12)
    assert decision == date(2026, 10, 13)
    assert opening == datetime(2026, 10, 13, 7, tzinfo=UTC)


@pytest.mark.parametrize('count', [20, 22, True, 21.0])
def test_feature_window_cannot_be_shortened(count):
    with pytest.raises(ValueError):
        module.window(None, date(2026, 9, 12), count)


@pytest.mark.parametrize('field', ['serving_allowed', 'orders_allowed', 'sql_writes',
                                 'model_inference_allowed', 'model_refit_allowed'])
def test_no_capability_enabled(field):
    cfg = protocol()
    cfg[field] = True
    with pytest.raises(ValueError):
        module.validate(cfg)


def test_frozen_pilot():
    cfg = protocol()
    cfg['pilot_symbols'] = ['AIR.PA']
    with pytest.raises(ValueError):
        module.validate(cfg)


def test_calendar_duplicate_sessions_rejected():
    class InvalidCalendar:
        def session_dates(self, start, end):
            return [start] * 21
    with pytest.raises(ValueError):
        module.window(InvalidCalendar(), date(2026, 9, 12), 21)


def test_future_inventory_remains_non_releasing(tmp_path, monkeypatch):
    base = tmp_path / 'artifacts/fr'
    base.mkdir(parents=True)
    packet = {'market_code': 'FR_EQ', 'matrix': [
        {'symbol': s, 'isin': i, 'mic': 'XPAR'} for s, i in module.PILOT.items()]}
    packet_path = base / 'packet.json'
    packet_path.write_text(json.dumps(packet), encoding='utf-8')
    _, digest = module.checked(packet_path)
    replay = {'source_packet_sha256': digest, 'start': '2026-09-12', 'end': '2026-09-25',
        'status': 'PREANCHOR_RESERVED', 'market_code': 'FR_EQ', 'anomalies': [],
        'missing_publication_days': [], 'created_at': '2026-10-08T19:53:00+00:00',
        'sessions_before_new_anchor': ['2026-09-09', '2026-09-10', '2026-09-11']}
    replay_path = base / 'replay.json'
    replay_path.write_text(json.dumps(replay), encoding='utf-8')
    cfg = {**protocol(), 'warmup_sessions': 21, 'anchor_full_date': '2026-09-12',
        'source_packet': str(packet_path), 'preanchor_replay': str(replay_path),
        'bootstrap_dir': str(base / 'bootstrap')}
    monkeypatch.setattr(module, 'observed_payloads', lambda *a: ([], []))
    monkeypatch.setattr(module, 'master_at', lambda *a: (None, ['MISSING'], []))
    result = module.prepare(cfg, root=tmp_path, now=datetime(2026, 10, 8, 20, tzinfo=UTC))
    assert result['closed_session_count'] == 19
    assert result['not_yet_closed_sessions'] == ['2026-10-09', '2026-10-12']
    assert result['matrix'][0]['valid_closed_session_bars'] == 0
    assert len(result['matrix'][0]['missing_closed_sessions']) == 19
    assert not result['future_release_qualified']
    assert not result['model_inference_executed']
    assert not result['orders_allowed']
    assert not result['original_test_changed']
    assert result['archive_errors'] == []
    received_cutoffs = []
    monkeypatch.setattr(module, 'observed_payloads',
        lambda folder, cutoff, *args: (received_cutoffs.append(cutoff) or [], []))
    with pytest.raises(ValueError, match='opening has not occurred'):
        module.prepare(cfg, root=tmp_path, now=datetime(2026, 10, 12, 20, tzinfo=UTC), phase='confirm')
    assert received_cutoffs == []
    confirmation = module.prepare(cfg, root=tmp_path,
        now=datetime(2026, 10, 13, 16, tzinfo=UTC), phase='confirm')
    assert set(received_cutoffs) == {datetime(2026, 10, 13, 7, tzinfo=UTC)}
    assert confirmation['closed_session_count'] == 21
    assert confirmation['not_yet_closed_sessions'] == []
    assert confirmation['status'] == 'OPENING_INVENTORY_CONFIRMED_NOT_RELEASED'
    assert not confirmation['future_release_qualified']


def test_naive_audit_time_rejected():
    with pytest.raises(ValueError):
        module.prepare(protocol(), now=datetime(2026, 10, 8))
