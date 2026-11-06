"""Offline launch, provider precedence, archived risk and UI contracts."""
from dataclasses import replace
from datetime import UTC, date, datetime
import json

import pandas as pd
import pytest
from sqlalchemy import create_engine, event

from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command
from backtesting.winner_campaign_replay import build_parser


@pytest.fixture(autouse=True)
def no_actual_batch_comment_queries(monkeypatch):
    monkeypatch.setattr('ihm.services.queries.get_ml_training_batch_comments',lambda:{})


def options(**changes):
    return replace(BacktestRunOptions(start='2025-01-02', end='2025-03-31',
        winner_enabled=True, oracle_batch_id='fixture-h10', output_dir='artifacts/fixture-new',
        winner_research_assumptions=True, ml_mode='off', equity=4000.), **changes)


def test_ui_command_is_consumed_by_real_replay_parser():
    command = build_backtesting_command('run',options(winner_top_n=50, winner_max_leverage=2.,
        winner_factor_model=False, winner_cost_per_leg_bps=8., max_positions=12, margin_interest_rate=.065,
        winner_options_filter_enabled=True))
    assert command[3]=='backtesting.winner_campaign_replay'
    args = build_parser().parse_args(command[4:])
    assert (args.oracle_batch_id,args.top_n,args.initial_equity,args.max_positions)==('fixture-h10',50,4000.,12)
    assert args.max_leverage==2. and args.factor_model is False
    assert args.cost_per_leg_bps==8. and args.margin_interest_annual==.065
    assert args.options_filter is True
    assert args.research_assumptions and args.symbol_source.endswith('univers_filtred_tradable.txt')
    assert '--phase2-mode' not in command and '--no-winner-pyramiding' not in command


def test_legacy_mode_explicitly_disables_yaml_winner_without_mutating_config():
    from backtesting.cli._impl import _build_parser
    command = build_backtesting_command('run',BacktestRunOptions(start='2025-01-01'))
    assert command[3:5]==['backtesting','run'] and '--no-winner-pyramiding' in command
    assert _build_parser().parse_args(command[4:]).winner_pyramiding is False


def test_winner_requires_explicit_assumptions_and_model():
    for changes in [dict(winner_research_assumptions=False),dict(oracle_batch_id=None)]:
        with pytest.raises(ValueError):
            build_backtesting_command('run', options(**changes))


@pytest.mark.parametrize('active',[True,False])
def test_explicit_per_symbol_choice_reaches_replay(active):
    command=build_backtesting_command('run',options(winner_top_n=20,winner_per_symbol_long_enabled=active))
    assert ('--per-symbol-long' if active else '--no-per-symbol-long') in command
    args=build_parser().parse_args(command[4:])
    assert args.per_symbol_long is active and args.top_n==20


@pytest.mark.parametrize('longs,shorts',[(True,False),(False,True),(True,True)])
def test_configurable_branch_directions_and_counts_reach_replay(longs,shorts):
    command=build_backtesting_command('run',options(winner_top_n=12,
        winner_per_symbol_long_enabled=True,winner_per_symbol_allow_long=longs,
        winner_per_symbol_allow_short=shorts,winner_per_symbol_top_long=3,winner_per_symbol_top_short=2))
    args=build_parser().parse_args(command[4:])
    assert (args.top_n,args.per_symbol_longs,args.per_symbol_shorts,
            args.per_symbol_top_long,args.per_symbol_top_short)==(12,longs,shorts,3,2)


