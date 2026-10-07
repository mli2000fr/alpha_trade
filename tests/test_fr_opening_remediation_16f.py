from datetime import UTC, date, datetime
import json

import pytest

from service.fr import opening_remediation_16f as module


def test_catalogue_absence_is_not_continuity_proof():
    rows = module.probe_catalogue([date(2026,9,9)], datetime(2026,10,7,20,tzinfo=UTC),
        loader=lambda *args: [], context_factory=lambda: None)
    assert rows[0]['status'] == 'PUBLICATION_ABSENT_OR_UNKNOWN'
    assert not rows[0]['continuity_qualified']


def test_catalogue_probe_error_is_explicit_and_sanitized():
    def failed(*args):
        raise OSError('https://source/?secret=private')
    rows = module.probe_catalogue([date(2026,10,7)], datetime(2026,10,7,20,tzinfo=UTC),
        loader=failed, context_factory=lambda: None)
    assert rows[0]['status'] == 'PROBE_FAILED'
    assert 'private' not in json.dumps(rows)


@pytest.mark.parametrize('days', [
    [date(2026,10,7)] * 2,
    [date(2026,10,5), date(2026,10,6), date(2026,10,7)],
    [date(2026,10,8)],
])
def test_probe_is_bounded_and_not_future(days):
    with pytest.raises(ValueError):
        module.probe_catalogue(days, datetime(2026,10,7,20,tzinfo=UTC),
            loader=lambda *a: pytest.fail('unexpected network'), context_factory=lambda: None)


def prepare(tmp_path):
    old = tmp_path/module.ORIGINAL
    old.parent.mkdir(parents=True)
    old.write_text(json.dumps({'phase':'confirm','decision_at':'2026-10-07T07:00:00+00:00',
        'audit_at':'2026-10-07T12:57:00+00:00',
        'daily_assembly':{'features_computed_count':242,'candidate_rows_count':0}}))
    plan = tmp_path/module.NEW_PROTOCOL
    plan.parent.mkdir(parents=True)
    plan.write_text(json.dumps({'schema_version':1,'market_code':'FR_EQ','calendar':'XPAR',
        'decision_date':'2026-10-08','serving_allowed':False,'orders_allowed':False,'sql_writes':False}))
    return old


def test_current_warmup_does_not_rewrite_original_or_authorize_serving(tmp_path,monkeypatch):
    old = prepare(tmp_path)
    content = old.read_bytes()
    monkeypatch.setattr(module, 'qualify', lambda *a,**k: {'servable_count':0})
    result = module.audit(tmp_path/'warmup', root=tmp_path, now=datetime(2026,10,7,20,tzinfo=UTC))
    assert old.read_bytes() == content
    assert not result['serving_allowed'] and not result['orders_allowed'] and not result['sql_writes']
    assert result['original_features_computed'] == 242
    assert result['next_protocol']['decision_date'] == '2026-10-08'
    assert result['warmup']['servable_count'] == 0


def test_changed_original_cutoff_is_rejected(tmp_path,monkeypatch):
    old = prepare(tmp_path)
    data = json.loads(old.read_bytes()); data['decision_at'] = '2026-10-07T13:00:00+00:00'
    old.write_text(json.dumps(data))
    monkeypatch.setattr(module,'qualify',lambda *a,**k: pytest.fail('Invalid original report'))
    with pytest.raises(ValueError,match='cutoff'):
        module.audit(tmp_path/'warmup',root=tmp_path,now=datetime(2026,10,7,20,tzinfo=UTC))


def test_remediation_config_keeps_market_and_release_guards():
    from service.fr.operational_batch_15a import load_section
    master = load_section('fr_security_master_sync', module.ROOT/'batch_fr.yaml')
    actions = load_section('fr_corporate_actions_sync', module.ROOT/'batch_fr.yaml')
    assert str(master['run_hours']) == '7'
    assert master['timezone'] == 'Europe/Paris'
    assert actions['lookback_days'] == 31
    for cfg in (master, actions):
        assert cfg['market_code'] == 'FR_EQ'
        assert not cfg['serving_enabled'] and not cfg['canonical_writes_enabled']
