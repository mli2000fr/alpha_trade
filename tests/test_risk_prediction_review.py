"""Exact read-only step-11 view; no provider, broker, sizing or orders."""
from datetime import date, datetime
import json

import pytest
from sqlalchemy import create_engine, event, text, update

from database.run_business_summaries import _build_summary_table
from ihm.services.risk_prediction_review import load_risk_prediction_review, risk_review_rows
from service.llm_directional.repository import metadata, runs, assessments, dumps

DAY = date(2026,10,16)


@pytest.fixture
def engine():
    engine = create_engine('sqlite:///:memory:')
    metadata.create_all(engine)
    summary_table = _build_summary_table('run_summaries')
    summary_table.create(engine)
    snapshot = dict(symbol_source='universe-file:test.txt', capital_preset_key='capital_2001_5000', candidates=[
        dict(symbol='AAA', oracle_rank=1, oracle_score=.9, trade_date=str(DAY),
             prices_through_decision_date=[dict(date=str(DAY), close=9.75)]),
        dict(symbol='FUN', oracle_rank=2, oracle_score=.8, trade_date=str(DAY),
             prices_through_decision_date=[dict(date=str(DAY), close=8.11)])])
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE stock_metadata (symbol TEXT PRIMARY KEY,company_name TEXT)'))
        conn.execute(text("INSERT INTO stock_metadata VALUES ('AAA','Example Corp'),('FUN','Six Flags Entertainment Corporation'),('HELD','Held Company')"))
        conn.execute(runs.insert().values(run_id='llm-one', trade_date=DAY, batch_id='oracle-one',
            account_id='default', status='COMPLETED', started_at=datetime(2026,10,17,18),
            config_json=dumps(dict(provider='openai', model='test', max_selected=1)),
            input_json=dumps(snapshot), input_sha256='x'*64, protocol_version='test',
            selected_json=dumps(['AAA']), risk_run_id='risk-one'))
        for symbol, rank, score, selected in [('AAA',1,.9,True),('FUN',2,.8,False)]:
            conn.execute(assessments.insert().values(run_id='llm-one', symbol=symbol, oracle_rank=rank,
                oracle_score=score, observed_at=datetime(2026,10,17,18), request_json='{}',
                status='VALID', selected=selected, assessment_json=dumps(dict(decision='LONG' if selected else 'SHORT',
                    confidence=.9, eligible=selected,
                    selection_blockers=[] if selected else ['excluded_untraceable_sources']))))
        # Match the deployed schema: optional side/reason_code absent on decisions.
        conn.execute(text('''CREATE TABLE risk_decisions (run_id TEXT,account_id TEXT,trade_date DATE,
            symbol TEXT,decision TEXT,reason TEXT,entry_price FLOAT,approved_shares FLOAT,
            price_asof_date DATE,target_notional FLOAT,stop_price_initial FLOAT,take_profit_price FLOAT)'''))
        conn.execute(text('''CREATE TABLE portfolio_targets (run_id TEXT,account_id TEXT,trade_date DATE,
            symbol TEXT,side TEXT,shares FLOAT,entry_price FLOAT,price_asof_date DATE,
            target_notional FLOAT,stop_price_initial FLOAT,take_profit_price FLOAT)'''))
        conn.execute(text("INSERT INTO risk_decisions VALUES ('risk-one','default','2026-10-16','AAA','ACCEPTED','OK',10,3,'2026-10-16',30,9,NULL)"))
        conn.execute(text("INSERT INTO portfolio_targets VALUES ('risk-one','default','2026-10-16','AAA','buy',3,10,'2026-10-16',30,9,NULL)"))
        conn.execute(summary_table.insert().values(summary_run_id='risk-one', entity_run_id='risk-one',
            step_key='risk_management', run_kind='step', account_id='default', trade_date=DAY, status='completed',
            summary_json=dumps(dict(run_id='risk-one', trade_date=str(DAY), llm_filter_run_id='llm-one',
                finished_at='2026-10-18T09:30:00', new_entry_data_rejections={}))))
    return engine


def load(engine, **kw):
    return load_risk_prediction_review(engine, trade_date=DAY, llm_run_id='llm-one', **kw)


