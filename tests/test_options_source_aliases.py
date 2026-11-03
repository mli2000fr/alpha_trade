"""Manual/batch universe aliases must preserve sealed membership and latest-run guards."""
from datetime import datetime, timezone

import pytest

from service.options_directional import store
from service.options_directional.accounts import shared_latest_matching, shared_qualified


RUN = 'opt-'+'a'*32
OTHER = 'opt-'+'b'*32
SHORT = 'universe-file:tradable.txt'
FULL = 'universe-file:config/univers_batch/tradable.txt'
NOW = datetime(2026, 11, 3, 7, tzinfo=timezone.utc)


@pytest.fixture
def context(tmp_path, monkeypatch):
    project = tmp_path/'project'
    for folder in ['config/univers', 'config/univers_batch']:
        path = project/folder
        path.mkdir(parents=True)
        (path/'tradable.txt').write_text('A,B,C', encoding='utf-8')
    monkeypatch.setattr(store, 'PROJECT_ROOT', project)
    monkeypatch.setattr(store, 'ROOT', tmp_path/'runs')
    monkeypatch.setattr(store, 'validate_window', lambda *a, **k: None)
    store.ROOT.mkdir()
    report = dict(run_id=RUN, status='COMPLETED', trade_date='2026-11-02',
        batch_id='model-test', account_id='default', symbol_source=FULL,
        capital_preset_key='capital_2001_5000', cutoff_utc='2026-11-03T00:10:00+00:00',
        config={'max_age_hours': 24}, rows=[dict(symbol='A', selected=True)], selected=['A'])
    sealed = store.seal(RUN, report, {'universe': ['A', 'B', 'C']})
    return project, sealed, dict(trade_date='2026-11-02', batch_id='model-test',
        symbol_source=SHORT, now=NOW)


def test_shared_manual_risk_finds_batch_universe_and_preserves_archive(context):
    _, report, kwargs = context
    selected = shared_latest_matching(account_id='test1', capital_preset_key='different-consumer', **kwargs)
    assert selected == report and selected['symbol_source'] == FULL
    assert shared_qualified(RUN, account_id='test2', **kwargs) == report


def test_aliases_do_not_require_same_order_or_text_layout(context):
    project, _, kwargs = context
    (project/'config/univers/tradable.txt').write_text('# description\nC,A\nB,B', encoding='utf-8')
    assert store.latest_matching(**kwargs)['run_id'] == RUN


def test_same_basename_with_different_membership_is_rejected(context):
    project, _, kwargs = context
    (project/'config/univers/tradable.txt').write_text('A,B,D', encoding='utf-8')
    with pytest.raises(ValueError, match='symbol_source'):
        store.qualified(RUN, **kwargs)
    with pytest.raises(ValueError, match='Aucun filtre'):
        store.latest_matching(**kwargs)


def test_two_changed_matching_files_do_not_override_frozen_universe(context):
    project, _, kwargs = context
    for folder in ['univers', 'univers_batch']:
        (project/f'config/{folder}/tradable.txt').write_text('A,B,D', encoding='utf-8')
    with pytest.raises(ValueError, match='diffère du snapshot'):
        store.latest_matching(**kwargs)


def test_missing_alias_never_falls_back_to_another_directory(context):
    project, _, kwargs = context
    (project/'config/univers/tradable.txt').unlink()
    with pytest.raises(ValueError, match='symbol_source'):
        store.qualified(RUN, **kwargs)


def test_newer_corrupt_aliased_run_blocks_older_valid_run(context):
    _, report, kwargs = context
    store.seal(OTHER, {**report, 'run_id': OTHER, 'cutoff_utc': '2026-11-03T00:20:00+00:00'},
               {'universe': ['A', 'B', 'C']})
    (store.directory(OTHER)/'inputs.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='altérée'):
        store.latest_matching(**kwargs)


def test_newer_failed_aliased_run_blocks_older_valid_run(context):
    _, report, kwargs = context
    folder = store.directory(OTHER)
    folder.mkdir()
    store.write_new(folder/'failure.json', {**report, 'run_id': OTHER, 'status': 'FAILED',
                                          'cutoff_utc': '2026-11-03T00:20:00+00:00'})
    with pytest.raises(ValueError, match='Dernière analyse options échouée'):
        store.latest_matching(**kwargs)


@pytest.mark.parametrize('change', [dict(trade_date='2026-10-30'), dict(batch_id='wrong'),
                                   dict(now=datetime(2026, 11, 5, tzinfo=timezone.utc))])
def test_aliases_preserve_date_model_and_expiry_controls(context, change):
    _, _, kwargs = context
    with pytest.raises(ValueError):
        store.qualified(RUN, **{**kwargs, **change})
