"""Step 10 archived top-ten display: SQLite and fake UI, no provider/broker."""
from datetime import date, datetime, timedelta
import json

import pytest
from sqlalchemy import create_engine, event, text

from ihm.services.llm_prediction_review import add_company_names, load_prediction_review, review_rows
from service.llm_directional.repository import metadata, runs, assessments, dumps


DAY = date(2026, 10, 16)
START = datetime(2026, 10, 17, 12)
SCOPE = dict(trade_date=DAY, batch_id='oracle-test', symbol_source='universe-file:test.txt',
             account_id='default', capital_preset_key='capital_2001_5000')


def candidates(n=12):
    return [dict(symbol=f'S{i:02}', oracle_rank=i, oracle_score=1 - i / 100,
        trade_date=DAY.isoformat(), prices_through_decision_date=[
            dict(date='2026-10-15', close=10), dict(date='2026-10-16', close=11.1256)])
        for i in range(1, n+1)]


def item(symbol='S01', decision='LONG', confidence=.9, **kw):
    return dict(dict(symbol=symbol, status='VALID', selected=True,
        assessment_json=dumps(dict(decision=decision, confidence=confidence, eligible=True))), **kw)


def annotated(row, **values):
    parsed = json.loads(row['assessment_json'])
    parsed.update(values)
    return dict(row, assessment_json=dumps(parsed))


def test_long_permission_blocker_is_explained_without_hiding_opinion():
    row=annotated(item(selected=False),eligible=False,selection_blockers=['long_not_allowed'],direction_score=9)
    view=review_rows(candidates(1),[row],run_status='COMPLETED',config={'allow_long':False})[0]
    assert view['Avis LLM']=='LONG' and view['Score directionnel LLM (/10)']==9
    assert not view['Retenu par le filtre']
    assert 'LONG non autorisé' in view['Motif de non-sélection LLM']


@pytest.fixture
def engine():
    engine = create_engine('sqlite:///:memory:')
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE stock_metadata (symbol TEXT PRIMARY KEY,company_name TEXT)'))
        conn.execute(text("INSERT INTO stock_metadata VALUES ('S01','Example Company'),('S02',NULL),('S03','   ')"))
    return engine


def archive(engine, run_id='llm-one', *, scope=None, status='COMPLETED',
            started_at=START, research=False, provider='openai', rows=None):
    scope = dict(SCOPE, **(scope or {}))
    snapshot = dict(symbol_source=scope['symbol_source'], capital_preset_key=scope['capital_preset_key'],
                    candidates=list(reversed(candidates())), research_only=research)
    with engine.begin() as conn:
        conn.execute(runs.insert().values(run_id=run_id, trade_date=scope['trade_date'],
            batch_id=scope['batch_id'], account_id=scope['account_id'], status=status,
            started_at=started_at, completed_at=started_at+timedelta(minutes=2) if status!='RUNNING' else None,
            config_json=dumps(dict(provider=provider, model='gpt-archived', deepseek_model='deepseek-archived')),
            input_json=dumps(snapshot), input_sha256='a'*64, protocol_version='test'))
        for row in rows or []:
            rank = int(row['symbol'][1:])
            conn.execute(assessments.insert().values(run_id=run_id, oracle_rank=rank,
                oracle_score=1-rank/100, observed_at=START, request_json='{}', **row))


def test_top10_is_score_order_not_confidence_or_selected_order():
    result = review_rows(list(reversed(candidates())), [item(confidence=.51, selected=False),
        item('S02', 'SHORT', .99), item('S03', 'ABSTAIN', .7, selected=False)], run_status='COMPLETED')
    assert [r['Symbole'] for r in result] == [f'S{i:02}' for i in range(1,11)]
    assert result[0]['Confiance LLM (%)'] == 51
    assert result[0]['Avis LLM'] == 'LONG' and not result[0]['Retenu par le filtre']
    assert result[1]['Avis LLM'] == 'SHORT'
    assert result[2]['Avis LLM'] == 'NEUTRE / ABSTENTION'
    assert result[3]['Confiance LLM (%)'] is None
    assert result[0]['Dernier prix ($)'] == 11.1256 and result[0]['Date du prix'] == DAY


