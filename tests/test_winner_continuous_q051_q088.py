from dataclasses import asdict
from datetime import date,timedelta

import pandas as pd

from scripts.research.us_winner_continuous_q051_q088_20261108 import CASES,configuration,settings,supplemental_windows,normalize_ranking_dates


def reference():
    from risk_management.config import RiskConfig
    from common.winner_pyramiding import WinnerPyramidingConfig
    from execution_engine.config import LeverageConfig
    risk=RiskConfig(account_equity=4000.,risk_per_trade_pct=.0125,max_position_weight=.2,
        max_gross_exposure=2.,force_close_on_breaker=True,force_close_pct=.5,max_positions=20,
        correlation_check_enabled=False,sector_weight_limit_enabled=False,sector_ticker_limit_enabled=False,
        enable_factor_model=False)
    policy=WinnerPyramidingConfig(enabled=True,initial_position_fraction=1.,reinforcement_enabled=False,
        confirmation_bars=0,entry_valid_sessions=1,market_data_delay_seconds=0,stop_loss_pct=.05,
        take_profit_pct=None,trailing_stop_pct=None,horizon_sessions=10)
    return dict(risk=asdict(risk),winner_policy=asdict(policy),leverage=asdict(LeverageConfig(enabled=True,
        max_leverage=2.,dry_run_simulated_leverage=2.)),arguments=dict(margin_interest_annual=.065,cost_per_leg_bps=8.))


def test_all_requested_variants_have_exact_selection_and_separate_entry_caps():
    ref=reference()
    for name,case in CASES.items():
        cfg=configuration(ref,case);s=settings(case,1790)
        assert s.oracle_top_n==(179 if case['profile']=='Q051' else 358)
        assert s.long_top_n==(5 if case['profile']=='Q051' else 10)
        assert s.min_long_probability==s.min_long_auc==(.6 if name=='Q051_060' else .5)
        assert cfg.risk_config.max_gross_exposure==case['gross']
        assert cfg.exec_config.leverage.max_leverage==2.
        assert cfg.exec_config.simulated_margin_buying_power_multiplier==2.
        assert cfg.winner_drawdown_controller_enabled==case['controller']
        assert cfg.risk_config.force_close_on_breaker==case['controller']
        assert cfg.risk_config.risk_per_trade_pct==.0125 and cfg.risk_config.max_position_weight==.2
        assert not cfg.risk_config.enable_factor_model and not cfg.risk_config.correlation_check_enabled
        assert cfg.winner_daily_entry_enabled
        assert cfg.cost_round_trip_bps==16.
        assert cfg.exec_config.winner_pyramiding.stop_loss_pct==.05
        assert cfg.exec_config.winner_pyramiding.horizon_sessions==10
        assert cfg.exec_config.winner_pyramiding.trailing_stop_pct is None
        assert cfg.exec_config.winner_pyramiding.take_profit_pct is None
        assert cfg.start_date==date(2021,1,1) and cfg.end_date==date(2026,10,1)


def test_additional_price_inventory_spans_next_open_to_open11_without_screening_candidates():
    sessions=[date(2021,1,4)+timedelta(days=i) for i in range(14)]
    signals=pd.DataFrame([dict(trade_date=date(2020,12,31),symbol='NEW'),
        dict(trade_date=sessions[-2],symbol='LATE'),dict(trade_date=sessions[0],symbol='KNOWN')])
    windows=supplemental_windows([signals],sessions,{'KNOWN'})
    assert all('NEW' in windows[d] for d in sessions[:11])
    assert all('NEW' not in windows[d] for d in sessions[11:])
    assert windows[sessions[-1]]=={'LATE'}
    assert all('KNOWN' not in names for names in windows.values())


def test_csv_and_sql_fold_dates_can_be_archived_together_without_changing_dates(tmp_path):
    mixed=pd.DataFrame({'date':[date(2024,1,2),'2025-01-02'],
        'fold_start':['2023-07-01',date(2024,7,1)]})
    frame=normalize_ranking_dates(mixed)
    path=tmp_path/'annual.parquet';frame.to_parquet(path,index=False)
    saved=pd.read_parquet(path)
    assert saved.fold_start.dt.strftime('%Y-%m-%d').tolist()==['2023-07-01','2024-07-01']
    assert saved.date.dt.year.tolist()==[2024,2025]
