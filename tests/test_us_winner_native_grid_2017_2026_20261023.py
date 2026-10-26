import pandas as pd
from scripts.research.us_winner_native_grid_2017_2026_20261023 import profiles,bounds,configuration,qualify_cohort,base,REFERENCE


def test_frozen_grid_includes_recent_profiles_and_all_horizons():
    p=profiles()
    assert len(p)==300 and len({x['name'] for x in p})==300
    assert {x['horizon_sessions'] for x in p}=={5,10,15,20}
    assert {'SL3_TR3_H10_TP7','SL3_TR3_H10_TP15','SL7_TR15_H20_TPOFF'} <= {x['name'] for x in p}
    assert all('side' not in x for x in p)


def test_partial_year_bounds_and_no_2016_pnl():
    assert tuple(map(str,bounds(2017)))==('2017-06-02','2017-12-31')
    assert tuple(map(str,bounds(2026)))==('2026-01-01','2026-09-30')


def test_native_config_preserves_risk_half_and_sizing_reserve():
    old=base.read(REFERENCE);p=dict(reference_config=old)
    rule=next(x for x in profiles() if x['name']=='SL3_TR3_H10_TP15')
    cfg=configuration(p,2017,rule)
    ref=base.engine_config(old,2025)
    assert cfg.risk_config==ref.risk_config
    assert cfg.exec_config.leverage==ref.exec_config.leverage
    assert cfg.exec_config.winner_pyramiding.initial_position_fraction==.5
    assert not cfg.exec_config.winner_pyramiding.reinforcement_enabled
    assert cfg.exec_config.winner_pyramiding.entry_valid_sessions==20
    assert cfg.exec_config.winner_pyramiding.cost_reserve_bps_per_leg==25
    assert cfg.cost_round_trip_bps==16 and cfg.initial_equity==4000
    assert cfg.risk_config.max_gross_exposure==1
    assert cfg.risk_config.max_portfolio_drawdown_pct==.15


def test_common_cohort_no_reranking_or_replacement_when_prices_missing():
    days=[pd.Timestamp('2025-01-02').date(),pd.Timestamp('2025-01-03').date()]
    f=pd.DataFrame(dict(date=[pd.Timestamp(days[0])]*2,symbol=['AA','BB'],rank=[1,2]))
    out=qualify_cohort(f,{('AA',d):object() for d in days},pd.DataFrame(),{'AA':'X','BB':'X'},days)
    assert list(out['rank'])==[1,2] and list(out.selected)==[True,False]
    assert out.coverage_reason.iloc[1]=='COMMON_MAX_WAIT_HOLD_SIP_WINDOW_MISSING'


def test_actions_are_reserved_on_the_same_common_window():
    days=[pd.Timestamp('2025-01-02').date(),pd.Timestamp('2025-01-03').date()]
    f=pd.DataFrame(dict(date=[pd.Timestamp(days[0])],symbol=['AA'],rank=[1]))
    actions=pd.DataFrame(dict(symbol=['AA'],ex_date=[pd.Timestamp(days[1])]))
    out=qualify_cohort(f,{('AA',d):object() for d in days},actions,{'AA':'X'},days)
    assert not out.selected.iloc[0]
    assert out.coverage_reason.iloc[0]=='CORPORATE_ACTION_LIFECYCLE_RESERVED'