def replace_summary(engine, **values):
    table = _build_summary_table('run_summaries')
    with engine.begin() as conn:
        parsed = json.loads(conn.execute(text("SELECT summary_json FROM run_summaries WHERE summary_run_id='risk-one'")).scalar_one())
        parsed.update(values)
        conn.execute(update(table).where(table.c.summary_run_id=='risk-one').values(summary_json=dumps(parsed)))


def test_bound_risk_and_llm_values_kept_distinct(engine):
    review = load(engine)
    assert review['run_id']=='risk-one' and review['llm_run_id']=='llm-one'
    assert review['status']=='COMPLETED' and review['target_count']==1
    assert [r['Symbole'] for r in review['rows']]==['AAA']
    a = review['rows'][0]
    assert a['Symbole']=='AAA' and a['Cible publiée'] and a['Décision risque']=='ACCEPTED'
    assert a['Sens cible']=='LONG' and a['Quantité validée']==3 and a['Montant cible ($)']==30
    assert a['Dernier prix ($)']==9.75 and a['Prix de référence risque ($)']==10
    assert a['SL initial ($)']==9 and a['TP prix ($)'] is None
    assert a['Nom de l’entreprise']=='Example Corp'
    assert 'Retenu par le filtre' not in a and 'Motif de non-sélection' not in a


def test_published_step10_selection_is_authoritative_not_assessment_flags(engine):
    with engine.begin() as conn:
        conn.execute(update(assessments).where(assessments.c.run_id=='llm-one').values(selected=True))
    assert [r['Symbole'] for r in load(engine)['rows']]==['AAA']


def test_no_step10_selection_means_no_rows_even_with_existing_targets(engine):
    with engine.begin() as conn:
        conn.execute(update(runs).where(runs.c.run_id=='llm-one').values(selected_json='[]'))
    review=load(engine)
    assert review['rows']==[] and review['target_count']==1


def test_selected_symbol_beyond_oracle_top10_stays_visible():
    base=[{'Rang Oracle':25,'Symbole':'SELECTED','Retenu par le filtre':True,
        'Motif de non-sélection':'—'}]
    result=risk_review_rows(base,[],[],status='COMPLETED',selected_symbols=['SELECTED'])
    assert [r['Symbole'] for r in result]==['SELECTED']
    assert result[0]['Décision risque']=='Aucune décision enregistrée'


def test_newer_other_risk_targets_are_never_substituted(engine):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO portfolio_targets VALUES ('risk-new','default','2026-10-16','WRONG','buy',99,10,'2026-10-16',990,9,NULL)"))
    assert 'WRONG' not in [r['Symbole'] for r in load(engine)['rows']]


def test_exact_analysis_is_not_replaced_by_newer_llm_attempt(engine):
    with engine.begin() as conn:
        old = dict(conn.execute(runs.select().where(runs.c.run_id=='llm-one')).mappings().one())
        old.update(run_id='llm-new', started_at=datetime(2026,10,18,20), risk_run_id='risk-new')
        conn.execute(runs.insert().values(**old))
    assert load(engine)['run_id']=='risk-one'


@pytest.mark.parametrize('scope', [dict(account_id='test1'),dict(trade_date=date(2026,10,15))])
def test_other_account_or_session_is_rejected(engine,scope):
    with pytest.raises(Exception):
        load_risk_prediction_review(engine, **dict(trade_date=DAY,llm_run_id='llm-one',**scope))


def test_explicit_risk_id_must_match_llm_link(engine):
    with pytest.raises(ValueError,match='Liaison exacte'):
        load(engine,risk_run_id='risk-other')


def test_summary_from_other_analysis_is_rejected(engine):
    replace_summary(engine,llm_filter_run_id='llm-other')
    with pytest.raises(ValueError,match='autre analyse'):
        load(engine)


def test_unbound_run_shows_waiting_never_old_targets(engine):
    with engine.begin() as conn:
        conn.execute(update(runs).where(runs.c.run_id=='llm-one').values(risk_run_id=None))
    review = load(engine)
    assert review['status']=='NON LIÉ' and not review['run_id']
    assert review['rows'][0]['Décision risque']=='En attente / non finalisé'
    assert not any(r['Cible publiée'] for r in review['rows'])