def test_settings_override_frozen_numbers_without_rewriting_training_contract():
    from copy import deepcopy
    from backtesting.winner_campaign_replay import per_symbol_settings
    command=build_backtesting_command('run',options(winner_top_n=12,
        winner_per_symbol_long_enabled=True,winner_per_symbol_allow_long=False,
        winner_per_symbol_allow_short=True,winner_per_symbol_top_long=3,winner_per_symbol_top_short=2))
    args=build_parser().parse_args(command[4:])
    protocol=dict(training_config=dict(oracle_path_directional_enabled=True),
        universe=list(range(32)),directional_contract=dict(oracle_top_n=20,selected_n=5))
    before=deepcopy(protocol)
    assert per_symbol_settings(protocol,args).snapshot()==dict(oracle_top_n=12,
        allow_long=False,allow_short=True,long_top_n=3,short_top_n=2,min_long_probability=None,min_long_auc=None)
    assert protocol==before
    args.per_symbol_top_short=0
    with pytest.raises(ValueError,match='entier positif'):per_symbol_settings(protocol,args)
    args.per_symbol_top_short=2;args.top_n=33
    with pytest.raises(ValueError,match='univers du modèle'):per_symbol_settings(protocol,args)
    args.per_symbol_long=False
    assert per_symbol_settings(protocol,args) is None


def test_short_execution_is_rejected_before_database_or_provider_calls(tmp_path,monkeypatch):
    from backtesting.winner_campaign_replay import run
    contract=dict(training_config=dict(oracle_path_directional_enabled=True),
        universe=list(range(32)),directional_contract=dict(oracle_top_n=20,selected_n=5))
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:(tmp_path,contract,None,{}))
    def unexpected(*a,**kw):raise AssertionError('No SQL or provider call allowed for unsupported SHORT replay')
    monkeypatch.setattr('database.connection.get_sqlalchemy_engine',unexpected)
    command=build_backtesting_command('run',options(output_dir=str(tmp_path/'new'),
        winner_per_symbol_long_enabled=True,winner_per_symbol_allow_short=True))
    args=build_parser().parse_args(command[4:])
    with pytest.raises(ValueError,match='exécution SHORT non raccordée'):run(args)
    progress=json.loads((tmp_path/'new/progress.json').read_text(encoding='utf-8'))
    assert progress['status']=='FAILED' and 'SHORT' in progress['error']


def test_old_commands_keep_bundle_auto_detection():
    from modelFactory.oracle_path.directional import use_long_selection
    protocol={'training_config':{'oracle_path_directional_enabled':True}}
    assert use_long_selection(protocol,None)
    assert not use_long_selection(protocol,False)
    assert not use_long_selection({},None)
    with pytest.raises(ValueError,match='ne contient pas'):
        use_long_selection({},True)


@pytest.mark.parametrize('symbols',[None,[],['AAA','AAA'],['aaa'],['AAA',None]])
def test_invalid_frozen_universe_is_rejected(symbols):
    from backtesting.winner_universe import universe_from_model
    with pytest.raises(ValueError):universe_from_model({'universe':symbols})


@pytest.mark.parametrize('chosen',['universe-file:large.txt','universe-file:missing.txt'])
def test_form_automatically_ignores_old_file_choice_and_locks_universe(monkeypatch,chosen):
    from streamlit.testing.v1 import AppTest
    def forbidden(*unused):raise AssertionError('The model universe must not depend on a mutable file')
    monkeypatch.setattr('common.universe_files.load_universe_file_symbols',forbidden)
    def app():
        import streamlit as st
        from ihm.components.winner_backtest import render_universe_selection
        st.session_state['universe_result']=render_universe_selection(
            {'universe':['AAA','BBB']},'fixture')
    at=AppTest.from_function(app)
    at.session_state['bt_winner_universe_fixture']=chosen
    at.run(timeout=30)
    assert not at.exception and not at.error
    assert at.session_state['universe_result']=='model-universe'
    field=at.text_input(key='bt_winner_universe_auto_fixture')
    assert field.disabled and '2 titres' in field.value
    assert not at.button


def test_universe_follows_selected_batch_including_oracle_only():
    from streamlit.testing.v1 import AppTest
    def app():
        import streamlit as st
        from ihm.components.winner_backtest import render_universe_selection
        batch=st.selectbox('Batch',['two','five'],key='model_choice')
        symbols=['AAA','BBB'] if batch=='two' else ['CCC','DDD','EEE','FFF','GGG']
        st.session_state['universe_result']=render_universe_selection({'universe':symbols},batch)
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception and not at.error
    assert '2 titres' in at.text_input[0].value and at.text_input[0].disabled
    at.selectbox(key='model_choice').select('five').run(timeout=30)
    assert not at.exception and '5 titres' in at.text_input[0].value and at.text_input[0].disabled
    assert at.session_state['universe_result']=='model-universe'


