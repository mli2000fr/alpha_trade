import json
from types import SimpleNamespace

import pytest

from service.options_directional import accounts
from service.options_directional.store import digest


@pytest.fixture
def publication(tmp_path,monkeypatch):
    report=dict(run_id='opt-'+'a'*32)
    summary=dict(account_id='default',run_id='risk-exact',options_filter_run_id=report['run_id'],
                 run_mode='paper',dry_run=False)
    binding=dict(account_id='default',risk_run_id='risk-exact',report_sha256=digest(report),summary_sha256=digest(summary))
    monkeypatch.setattr(accounts,'consumer_directory',lambda *a:tmp_path)
    return tmp_path,report,summary,binding


def test_valid_current_publication_is_required(publication):
    folder,report,summary,binding=publication
    for name,data in [('risk_binding.json',binding),('risk_summary.json',summary)]:
        (folder/name).write_text(json.dumps(data),encoding='utf-8')
    assert accounts.load_risk_publication(report,'default')==(binding,summary)


def test_archived_publication_is_not_silently_restored(publication):
    folder,report,summary,binding=publication
    archived=folder/'manual_rearms'/'old-risk'
    archived.mkdir(parents=True)
    for name,data in [('risk_binding.json',binding),('risk_summary.json',summary)]:
        (archived/name).write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='Relancer l’étape 11, puis l’étape 12'):
        accounts.load_risk_publication(report,'default')
    assert not (folder/'risk_binding.json').exists()


def test_execution_ui_is_blocked_after_risk_reset_then_available_after_new_risk(publication,monkeypatch):
    folder,report,summary,binding=publication
    from ihm.services import options_prediction_review as ui
    monkeypatch.setattr(ui.store,'sealed_report',lambda *a:report)
    options=SimpleNamespace(options_filter_enabled=True,options_filter_run_id=report['run_id'],account_id='default')
    assert 'Relancer l’étape 11' in ui.execution_publication_block_reason(options,[])
    for name,data in [('risk_binding.json',binding),('risk_summary.json',summary)]:
        (folder/name).write_text(json.dumps(data),encoding='utf-8')
    assert ui.execution_publication_block_reason(options,[]) is None
