from dataclasses import asdict

import pandas as pd
import pytest

from scripts.research.us_winner_ui_grid_20261107 import cases,configuration,selection_settings,FrozenIntraday


def reference():
    from risk_management.config import RiskConfig
    from common.winner_pyramiding import WinnerPyramidingConfig
    from execution_engine.config import LeverageConfig
    return dict(arguments=dict(top_n=179,per_symbol_top_long=10,per_symbol_top_short=5,
        per_symbol_min_long_probability=.7,per_symbol_min_long_auc=.6,margin_interest_annual=.065),
        risk=asdict(RiskConfig(account_equity=4000.,force_close_on_breaker=False,enable_factor_model=False)),
        winner_policy=asdict(WinnerPyramidingConfig(enabled=True,initial_position_fraction=1.,
            confirmation_bars=0,horizon_sessions=10,trailing_stop_pct=None)),
        leverage=asdict(LeverageConfig(enabled=True,mode='regt_swing',max_leverage=2.)))


def test_grid_is_frozen_factorial_and_dedicated_reference():
    arms=cases()
    assert len(arms)==269 and len({a['name'] for a in arms})==269
    assert arms[0]['name']=='REFERENCE'
    factorial=[a for a in arms if a['family']=='FACTORIAL']
    assert len(factorial)==128
    for k in ('selection','risk','policy'):
        assert all(isinstance(a[k],dict) for a in arms)
    assert {a['selection']['min_long_probability'] for a in factorial}=={.6,.7}
    assert {a['controller'] for a in factorial}=={False,True}
    joint=[a for a in arms if a['family']=='JOINT_SELECTION_GRID']
    assert len(joint)==108
    assert {a['selection']['oracle_top_n'] for a in joint}=={90,179,358}
    assert {a['selection']['min_long_probability'] for a in joint}=={.55,.6,.65,.7}
    assert {a['selection']['min_long_auc'] for a in joint}=={None,.55,.6}
    assert {a['selection']['long_top_n'] for a in joint}=={5,10,20}


def test_every_variant_uses_valid_ui_settings_and_keeps_native_leverage():
    ref=reference()
    for arm in cases():
        cfg=configuration(ref,arm)
        settings=selection_settings(ref,arm)
        assert cfg.initial_equity==4000.
        assert cfg.exec_config.leverage.max_leverage==2.
        assert not cfg.risk_config.allow_fractional_shares
        assert cfg.winner_daily_entry_enabled==arm['daily']
        assert cfg.winner_drawdown_controller_enabled==arm['controller']
        assert cfg.risk_config.fixed_stop_pct==cfg.exec_config.winner_pyramiding.stop_loss_pct
        assert settings.allow_long and not settings.allow_short
        if arm['name']=='S_POSITIONS30':
            assert cfg.risk_config.max_positions==cfg.risk_config.max_long_positions==30
        if arm['controller']:
            assert cfg.risk_config.force_close_on_breaker and cfg.risk_config.force_close_pct==.5
    assert reference()==ref  # Original settings not mutated.


def test_frozen_source_never_refills_missing_symbols_or_queries_sql(tmp_path):
    folder=tmp_path/'inputs/intraday';folder.mkdir(parents=True)
    pd.DataFrame(dict(symbol=['A','B'],open=[10.,20.])).to_parquet(folder/'2025-01-02.parquet',index=False)
    source=FrozenIntraday(tmp_path)
    assert source('2025-01-02',['A']).symbol.tolist()==['A']
    assert source('2025-01-02',['C']).empty
    with pytest.raises(FileNotFoundError):source('2025-01-03',['A'])


def test_recommendations_reject_cash_tiny_samples_and_dominated_cases():
    from scripts.research.us_winner_ui_grid_review_20261107 import recommend
    frame=pd.DataFrame([
        dict(name='REFERENCE',return_pct=7.,max_drawdown_pct=-11.,closed_lot_trades=59),
        dict(name='CASH',return_pct=0.,max_drawdown_pct=0.,closed_lot_trades=0),
        dict(name='TINY',return_pct=999.,max_drawdown_pct=-1.,closed_lot_trades=2),
        dict(name='BALANCED',return_pct=30.,max_drawdown_pct=-10.,closed_lot_trades=70),
        dict(name='RETURN',return_pct=50.,max_drawdown_pct=-25.,closed_lot_trades=100),
        dict(name='LOW_DD',return_pct=8.,max_drawdown_pct=-4.,closed_lot_trades=50),
        dict(name='DOMINATED',return_pct=20.,max_drawdown_pct=-15.,closed_lot_trades=65),
    ])
    result=recommend(frame,7.)
    assert [c['name'] for c in result]==['BALANCED','RETURN','LOW_DD']


def test_partitioned_queries_preserve_all_symbols_and_do_not_duplicate():
    from scripts.research.us_winner_ui_grid_20261107 import partitioned_intraday
    seen=[]
    def source(day,symbols):
        seen.append(list(symbols))
        return pd.DataFrame(dict(symbol=symbols,timestamp=pd.Timestamp(day),open=1.))
    names=[f'S{i:03}' for i in range(254)]
    result=partitioned_intraday(source,'2025-01-02',names+names[:3])
    assert [len(group) for group in seen]==[100,100,54]
    assert result.symbol.tolist()==sorted(names)