def test_last_archived_close_respects_date_not_array_order_or_future_price():
    row = candidates(1)[0]
    row['prices_through_decision_date'] = [dict(date='2026-10-15', close=10),
        dict(date='2026-10-19', close=999), dict(date='2026-10-16', close=11.25)]
    result = review_rows([row], [], run_status='COMPLETED', trade_date=DAY)[0]
    assert result['Dernier prix ($)'] == 11.25 and result['Date du prix'] == DAY


@pytest.mark.parametrize('price', [None, 0, -1, True, 'invalid', float('nan'), float('inf')])
def test_invalid_prices_are_not_displayed_as_real_prices(price):
    row = candidates(1)[0]
    row['prices_through_decision_date'] = [dict(date=DAY.isoformat(), close=price)]
    result = review_rows([row], [], run_status='COMPLETED')[0]
    assert result['Dernier prix ($)'] is None and result['Date du prix'] is None


def test_old_archives_without_price_remain_displayable():
    row = candidates(1)[0]
    row.pop('prices_through_decision_date')
    result = review_rows([row], [], run_status='COMPLETED')[0]
    assert result['Symbole'] == 'S01' and result['Dernier prix ($)'] is None


def test_price_date_stays_visible_if_only_older_close_was_supplied():
    row = candidates(1)[0]
    row['prices_through_decision_date'] = [dict(date='2026-10-15', close=10)]
    result = review_rows([row], [], run_status='COMPLETED')[0]
    assert result['Dernier prix ($)'] == 10 and result['Date du prix'] == date(2026,10,15)


def test_run_date_is_the_price_cutoff_even_if_candidate_has_a_future_date():
    row = candidates(1)[0]
    row['trade_date'] = '2026-10-19'
    row['prices_through_decision_date'].append(dict(date='2026-10-19', close=999))
    result = review_rows([row], [], run_status='COMPLETED', trade_date=DAY)[0]
    assert result['Dernier prix ($)'] == 11.1256 and result['Date du prix'] == DAY


def test_pending_error_and_abstention_are_never_confused():
    result = review_rows(candidates(4), [item(status='FAILED', assessment_json=None),
        item('S02', status='RECEIVED', assessment_json=None),
        item('S03', 'ABSTAIN', .8, selected=False)], run_status='RUNNING')
    assert [r['Avis LLM'] for r in result] == ['Erreur technique', 'En attente de validation',
        'NEUTRE / ABSTENTION', 'En attente']
    assert all(not r['Retenu par le filtre'] for r in result)
    assert result[0]['Confiance LLM (%)'] is None
    assert 'Erreur technique' in result[0]['Motif de non-sélection']
    assert 'validation en attente' in result[1]['Motif de non-sélection']
    assert 'Abstention du LLM' in result[2]['Motif de non-sélection']
    assert 'Analyse globale en cours' in result[3]['Motif de non-sélection']


def test_fun_like_short_explains_untraceable_source_not_low_confidence():
    row = annotated(item(decision='SHORT', confidence=.74, selected=False),
        eligible=False, selection_blockers=['excluded_untraceable_sources'], fresh_source_count=2)
    result = review_rows(candidates(1), [row], run_status='COMPLETED',
        config=dict(min_confidence=.5, min_sources=2, allow_short=True))
    assert result[0]['Avis LLM'] == 'SHORT' and not result[0]['Retenu par le filtre']
    reason = result[0]['Motif de non-sélection']
    assert 'non traçable' in reason and 'Confiance' not in reason and 'non autorisé' not in reason


def test_all_archived_blockers_are_translated_with_archived_thresholds():
    row = annotated(item(decision='SHORT', confidence=.746, selected=False), eligible=False,
        selection_blockers=['insufficient_fresh_sources', 'confidence_below_threshold', 'short_not_allowed'],
        fresh_source_count=1)
    result = review_rows(candidates(1), [row], run_status='COMPLETED',
        config=dict(min_confidence=.75, min_sources=2))
    reason = result[0]['Motif de non-sélection']
    assert 'insuffisantes (1/2)' in reason and '74.6 % < 75 %' in reason
    assert 'SHORT non autorisé' in reason