def test_failed_run_with_partial_target_not_reported_as_published(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE run_summaries SET status='failed'"))
    review = load(engine)
    assert review['rows'][0]['Quantité validée']==3 and not review['rows'][0]['Cible publiée']
    assert 'résultat partiel' in review['rows'][0]['Motif risque']


def test_recorded_rejection_reason_and_zero_quantity_remain_visible(engine):
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM portfolio_targets'))
        conn.execute(text("UPDATE risk_decisions SET decision='REJECTED',reason='sizing insuffisant',approved_shares=0,target_notional=0"))
    row=load(engine)['rows'][0]
    assert row['Décision risque']=='REJECTED' and row['Quantité validée']==0
    assert row['Motif risque']=='sizing insuffisant' and not row['Cible publiée']


def test_guard_rejection_before_sizing_has_own_reason(engine):
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM portfolio_targets'))
        conn.execute(text('DELETE FROM risk_decisions'))
    replace_summary(engine,new_entry_data_rejections={'AAA':'missing_J_bar'})
    row=load(engine)['rows'][0]
    assert row['Décision risque']=='Données d’entrée non qualifiées' and row['Motif risque']=='missing_J_bar'


def test_no_decision_does_not_invent_rejection_or_zero_quantity(engine):
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM portfolio_targets'))
        conn.execute(text('DELETE FROM risk_decisions'))
    row=load(engine)['rows'][0]
    assert row['Décision risque']=='Aucune décision enregistrée'
    assert row['Quantité validée'] is None and 'aucun motif individuel' in row['Motif risque']


def test_exact_archived_universe_explains_pre_sizing_exclusion(engine):
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM portfolio_targets'))
        conn.execute(text('DELETE FROM risk_decisions'))
        conn.execute(text('CREATE TABLE tradable_universe_runs (universe_run_id TEXT,snapshot_date DATE,status TEXT)'))
        conn.execute(text('CREATE TABLE tradable_universe_history (universe_run_id TEXT,symbol TEXT,is_tradable INTEGER,tradability_reason_code TEXT)'))
        conn.execute(text("INSERT INTO tradable_universe_runs VALUES ('universe-one','2026-10-16','completed')"))
        conn.execute(text("INSERT INTO tradable_universe_history VALUES ('universe-one','AAA',0,'spread_above_maximum')"))
    replace_summary(engine,universe_run_id='universe-one')
    row=load(engine)['rows'][0]
    assert row['Décision risque']=='Exclu avant sizing' and 'spread_above_maximum' in row['Motif risque']


def test_non_llm_risk_and_held_positions_are_displayed_without_fake_llm_advice(engine):
    replace_summary(engine,llm_filter_run_id=None)
    review=load_risk_prediction_review(engine,trade_date=DAY,risk_run_id='risk-one')
    row=review['rows'][0]
    assert row['Avis LLM']=='Sans filtre LLM' and row['Cible publiée']
    assert row['Score Oracle'] is None and row['Confiance LLM (%)'] is None
    assert row['Nom de l’entreprise']=='Example Corp'


def test_held_positions_not_selected_in_step10_are_hidden_not_deleted(engine):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO portfolio_targets VALUES ('risk-one','default','2026-10-16','HELD','sell',2,10,'2026-10-16',20,11,NULL)"))
    assert [r['Symbole'] for r in load(engine)['rows']]==['AAA']
    with engine.connect() as conn:
        assert conn.execute(text("SELECT shares FROM portfolio_targets WHERE symbol='HELD'")).scalar_one()==2


def test_only_read_statements_are_executed(engine):
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda c,cu,sql,p,ctx,many:statements.append(sql))
    load(engine)
    assert not any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','CREATE','ALTER','DROP')) for s in statements)


@pytest.fixture
def fake_ui(monkeypatch):
    from ihm.pages import pipeline
    calls=dict(markdown=[],caption=[],info=[],warning=[],dataframe=[])
    for kind in calls:
        monkeypatch.setattr(pipeline.st,kind,lambda value,*a,_kind=kind,**kw:calls[_kind].append(value))
    monkeypatch.setattr(pipeline,'render_prediction_review_table',lambda frame,**kw:calls['dataframe'].append(frame))
    import common.us_signal_date
    monkeypatch.setattr(common.us_signal_date,'resolve_us_signal_date',lambda *a,**kw:DAY)
    return pipeline,calls