def test_configurable_selection_widgets_and_clamping(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from ihm.components import winner_backtest as ui
    bid='fixture'
    folder=tmp_path/bid/'oracle_path';folder.mkdir(parents=True)
    (folder/'report.json').write_text(json.dumps(dict(status='completed',serving_ready=True,horizon=10,directional_models=64)))
    contract=dict(horizon=10,universe=[f'S{i:02}' for i in range(32)],
        training_config=dict(oracle_path_directional_enabled=True),
        directional_contract=dict(oracle_top_n=20,selected_n=5))
    monkeypatch.setattr(ui,'MODEL_ROOT',tmp_path)
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:(folder,contract,None,{}))
    monkeypatch.setattr('modelFactory.oracle_path.directional.load_manifest',lambda *a:({},'hash'))
    def app():
        import streamlit as st
        from ihm.components.winner_backtest import render_model_selection
        st.session_state['choice']=render_model_selection()[-1]
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception
    assert at.checkbox(key=f'bt_winner_per_symbol_long_{bid}').label=='per-symbol'
    assert at.number_input(key=f'bt_per_symbol_top_short_{bid}').disabled
    at.number_input(key=f'bt_per_symbol_pool_{bid}').set_value(12)
    at.checkbox(key=f'bt_per_symbol_allow_short_{bid}').check()
    at.number_input(key=f'bt_per_symbol_top_long_{bid}').set_value(3)
    at.number_input(key=f'bt_per_symbol_top_short_{bid}').set_value(2)
    at.run(timeout=30)
    assert not at.exception
    assert at.session_state['choice']==dict(oracle_top_n=12,allow_long=True,allow_short=True,long_top_n=3,short_top_n=2,
        min_long_probability=.6,min_long_auc=.6)
    at.number_input(key=f'bt_per_symbol_pool_{bid}').set_value(1).run(timeout=30)
    assert not at.exception
    assert at.session_state['choice']['long_top_n']==at.session_state['choice']['short_top_n']==1
    at.checkbox(key=f'bt_per_symbol_allow_long_{bid}').uncheck().run(timeout=30)
    assert not at.exception and not at.session_state['choice']['allow_long']
    at.checkbox(key=f'bt_per_symbol_allow_short_{bid}').uncheck().run(timeout=30)
    assert not at.exception and any('Cocher LONG ou SHORT' in e.value for e in at.error)