def test_valid_but_not_selected_explains_cap_using_full_not_displayed_top10():
    rows = [item('S01', confidence=.9, selected=False), item('S12', confidence=.99)]
    result = review_rows(candidates(12), rows, run_status='COMPLETED',
        config=dict(max_selected=1), selected_symbols=['S12'])
    assert len(result) == 10
    assert 'hors des 1 titres retenus' in result[0]['Motif de non-sélection']
    assert 'classement par confiance LLM' in result[0]['Motif de non-sélection']


def test_selected_title_has_no_rejection_reason():
    result = review_rows(candidates(1), [item()], run_status='COMPLETED')
    assert result[0]['Motif de non-sélection'] == '—'


def test_zero_cap_is_explicit_not_a_qualification_failure():
    result = review_rows(candidates(1), [item(selected=False)], run_status='COMPLETED',
        config=dict(max_selected=0), selected_symbols=[])
    assert 'fixé à 0' in result[0]['Motif de non-sélection']


def test_do_not_invent_a_cap_explanation_when_archive_is_inconsistent():
    result = review_rows(candidates(2), [item(selected=False), item('S02', confidence=.8)],
        run_status='COMPLETED', config=dict(max_selected=1), selected_symbols=['S02'])
    assert 'motif non renseigné' in result[0]['Motif de non-sélection']
    assert 'hors des' not in result[0]['Motif de non-sélection']


def test_failed_overall_analysis_does_not_misreport_cap_exclusion():
    result = review_rows(candidates(1), [item(selected=False)], run_status='FAILED',
        config=dict(max_selected=0), selected_symbols=[])
    assert 'Analyse globale échouée' in result[0]['Motif de non-sélection']
    assert 'fixé à 0' not in result[0]['Motif de non-sélection']


def test_old_eligible_false_archive_without_reason_stays_explicitly_unknown():
    result = review_rows(candidates(1), [annotated(item(selected=False), eligible=False)], run_status='COMPLETED')
    assert 'non admissible : motif non renseigné' in result[0]['Motif de non-sélection']


@pytest.mark.parametrize('confidence', [None, True, float('nan'), float('inf'), -1, 1.1])
def test_invalid_confidence_is_not_a_probability_or_valid_abstention(confidence):
    result = review_rows(candidates(1), [item(assessment_json=json.dumps(
        dict(decision='LONG', confidence=confidence)))], run_status='COMPLETED')
    assert result[0]['Avis LLM'] == 'Erreur technique'
    assert result[0]['Confiance LLM (%)'] is None


def test_malformed_parsed_response_does_not_hide_other_rows():
    result = review_rows(candidates(2), [item(assessment_json='{'), item('S02')], run_status='COMPLETED')
    assert result[0]['Avis LLM'] == 'Erreur technique' and result[1]['Avis LLM'] == 'LONG'


def test_latest_failed_attempt_not_old_success(engine):
    archive(engine, rows=[item()])
    archive(engine, 'llm-failed', status='FAILED', started_at=START+timedelta(hours=1), rows=[item()])
    review = load_prediction_review(engine, **SCOPE)
    assert review['run_id'] == 'llm-failed' and review['status'] == 'FAILED'
    assert not any(r['Retenu par le filtre'] for r in review['rows'])


@pytest.mark.parametrize('override', [dict(trade_date=date(2026,10,15)), dict(batch_id='another'),
    dict(account_id='test1'), dict(symbol_source='universe-file:another.txt'),
    dict(capital_preset_key='another')])
def test_no_mixing_dates_models_accounts_universes_or_presets(engine, override):
    archive(engine, scope=override)
    assert load_prediction_review(engine, **SCOPE) is None


def test_research_retry_is_not_paper_analysis(engine):
    archive(engine)
    archive(engine, 'llm-research', research=True, started_at=START+timedelta(hours=1))
    assert load_prediction_review(engine, **SCOPE)['run_id'] == 'llm-one'


def test_archived_provider_and_model_not_current_config(engine):
    archive(engine, provider='deepseek', rows=[item()])
    review = load_prediction_review(engine, **SCOPE)
    assert review['provider_label'] == 'DeepSeek' and review['model'] == 'deepseek-archived'


