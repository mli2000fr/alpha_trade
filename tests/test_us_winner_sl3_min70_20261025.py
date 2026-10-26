from dataclasses import asdict

import pytest

from scripts.research import us_winner_sl3_min70_20261025 as treatment


def test_only_stop_changes_and_shared_runner_restores():
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from tests.test_us_winner_min70_4000_20261025 import fixture
    study=repair.study;cfg=fixture()
    names=['ROOT','ARM','DOC','TEST','prepare','actual_sl1']
    originals={n:getattr(treatment.runner,n) for n in names}
    policy=study.profile_policy(cfg.exec_config,study.REFERENCE)
    after=treatment.actual_sl3(policy);a,b=asdict(policy),asdict(after)
    b['stop_loss_pct']=.05
    assert a==b and after.stop_loss_pct==.03
    with treatment.installed():
        assert treatment.runner.ROOT==treatment.ROOT
        assert treatment.runner.actual_sl1==treatment.actual_sl3
        with treatment.runner.sl1_policy(study):assert study.profile_policy(cfg.exec_config,study.REFERENCE).stop_loss_pct==.03
    assert originals=={n:getattr(treatment.runner,n) for n in names}
    with pytest.raises(ValueError):treatment.actual_sl3(after)


def test_native_three_percent_stop_is_really_used():
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from tests.test_us_winner_monthly_selector_20261024 import replay_fixture
    from backtesting.simulator import BacktestEngine
    study=repair.study;cfg,kwargs=replay_fixture();original=kwargs['intraday_source']
    def source(day,symbols):
        frame=original(day,symbols)
        if not frame.empty and day==cfg.start_date:frame.loc[frame.index>=5,'low']=98.8
        return frame
    kwargs['intraday_source']=source
    with treatment.installed(),treatment.runner.sl1_policy(study),study.capacity.corrected_runtime(),repair.campaign_adapter(
            cfg.exec_config,lambda _d:study.REFERENCE) as metadata:
        result=BacktestEngine(cfg).run(**kwargs)
    assert result.trade_events_df.event.eq('BUY_FILL').sum()==1
    assert len(result.closed_trades_df)==1
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_reason=='STOP'
    assert trade.exit_price==pytest.approx(round(trade.entry_price*.97,2))
    assert next(m for m in metadata.values() if m.get('first_fill_at'))['policy']['stop_loss_pct']==.03


def test_sl3_resize_keeps_admission_quantity_cap():
    from datetime import date
    from execution_engine.models import ExecutionTarget
    from tests.test_us_winner_min70_4000_20261025 import fixture
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    cfg=fixture();study=repair.study
    target=ExecutionTarget('r',date(2020,1,2),'AAA',50,10.,.125,'S',1.,'test',None,risk_budget_dollars=50.,side='long')
    policy=treatment.actual_sl3(study.profile_policy(cfg.exec_config,study.REFERENCE))
    got=study.resize_target(target,cfg.exec_config,policy)
    assert got.target_shares<=50 and got.target_weight<=.125
    assert got.risk_budget_dollars==50.
