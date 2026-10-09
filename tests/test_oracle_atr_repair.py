from datetime import date
import pandas as pd

from service.market.oracle_atr_repair import calendar_changes, qualify_static_extension


def group(**overrides):
    return {'prediction_date': date(2026, 9, 3), 'exit_min': date(2026, 10, 2),
            'exit_max': date(2026, 10, 2), 'available_min': None,
            'available_max': None, 'missing_available': 1749, **overrides}


CALENDAR = {date(2026, 9, 3): (date(2026, 10, 2), date(2026, 10, 5))}


def test_missing_availability_can_be_repaired_without_touching_returns():
    updates, rebuild = calendar_changes(pd.DataFrame([group()]), CALENDAR)
    assert updates == [{'day': date(2026, 9, 3), 'available': date(2026, 10, 5)}]
    assert not rebuild


def test_wrong_exit_requires_full_day_rebuild_not_availability_patch():
    updates, rebuild = calendar_changes(pd.DataFrame([group(exit_max=date(2026, 10, 5))]), CALENDAR)
    assert not updates
    assert rebuild == ['2026-09-03']


def test_repeated_calendar_repair_is_idempotent():
    updates, rebuild = calendar_changes(pd.DataFrame([group(missing_available=0,
        available_min=date(2026, 10, 5), available_max=date(2026, 10, 5))]), CALENDAR)
    assert not updates and not rebuild


def test_static_extension_requires_original_reference_membership(tmp_path, monkeypatch):
    import json
    import service.market.oracle_atr_repair as repair
    from contextlib import contextmanager
    monkeypatch.chdir(tmp_path)
    profile = tmp_path / 'artifacts/models/batch/oracle/feature_profile.json'
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({'oracle_universe_mode': 'static_bars'}))

    class Conn:
        def execute(self, query, params):
            return self
        def scalars(self):
            return self
        def all(self):
            return ['ORIGINAL', 'DELISTED']

    class Engine:
        @contextmanager
        def connect(self):
            yield Conn()

    original = {('2026-09-03', 'ORIGINAL')}
    monkeypatch.setattr(repair, 'load_stored_membership', lambda *args: original)
    monkeypatch.setattr(repair, 'load_universe_from_bars', lambda *args, **kwargs: original)
    seed, reason = qualify_static_extension(Engine(), 'batch', 20, '2026-09-03')
    assert seed == ['DELISTED', 'ORIGINAL']
    assert reason.startswith('STATIC_BARS_SEED')
    monkeypatch.setattr(repair, 'load_universe_from_bars', lambda *args, **kwargs: original | {('2026-09-03', 'EXTRA')})
    assert qualify_static_extension(Engine(), 'batch', 20, '2026-09-03')[0] == []
    profile.write_text(json.dumps({'oracle_universe_mode': 'pit_dynamic_bars'}))
    assert qualify_static_extension(Engine(), 'batch', 20, '2026-09-03')[0] == []
