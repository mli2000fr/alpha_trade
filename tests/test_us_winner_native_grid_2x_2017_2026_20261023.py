from dataclasses import asdict
import pandas as pd
import pytest
from scripts.research import us_winner_native_grid_2x_2017_2026_20261023 as lever


def test_only_gross_ceiling_changes_in_native_risk_configuration():
    p=dict(reference_config=lever.grid.base.read(lever.grid.REFERENCE))
    rule=lever.grid.profiles()[0]
    a=lever.ORIGINAL_CONFIG(p,2017,rule);b=lever.configuration_2x(p,2017,rule)
    before,after=asdict(a.risk_config),asdict(b.risk_config)
    assert {k for k in before if before[k]!=after[k]}=={'max_gross_exposure'}
    assert b.risk_config.max_gross_exposure==2
    assert b.risk_config.risk_per_trade_pct==a.risk_config.risk_per_trade_pct
    assert b.exec_config.winner_pyramiding==a.exec_config.winner_pyramiding
    assert b.exec_config.leverage==a.exec_config.leverage
    assert b.cost_round_trip_bps==a.cost_round_trip_bps==16
    assert b.initial_equity==a.initial_equity==4000


def test_native_margin_capacity_is_not_limited_to_cash():
    p=dict(reference_config=lever.grid.base.read(lever.grid.REFERENCE))
    cfg=lever.configuration_2x(p,2017,lever.grid.profiles()[0])
    engine=lever.grid.base.BacktestEngine(cfg)
    assert engine._resolve_daily_leverage_state(4000).effective_leverage==2
    capacity=engine._resolve_available_entry_budget(constraints=cfg.trading_constraints,
        settled_cash=-2000,current_equity=4000,current_gross_notional=6000)
    assert capacity==2000
    assert engine._resolve_daily_leverage_state(1500).effective_leverage==1


def test_observed_exposure_is_not_the_configured_two():
    f=pd.DataFrame(dict(equity=[4000.,4000.],gross=[2000.,6000.]))
    m=lever.exposure_metrics(f)
    assert m['maximum_gross_equity_ratio']==1.5
    assert m['fraction_bars_above_1x']==.5
    assert m['average_borrowed_capital']==1000
    assert m['maximum_borrowed_capital']==2000
    with pytest.raises(ValueError):lever.exposure_metrics(pd.DataFrame(dict(equity=[0.],gross=[1.])))


def test_process_local_adapter_restores_sealed_module():
    before={k:getattr(lever.grid,k) for k in ['prepare','snapshot','configuration','worker','metrics','load_year','aggregate']}
    with pytest.raises(RuntimeError):
        with lever.adapter():
            assert lever.grid.configuration is lever.configuration_2x
            assert lever.grid.worker is lever.leveraged_worker
            raise RuntimeError('test restoration')
    assert all(getattr(lever.grid,k) is v for k,v in before.items())