@pytest.mark.parametrize('size,percent,expected',[(1790,10.,179),(32,10.,4),(1,.1,1),(20,100.,20)])
def test_percentage_pool_uses_frozen_universe_and_reaches_replay(size,percent,expected):
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''import streamlit as st
from ihm.components.winner_backtest import render_oracle_pool_size
st.session_state['pool_result']=render_oracle_pool_size(st.session_state['size'],20,key='pool',label='Top N Oracle')
''')
    app.session_state['size']=size
    app.run(timeout=30)
    assert not app.exception and app.session_state['pool_result']==min(20,size)
    app.radio(key='pool_mode').set_value('Pourcentage de l’univers').run(timeout=30)
    app.number_input(key='pool_pct').set_value(percent).run(timeout=30)
    assert not app.exception and app.session_state['pool_result']==expected
    command=build_backtesting_command('run',options(winner_top_n=app.session_state['pool_result']))
    assert build_parser().parse_args(command[4:]).top_n==expected


def test_bundle_form_2022_top20_to_top5_and_command(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from risk_management.config import RiskConfig
    from execution_engine.config import LeverageConfig
    from ihm.components import winner_backtest as ui
    bid='model-factory-20261104153014-49a6da'
    folder=tmp_path/bid/'oracle_path';folder.mkdir(parents=True)
    (folder/'report.json').write_text(json.dumps(dict(status='completed',serving_ready=True,horizon=10,directional_models=120)))
    contract=dict(horizon=10,universe=[f'S{i:02}' for i in range(32)],
        training_config=dict(oracle_path_directional_enabled=True,data=dict(training_end_date='2021-12-31')),
        directional_contract=dict(oracle_top_n=20,selected_n=5))
    folds={'2021-01-05':{'metrics':dict(fold_start='2021-01-05',train_available_max='2020-07-06',val_available_max='2021-01-04')}}
    monkeypatch.setattr(ui,'MODEL_ROOT',tmp_path)
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:(folder,contract,None,folds))
    monkeypatch.setattr('modelFactory.oracle_path.directional.load_manifest',lambda *a:(dict(models=[dict(side='long',year=2021),dict(side='long',year=2022)]),'hash'))
    monkeypatch.setattr('risk_management.config.load_risk_config',lambda **kw:RiskConfig(account_equity=kw['equity'],enable_factor_model=False))
    monkeypatch.setattr('execution_engine.config.load_leverage_config_from_yaml',lambda:LeverageConfig(enabled=True,mode='regt_swing',max_leverage=2.))
    def app():
        import streamlit as st
        from dataclasses import asdict
        from ihm.components.winner_backtest import render_winner_backtest
        st.session_state['result']=asdict(render_winner_backtest())
    at=AppTest.from_function(app)
    at.session_state['bt_winner_account']='cash'
    at.session_state['bt_winner_leverage_margin']=1.
    at.run(timeout=30)
    assert not at.exception
    result=at.session_state['result']
    assert result['oracle_batch_id']==bid and result['winner_per_symbol_long_enabled'] is True
    assert result['winner_per_symbol_min_long_probability']==.6
    assert result['winner_per_symbol_top_long']==10
    assert result['start']=='2022-01-01' and result['end']=='2022-12-31'
    assert result['winner_top_n']==20 and result['winner_symbol_source']=='model-universe'
    assert result['winner_options_filter_enabled'] is False
    assert result['account_type']=='margin' and result['winner_max_leverage']==2.
    parsed=build_parser().parse_args(build_backtesting_command('run',BacktestRunOptions(**result))[4:])
    assert parsed.account_type=='margin' and parsed.max_leverage==2.
    assert parsed.symbol_source=='model-universe'
    assert parsed.per_symbol_min_long_probability==.6
    at.number_input(key=f'bt_per_symbol_min_long_probability_{bid}').set_value(.7).run(timeout=30)
    assert not at.exception and at.session_state['result']['winner_per_symbol_min_long_probability']==.7
    assert at.session_state['result']['winner_per_symbol_min_long_auc']==.6
    assert at.checkbox(key=f'bt_per_symbol_auc_enabled_{bid}').value
    at.checkbox(key=f'bt_per_symbol_auc_enabled_{bid}').check().run(timeout=30)
    at.number_input(key=f'bt_per_symbol_min_long_auc_{bid}').set_value(.65).run(timeout=30)
    assert not at.exception and at.session_state['result']['winner_per_symbol_min_long_auc']==.65
    with_auc=build_parser().parse_args(build_backtesting_command('run',BacktestRunOptions(**at.session_state['result']))[4:])
    assert with_auc.per_symbol_min_long_auc==.65
    assert at.checkbox(key='bt_winner_options_filter').disabled
    assert '--per-symbol-long' in build_backtesting_command('run',BacktestRunOptions(**result))
    at.checkbox(key=f'bt_winner_per_symbol_long_{bid}').uncheck().run(timeout=30)
    assert not at.exception and at.session_state['result']['winner_per_symbol_long_enabled'] is False
    assert '--per-symbol-min-long-probability' not in build_backtesting_command('run',BacktestRunOptions(**at.session_state['result']))
    assert '--per-symbol-min-long-auc' not in build_backtesting_command('run',BacktestRunOptions(**at.session_state['result']))
    at.selectbox(key='bt_winner_leverage_margin').select(1.).run(timeout=30)
    assert not at.exception and at.session_state['result']['winner_max_leverage']==1.
    at.selectbox(key='bt_winner_account').select('cash').run(timeout=30)
    assert not at.exception and at.session_state['result']['account_type']=='cash'
    assert at.session_state['result']['winner_max_leverage']==1.


def test_daily_optout_restores_only_winner_specific_risk_fields(monkeypatch):
    from backtesting.cli._impl import _without_winner_risk_policy
    from risk_management.config import RiskConfig
    monkeypatch.setattr('common.config_loader.load_config',lambda:dict(
        winner_pyramiding=dict(enabled=True,stop_loss_pct=.05),risk_management={}))
    current=RiskConfig(account_equity=4000.,fixed_stop_pct=.05,disable_price_take_profit=True,
                       allow_fractional_shares=False,max_positions=7,max_daily_loss_pct=.02)
    standard=_without_winner_risk_policy(current,equity=4000.,preset_key=None,allow_fractional_shares=True)
    assert standard.fixed_stop_pct is None and standard.disable_price_take_profit is False
    assert standard.allow_fractional_shares is True
    assert standard.max_positions==7 and standard.max_daily_loss_pct==.02


def test_forged_past_sql_availability_cannot_serve_future_weights():
    from backtesting.winner_campaign_replay import validate_scores
    rows=pd.DataFrame([dict(trade_date='2025-01-02',symbol='AAA',proba_extreme=.9,
        fold_start='2024-01-01',lineage_fold_start='2024-01-01',model_available_date='2024-12-31',
        model_sha256='weights',feature_profile_sha256='profile',target_name='oracle_path_extreme10',target_horizon=10)])
    folds={'2024-01-01':dict(model_sha256='weights',metrics=dict(
        train_available_max='2025-02-01',val_available_max='2025-04-01'))}
    with pytest.raises(ValueError,match='non-causal'):
        validate_scores(rows,profile_hash='profile',folds=folds,expected_days=[date(2025,1,2)],top_n=1,horizon=10)
    folds['2024-01-01']['metrics']=dict(train_available_max='2024-12-30',val_available_max='2024-12-31')
    with pytest.raises(ValueError,match='Couverture Oracle insuffisante'):
        validate_scores(rows,profile_hash='profile',folds=folds,expected_days=[date(2025,1,2)],
                        top_n=1,horizon=10,universe_size=100,min_coverage=.9)


def test_new_year_requires_prior_year_signal_and_explains_j_plus_one():
    from backtesting.winner_campaign_replay import validate_scores
    rows=pd.DataFrame([dict(trade_date='2023-01-03',symbol='AAA',proba_extreme=.9,
        fold_start='2022-01-04',lineage_fold_start='2022-01-04',model_available_date='2021-12-31',
        model_sha256='weights',feature_profile_sha256='profile',target_name='oracle_path_extreme10',target_horizon=10)])
    folds={'2022-01-04':dict(model_sha256='weights',metrics=dict(
        train_available_max='2021-06-30',val_available_max='2021-12-31'))}
    with pytest.raises(ValueError,match='2022-12-30.*Dates de signal J'):
        validate_scores(rows,profile_hash='profile',folds=folds,
            expected_days=[date(2022,12,30),date(2023,1,3)],top_n=1,horizon=10)
    prior=rows.assign(trade_date='2022-12-30')
    assert len(validate_scores(pd.concat([prior,rows]),profile_hash='profile',folds=folds,
        expected_days=[date(2022,12,30),date(2023,1,3)],top_n=1,horizon=10))==2


def test_daily_whole_row_priority_and_invalid_preferred_not_replaced(monkeypatch):
    from backtesting.winner_data import daily_bars
    monkeypatch.setattr('common.daily_bar_sources.load_config',lambda:dict(
        market_data=dict(daily_bars_preferred_source='eodhd')))
    engine=create_engine('sqlite://')
    rows=[]
    for day in ('2025-01-02','2025-01-03'):
        for source,price in [('alpaca_sip',100.),('eodhd_eod',110.)]:
            rows.append(dict(date=day,symbol='AAA',open=price,high=price+1,low=price-1,
                close=price,volume=1000,is_filled=int(day=='2025-01-03' and source=='eodhd_eod'),
                data_source=source,data_adjustment='split'))
    pd.DataFrame(rows).to_sql('stock_bars_daily',engine,index=False)
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda conn,cursor,sql,*a:statements.append(sql))
    with engine.connect() as conn:
        result=daily_bars(conn,['AAA'],'2025-01-02','2025-01-03')
    assert result.close.tolist()==[110.] and result.data_source.tolist()==['eodhd_eod']
    assert all(s.lstrip().startswith('SELECT') for s in statements)


def test_factor_source_cannot_backdate_or_refresh_observations():
    from backtesting.winner_data import HistoricalFactorSource
    from risk_management.config import RiskConfig
    engine=create_engine('sqlite://')
    pd.DataFrame([dict(asof_date='2025-01-02',observed_at='2026-01-01',id=1)]).to_sql(
        'stock_risk_factor_inputs',engine,index=False)
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda conn,cursor,sql,*a:statements.append(sql))
    with engine.connect() as conn:
        source=HistoricalFactorSource(conn,pd.DataFrame())
        with pytest.raises(ValueError,match='Aucun snapshot'):
            source(date(2025,1,2),['AAA'],datetime(2025,1,3,15,tzinfo=UTC),RiskConfig(account_equity=4000.))
    assert source.receipts[0]['qualified'] is False
    assert all(s.lstrip().startswith('SELECT') for s in statements)


def test_real_form_default_policy_and_independent_dates(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from common.winner_pyramiding import WinnerPyramidingConfig
    from risk_management.config import RiskConfig
    from execution_engine.config import LeverageConfig
    monkeypatch.setattr('ihm.components.winner_backtest.load_winner_pyramiding_config',lambda:
        WinnerPyramidingConfig(enabled=True,horizon_sessions=10,stop_loss_pct=.05,trailing_stop_pct=None))
    monkeypatch.setattr('modelFactory.oracle_path.predict.load_contract',lambda *a:
        (None,{'horizon':10,'universe':['AAA']},None,{'2021-07-02':{'metrics':dict(fold_start='2021-07-02',
             train_available_max='2020-12-30',val_available_max='2021-07-01')}}))
    monkeypatch.setattr('risk_management.config.load_risk_config',lambda **kw:RiskConfig(
        account_equity=kw['equity'],enable_factor_model=True))
    monkeypatch.setattr('execution_engine.config.load_leverage_config_from_yaml',lambda:LeverageConfig(enabled=False))
    def app():
        from dataclasses import asdict
        import streamlit as st
        from ihm.components.winner_backtest import render_winner_backtest
        st.session_state['winner_options']=asdict(render_winner_backtest())
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception
    assert at.session_state['winner_options']['winner_enabled'] is True
    assert at.session_state['winner_options']['winner_options_filter_enabled'] is False
    assert at.session_state['winner_options']['winner_factor_market_cap_check'] is False
    assert at.session_state['winner_options']['winner_ignore_missing_intraday'] is False
    assert at.session_state['winner_options']['winner_factor_model'] is False
    assert at.session_state['winner_options']['winner_drawdown_controller_enabled'] is False
    assert at.session_state['winner_options']['winner_daily_entry_enabled'] is True
    at.checkbox(key='bt_winner_factors').check().run(timeout=30)
    at.checkbox(key='bt_winner_factor_cap').check().run(timeout=30)
    assert not at.exception and at.session_state['winner_options']['winner_factor_market_cap_check'] is True
    at.checkbox(key='bt_winner_options_filter').check().run(timeout=30)
    assert not at.exception and at.session_state['winner_options']['winner_options_filter_enabled'] is True
    assert at.session_state['winner_options']['winner_research_assumptions'] is True
    assert at.date_input[0].min==date(2021,7,6)  # NYSE closed July 5.
    at.checkbox(key='bt_winner_prudent_replay').uncheck().run(timeout=30)
    assert not at.exception and at.session_state['winner_options']['winner_research_assumptions'] is False
    assert at.session_state['winner_options']['winner_factor_model'] is True