def test_ui_uses_exact_handoff_and_shows_risk_columns(engine,fake_ui,monkeypatch):
    pipeline,calls=fake_ui
    scopes=[]
    def fetch(**scope):
        scopes.append(scope)
        return load(engine)
    monkeypatch.setattr(pipeline,'_load_risk_prediction_review_cached',fetch)
    pipeline._render_risk_prediction_review(pipeline.PipelineLaunchOptions(
        llm_filter_enabled=True,llm_filter_run_id='llm-one'),[])
    assert scopes==[dict(trade_date=DAY,account_id='default',llm_run_id='llm-one',risk_run_id=None)]
    frame=calls['dataframe'][0]
    assert 'Avis GPT' in frame.columns and 'Motif risque' in frame.columns
    assert frame.iloc[0]['Quantité validée']==3 and frame.iloc[0]['SL initial ($)']==9
    assert frame.iloc[0]['Nom de l’entreprise']=='Example Corp'
    assert list(frame['Symbole'])==['AAA']
    assert not {'Retenu par le filtre','Retenu par le filtre LLM','Motif de non-sélection',
        'Motif de non-sélection LLM'} & set(frame.columns)


def test_ui_risk_score_column_comes_from_exact_step10_selection(engine,fake_ui,monkeypatch):
    pipeline,calls=fake_ui
    review=load(engine)
    review['scoring_mode']='direction_1_10'
    for row in review['rows']:
        row['Score directionnel LLM (/10)']=9
    monkeypatch.setattr(pipeline,'_load_risk_prediction_review_cached',lambda **kw:review)
    pipeline._render_risk_prediction_review(pipeline.PipelineLaunchOptions(
        llm_filter_enabled=True,llm_filter_run_id='llm-one'),[])
    frame=calls['dataframe'][0]
    assert list(frame['Symbole'])==['AAA'] and frame.iloc[0]['Score GPT (/10)']==9
    assert not any('Confiance' in name for name in frame.columns)


def test_ui_without_exact_llm_link_does_not_query_latest(fake_ui,monkeypatch):
    pipeline,calls=fake_ui
    monkeypatch.setattr(pipeline,'_load_risk_prediction_review_cached',lambda **kw:pytest.fail('no latest lookup'))
    pipeline._render_risk_prediction_review(pipeline.PipelineLaunchOptions(llm_filter_enabled=True),[])
    assert calls['info'] and not calls['dataframe']


def test_ui_without_llm_uses_business_id_of_latest_attempt_for_this_account(engine,fake_ui,monkeypatch):
    pipeline,calls=fake_ui
    scopes=[]
    def fetch(**scope):
        scopes.append(scope)
        return load(engine)
    monkeypatch.setattr(pipeline,'_load_risk_prediction_review_cached',fetch)
    records=[dict(step_key='risk_management',account_id='default',executed_at='2026-10-18T09:00',
        run_summary=dict(run_id='risk-one',llm_filter_run_id='llm-one')),
        dict(step_key='risk_management',account_id='test1',executed_at='2026-10-18T10:00',
             run_summary=dict(run_id='risk-wrong-account'))]
    pipeline._render_risk_prediction_review(pipeline.PipelineLaunchOptions(llm_filter_enabled=False),records)
    assert scopes==[dict(trade_date=DAY,account_id='default',llm_run_id='llm-one',risk_run_id='risk-one')]
    assert calls['dataframe']


def test_ui_newer_failure_without_business_id_never_falls_back_to_old_success(fake_ui,monkeypatch):
    pipeline,calls=fake_ui
    monkeypatch.setattr(pipeline,'_load_risk_prediction_review_cached',lambda **kw:pytest.fail('no old success fallback'))
    records=[dict(step_key='risk_management',account_id='default',executed_at='2026-10-18T09:00',
        status='completed',run_summary=dict(run_id='risk-old')),
        dict(step_key='risk_management',account_id='default',executed_at='2026-10-18T10:00',
        status='failed')]
    pipeline._render_risk_prediction_review(pipeline.PipelineLaunchOptions(llm_filter_enabled=False),records)
    assert calls['info'] and not calls['dataframe']


def test_ui_read_error_does_not_expose_connection_details(fake_ui,monkeypatch):
    pipeline,calls=fake_ui
    def fetch(**kw):
        raise ValueError('secret-connection-detail')
    monkeypatch.setattr(pipeline,'_load_risk_prediction_review_cached',fetch)
    pipeline._render_risk_prediction_review(pipeline.PipelineLaunchOptions(
        llm_filter_enabled=True,llm_filter_run_id='llm-one'),[])
    assert calls['warning'] and 'secret-connection-detail' not in str(calls)