def test_archived_top20_default_view_not_truncated_to_ten_and_explicit_limit_still_works(engine):
    archive(engine)
    with engine.begin() as conn:
        row=conn.execute(runs.select().where(runs.c.run_id=='llm-one')).mappings().one()
        snapshot=json.loads(row['input_json']);snapshot['candidates']=candidates(20)
        config=json.loads(row['config_json']);config.update(oracle_top_n=20,max_selected=5)
        from service.llm_directional.repository import digest
        conn.execute(runs.update().where(runs.c.run_id=='llm-one').values(
            config_json=dumps(config),input_json=dumps(snapshot),input_sha256=digest(snapshot)))
    review=load_prediction_review(engine,**SCOPE)
    assert review['oracle_top_n']==20 and review['max_selected']==5
    assert len(review['rows'])==20
    assert [r['Symbole'] for r in review['rows']]==[f'S{i:02}' for i in range(1,21)]
    assert len(load_prediction_review(engine,**SCOPE,limit=7)['rows'])==7


def test_legacy_archive_without_n_keeps_top10_despite_factory_default20(engine):
    from service.llm_directional.config import FilterConfig
    assert FilterConfig().oracle_top_n==20
    archive(engine)
    review=load_prediction_review(engine,**SCOPE)
    assert review['oracle_top_n']==10 and len(review['rows'])==10


def test_company_names_use_metadata_keep_order_and_missing_symbols(engine):
    archive(engine, rows=[item()])
    rows = load_prediction_review(engine, **SCOPE)['rows']
    assert rows[0]['Nom de l’entreprise'] == 'Example Company'
    assert all(rows[i]['Nom de l’entreprise'] is None for i in (1,2,3))
    assert [r['Symbole'] for r in rows] == [f'S{i:02}' for i in range(1,11)]
    assert list(rows[0])[1:3] == ['Symbole', 'Nom de l’entreprise']


def test_company_name_is_current_label_not_an_archived_issuer_claim(engine):
    archive(engine)
    assert load_prediction_review(engine, **SCOPE)['rows'][0]['Nom de l’entreprise'] == 'Example Company'
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_metadata SET company_name='New Company Name' WHERE symbol='S01'"))
    old_rows = [dict(Symbole='S01', **{'Nom de l’entreprise':'Old label'})]
    assert add_company_names(engine, old_rows)[0]['Nom de l’entreprise'] == 'New Company Name'
    assert old_rows[0]['Nom de l’entreprise'] == 'Old label'
    assert load_prediction_review(engine, **SCOPE)['rows'][0]['Nom de l’entreprise'] == 'New Company Name'


def test_view_uses_only_selects_and_does_not_require_current_oracle_predictions(engine):
    archive(engine, rows=[item(), item('S02', 'SHORT', .8)])
    statements = []
    event.listen(engine, 'before_cursor_execute', lambda conn,cursor,statement,params,ctx,many: statements.append(statement))
    review = load_prediction_review(engine, **SCOPE)
    assert len(review['rows']) == 10 and all(s.lstrip().upper().startswith('SELECT') for s in statements)
    assert not any('response_json' in s or 'request_json' in s or 'oracle_extreme_predictions' in s for s in statements)


def test_fewer_than_ten_does_not_invent_candidates():
    assert len(review_rows(candidates(2), [], run_status='COMPLETED')) == 2


@pytest.fixture
def fake_ui(monkeypatch):
    from ihm.pages import pipeline
    calls = dict(caption=[], info=[], warning=[], dataframe=[])
    monkeypatch.setattr(pipeline.st, 'session_state', {})
    monkeypatch.setattr(pipeline.st, 'markdown', lambda *a,**k:None)
    for kind in calls:
        monkeypatch.setattr(pipeline.st, kind, lambda value,*a,_kind=kind,**kw:calls[_kind].append(value))
    monkeypatch.setattr(pipeline,'render_prediction_review_table',lambda frame,**kw:calls['dataframe'].append(frame))
    import common.us_signal_date
    monkeypatch.setattr(common.us_signal_date, 'resolve_us_signal_date', lambda *a,**k:DAY)
    return pipeline, calls


