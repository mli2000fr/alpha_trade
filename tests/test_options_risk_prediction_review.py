"""Display the whole sealed selection without authorizing another risk/order."""
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import event, text

from tests.test_risk_prediction_review import engine, fake_ui, DAY, replace_summary
from ihm.services.risk_prediction_review import load_risk_prediction_review
from service.options_directional import store
from service.options_directional.accounts import BINDING_PROTOCOL, consumer_directory


@pytest.fixture
def selection(engine, monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'ROOT', tmp_path)
    run_id = 'opt-' + 'a' * 32
    symbols = ['AAA', 'FUN']
    report = store.seal(run_id, dict(run_id=run_id, status='COMPLETED',
        trade_date=str(DAY), account_id='default', cutoff_utc='2026-10-16T21:00:00+00:00',
        batch_id='oracle', symbol_source='universe-file:test.txt', capital_preset_key='capital_2001_5000',
        config={'max_age_hours':72}, selected=symbols, rows=[
            dict(symbol=s, oracle_rank=i+1, oracle_score=.9-i*.1, combined_score=.8,
                 selected=True) for i,s in enumerate(symbols)]),
        {'prices':[dict(symbol=s, date=str(DAY), close=10+i) for i,s in enumerate(symbols)]})
    archived = dict(run_id='risk-one', options_filter_run_id=run_id, account_id='default',
                    trade_date=str(DAY), run_mode='paper', dry_run=False)
    folder = consumer_directory(run_id)
    store.write_new(folder/'risk_summary.json', archived)
    store.write_new(folder/'risk_binding.json', dict(account_id='default', risk_run_id='risk-one',
        report_sha256=store.digest(report), summary_sha256=store.digest(archived)))
    replace_summary(engine, llm_filter_run_id=None, **archived, universe_run_id='universe-one')
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM portfolio_targets'))
        conn.execute(text("UPDATE risk_decisions SET decision='REJECTED', reason='optimizer: edge net manquant', approved_shares=0"))
        conn.execute(text('CREATE TABLE tradable_universe_runs (universe_run_id TEXT,snapshot_date DATE,status TEXT)'))
        conn.execute(text('CREATE TABLE tradable_universe_history (universe_run_id TEXT,symbol TEXT,is_tradable INTEGER,tradability_reason_code TEXT)'))
        conn.execute(text("INSERT INTO tradable_universe_runs VALUES ('universe-one','2026-10-16','completed')"))
        conn.execute(text("INSERT INTO tradable_universe_history VALUES ('universe-one','FUN',0,'earnings_blackout')"))
    return run_id, folder


def review(engine, **kwargs):
    return load_risk_prediction_review(engine, trade_date=DAY, risk_run_id='risk-one', **kwargs)


def test_whole_selection_in_original_order_including_pre_sizing_exclusion(engine, selection):
    result = review(engine)
    assert result['options_filter_run_id'] == selection[0]
    assert result['decision_count'] == 1 and result['target_count'] == 0
    assert [r['Symbole'] for r in result['rows']] == ['AAA', 'FUN']
    evaluated, absent = result['rows']
    assert evaluated['Motif risque'] == 'optimizer: edge net manquant'
    assert absent['Décision risque'] == 'Exclu avant sizing'
    assert 'earnings_blackout' in absent['Motif risque']
    assert absent['Quantité validée'] is None and not absent['Cible publiée']
    assert evaluated['Score options (volume + OI)'] == .8
    assert evaluated['Dernier prix ($)'] == 10
    assert evaluated['Nom de l’entreprise'] == 'Example Corp'
    assert 'Avis LLM' not in evaluated


def test_archive_display_does_not_relax_trading_expiry(engine, selection):
    assert len(review(engine)['rows']) == 2
    with pytest.raises(ValueError, match='périmé'):
        store.qualified(selection[0], trade_date=DAY, now=datetime(2026,11,1,tzinfo=timezone.utc))


@pytest.mark.parametrize('problem', ['seal', 'risk_id', 'account', 'date', 'summary_hash'])
def test_invalid_or_wrong_account_binding_never_uses_another_run(engine, selection, problem):
    _, folder = selection
    if problem == 'seal':
        (folder/'inputs.json').write_text('{}', encoding='utf-8')
    elif problem == 'summary_hash':
        (folder/'risk_summary.json').write_text('{}', encoding='utf-8')
    else:
        file = folder/'risk_binding.json'
        binding = json.loads(file.read_text(encoding='utf-8'))
        if problem == 'risk_id': binding['risk_run_id'] = 'wrong'
        if problem == 'account': binding['account_id'] = 'test1'
        file.write_text(store.dumps(binding), encoding='utf-8')
        if problem == 'date': replace_summary(engine, trade_date='2026-10-15')
    with pytest.raises(ValueError):
        review(engine)


def test_secondary_account_has_separate_binding_and_risk(engine, selection):
    from database.run_business_summaries import _build_summary_table
    run_id, _ = selection
    report = store.sealed_report(run_id)
    folder = consumer_directory(run_id, 'test1', create=True)
    archived = dict(run_id='risk-test1', options_filter_run_id=run_id, account_id='test1',
                    trade_date=str(DAY), run_mode='paper', dry_run=False)
    store.write_new(folder/'risk_summary.json', archived)
    store.write_new(folder/'risk_binding.json', dict(account_id='test1', risk_run_id='risk-test1',
        binding_protocol=BINDING_PROTOCOL, report_sha256=store.digest(report),
        summary_sha256=store.digest(archived)))
    with engine.begin() as conn:
        conn.execute(_build_summary_table('run_summaries').insert().values(
            summary_run_id='risk-test1', entity_run_id='risk-test1', step_key='risk_management',
            run_kind='step', account_id='test1', trade_date=DAY, status='completed',
            summary_json=store.dumps(archived)))
    result = load_risk_prediction_review(engine, trade_date=DAY, risk_run_id='risk-test1',account_id='test1')
    assert len(result['rows']) == 2 and result['decision_count'] == 0
    assert all(r['Décision risque'] == 'Aucune décision enregistrée' for r in result['rows'])


def test_display_only_reads_and_does_not_change_claims(engine, selection):
    _, folder = selection
    store.write_new(folder/'risk.claim.json', {'consumed':True})
    before = {p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
    statements = []
    event.listen(engine,'before_cursor_execute',lambda c,cu,sql,p,ctx,many:statements.append(sql))
    review(engine)
    assert not any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER','DROP')) for s in statements)
    assert before == {p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}


def test_pipeline_table_shows_all_selected_symbols_and_options_labels(engine, selection, fake_ui, monkeypatch):
    pipeline, calls = fake_ui
    monkeypatch.setattr(pipeline, '_load_risk_prediction_review_cached', lambda **kw:review(engine))
    records = [dict(step_key='risk_management',account_id='default',executed_at='2026-10-17T08:00',
                    run_summary={'run_id':'risk-one'})]
    pipeline._render_risk_prediction_review(pipeline.PipelineLaunchOptions(llm_filter_enabled=False),records)
    frame = calls['dataframe'][0]
    assert list(frame['Symbole']) == ['AAA','FUN']
    assert 'Score options (volume + OI)' in frame.columns
    assert not any('Confiance' in name for name in frame.columns)
    assert any(selection[0] in text for text in calls['caption'])
    assert any('Scores Oracle/options' in text for text in calls['caption'])
