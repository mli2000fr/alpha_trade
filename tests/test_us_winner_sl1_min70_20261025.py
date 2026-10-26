from dataclasses import asdict

import pytest

from scripts.research.us_winner_sl1_min70_20261025 import actual_sl1,sl1_policy,archived_config_equal


def test_persisted_configuration_compares_dates_in_json_form_without_ignoring_changes():
    import json
    from dataclasses import replace
    from tests.test_us_winner_min70_4000_20261025 import fixture
    cfg=fixture();persisted=json.loads(json.dumps(asdict(cfg),default=str))
    assert archived_config_equal(cfg,persisted)
    assert not archived_config_equal(replace(cfg,initial_equity=5000.),persisted)


def test_only_actual_stop_changes_and_wrapper_restores():
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from tests.test_us_winner_min70_4000_20261025 import fixture
    study=repair.study;cfg=fixture();original=study.profile_policy
    before=original(cfg.exec_config,study.REFERENCE)
    with sl1_policy(study):
        changed=study.profile_policy(cfg.exec_config,study.REFERENCE)
        assert changed.stop_loss_pct==.01
        a,b=asdict(before),asdict(changed);b['stop_loss_pct']=.05
        assert a==b
        with pytest.raises(ValueError):study.profile_policy(cfg.exec_config,'OTHER')
    assert study.profile_policy is original
    with pytest.raises(ValueError):actual_sl1(changed)


def test_sl1_resize_never_expands_historical_admission_quantity():
    from datetime import date
    from execution_engine.models import ExecutionTarget
    from tests.test_us_winner_min70_4000_20261025 import fixture
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    study=repair.study;cfg=fixture()
    target=ExecutionTarget('r',date(2020,1,2),'AAA',50,10.,.125,'S',1.,'test',None,
        risk_budget_dollars=50.,side='long')
    policy=actual_sl1(study.profile_policy(cfg.exec_config,study.REFERENCE))
    got=study.resize_target(target,cfg.exec_config,policy)
    assert got.target_shares==50 and got.target_weight==.125
    assert got.risk_budget_dollars==50.


def test_real_native_runtime_books_one_percent_stop_not_outer_three_percent():
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from tests.test_us_winner_monthly_selector_20261024 import replay_fixture
    from backtesting.simulator import BacktestEngine
    study=repair.study;cfg,kwargs=replay_fixture()
    original_source=kwargs['intraday_source']
    def source(day,symbols):
        frame=original_source(day,symbols)
        if not frame.empty and day==cfg.start_date:
            # After two breakout closes and the actual fill, breach SL1 but not SL5.
            frame.loc[frame.index>=5,'low']=100.5
        return frame
    kwargs['intraday_source']=source
    with sl1_policy(study),study.capacity.corrected_runtime(),repair.campaign_adapter(
            cfg.exec_config,lambda _d:study.REFERENCE) as metadata:
        result=BacktestEngine(cfg).run(**kwargs)
    assert result.trade_events_df.event.eq('BUY_FILL').sum()==1
    assert len(result.closed_trades_df)==1
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_price==pytest.approx(round(trade.entry_price*.99,2))
    assert trade.exit_reason=='STOP'
    filled=[m for m in metadata.values() if m.get('first_fill_at')]
    assert len(filled)==1 and filled[0]['policy']['stop_loss_pct']==.01