def test_ui_displays_archive_with_dynamic_label_and_non_calibrated_notice(engine, fake_ui, monkeypatch):
    pipeline, calls = fake_ui
    archive(engine, provider='deepseek', rows=[item()])
    review = load_prediction_review(engine, **SCOPE)
    scopes = []
    def load(**scope):
        scopes.append(scope)
        return review
    monkeypatch.setattr(pipeline, '_load_prediction_review_cached', load)
    opts = pipeline.PipelineLaunchOptions(ml_predict_batch_id='oracle-test',
        ml_predict_symbol_source=SCOPE['symbol_source'], trade_date='2026-10-17')
    pipeline._render_ml_predict_review(opts)
    assert scopes == [SCOPE]
    frame = calls['dataframe'][0]
    assert frame.iloc[0]['Symbole'] == 'S01' and 'Avis DeepSeek' in frame.columns
    assert frame.iloc[0]['Confiance historique DeepSeek (%)'] == 90
    assert 'Motif de non-sélection' in frame.columns
    assert frame.iloc[0]['Dernier prix ($)'] == 11.1256
    assert frame.iloc[0]['Date du prix'] == DAY
    assert frame.iloc[0]['Nom de l’entreprise'] == 'Example Company'
    assert any('subjective non calibrée' in msg and 'Lecture seule' in msg for msg in calls['caption'])
    assert any('llm-one' in msg and 'DeepSeek / deepseek-archived' in msg for msg in calls['caption'])


def test_ui_new_score_column_and_archived_strict_thresholds(engine,fake_ui,monkeypatch):
    pipeline,calls=fake_ui
    archive(engine,rows=[annotated(item(),direction_score=9)])
    review=load_prediction_review(engine,**SCOPE)
    review.update(scoring_mode='direction_1_10',score_thresholds={'long_score_threshold':8,'short_score_threshold':3})
    monkeypatch.setattr(pipeline,'_load_prediction_review_cached',lambda **kw:review)
    pipeline._render_ml_predict_review(pipeline.PipelineLaunchOptions(ml_predict_batch_id='oracle-test'))
    frame=calls['dataframe'][0]
    assert frame.iloc[0]['Score GPT (/10)']==9
    assert not any('Confiance' in name for name in frame.columns)
    assert any('LONG > 8, SHORT < 3' in message for message in calls['caption'])


def test_ui_displays_all_twenty_candidates_from_archived_n(engine,fake_ui,monkeypatch):
    pipeline,calls=fake_ui
    archive(engine)
    review=load_prediction_review(engine,**SCOPE)
    review.update(oracle_top_n=20,candidate_count=20,rows=review_rows(candidates(20),[],run_status='COMPLETED',limit=20))
    monkeypatch.setattr(pipeline,'_load_prediction_review_cached',lambda **kw:review)
    pipeline._render_ml_predict_review(pipeline.PipelineLaunchOptions(ml_predict_batch_id='oracle-test'))
    assert len(calls['dataframe'][0])==20
    assert any('TOP 20 Oracle' in text for text in calls['caption'])


def test_ui_read_error_never_exposes_secrets_or_prevents_predict(fake_ui, monkeypatch):
    pipeline, calls = fake_ui
    def load(**kw):
        raise RuntimeError('private-connection-token')
    monkeypatch.setattr(pipeline, '_load_prediction_review_cached', load)
    pipeline._render_ml_predict_review(pipeline.PipelineLaunchOptions(ml_predict_batch_id='oracle-test'))
    assert calls['warning'] and not calls['dataframe']
    assert 'private-connection-token' not in str(calls)


def test_ui_no_matching_archive_shows_explanation(fake_ui, monkeypatch):
    pipeline, calls = fake_ui
    monkeypatch.setattr(pipeline, '_load_prediction_review_cached', lambda **kw:None)
    pipeline._render_ml_predict_review(pipeline.PipelineLaunchOptions(ml_predict_batch_id='oracle-test'))
    assert any('Aucune analyse' in msg for msg in calls['info']) and not calls['dataframe']
