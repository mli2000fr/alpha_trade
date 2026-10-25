from dataclasses import asdict

from scripts.research.us_winner_top20_half_continuous_20261025 import half_staging_config, half_adapter


def test_staging_changes_only_fraction_and_leaves_outer_full():
    from execution_engine.config import ExecutionConfig
    from common.winner_pyramiding import WinnerPyramidingConfig
    config = ExecutionConfig(winner_pyramiding=WinnerPyramidingConfig(enabled=True,
        initial_position_fraction=1.,stop_loss_pct=.03,take_profit_pct=None,trailing_stop_pct=None))
    half = half_staging_config(config)
    before, after = asdict(config), asdict(half)
    assert before['winner_pyramiding']['initial_position_fraction'] == 1.
    assert after['winner_pyramiding']['initial_position_fraction'] == .5
    after['winner_pyramiding']['initial_position_fraction'] = 1.
    assert before == after


def test_native_half_is_applied_once_to_the_same_approval():
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from tests.test_us_winner_monthly_selector_20261024 import replay_fixture
    from backtesting.simulator import BacktestEngine
    results = []
    for fraction in [1., .5]:
        cfg, kwargs = replay_fixture()
        adapter = repair.campaign_adapter if fraction == 1. else lambda c,s: half_adapter(repair,c,s)
        with repair.study.capacity.corrected_runtime(), adapter(cfg.exec_config,lambda _d:repair.study.REFERENCE) as metadata:
            result = BacktestEngine(cfg).run(**kwargs)
        filled = [m for m in metadata.values() if m.get('first_fill_at')]
        assert len(filled) == 1
        assert filled[0]['policy']['initial_position_fraction'] == fraction
        events = result.trade_events_df
        buys = events[events.event.eq('BUY_FILL')]
        assert len(buys) == 1
        assert cfg.exec_config.winner_pyramiding.initial_position_fraction == 1.
        results.append((filled[0], buys.iloc[0]))
    full, half = results
    assert full[0]['admission_target'] == half[0]['admission_target']
    from execution_engine.models import ExecutionTarget
    from common.winner_pyramiding import initial_quantities, WinnerPyramidingConfig
    policy = WinnerPyramidingConfig(**half[0]['policy'])
    target = repair.study.resize_target(ExecutionTarget(**half[0]['admission_target']), cfg.exec_config, policy)
    approved_full, approved_half = initial_quantities(target.target_shares,target.entry_price,
        target.risk_budget_dollars,policy)
    assert approved_half == int(approved_full*.5)
    assert half[1].quantity == approved_half
    # Full may be clipped again at the actual higher opening fill price. Compare
    # HALF to its original approval, not floor(FULL's already clipped fill / 2).
    assert half[1].quantity <= full[1].quantity
    assert half[1].time == full[1].time and half[1].price == full[1].price
    a,b=full[0]['policy'].copy(),half[0]['policy'].copy()
    b['initial_position_fraction']=1.
    assert a==b
