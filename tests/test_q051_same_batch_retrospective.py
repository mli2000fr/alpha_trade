from datetime import date
import pandas as pd

from scripts.research.us_q051_same_batch_retrospective_20261114 import latest_heads,rank_retrospective,replay_config,MODE


def test_weights_are_fixed_latest_heads_not_fabricated_annual_models():
    rows=[dict(symbol='A',side='long',year=2025,available='2024-12-31'),
          dict(symbol='A',side='long',year=2027,available='2026-10-15'),
          dict(symbol='A',side='short',year=2028,available='2027-12-31')]
    assert latest_heads(dict(models=rows))=={'A':rows[1]}


def test_research_ranking_keeps_future_disclosure_and_never_refills_failed_top_five():
    frame=pd.DataFrame(dict(date=pd.Timestamp('2021-01-04'),symbol=[f'S{i:02}' for i in range(200)],
        proba_extreme=[1-i/200 for i in range(200)],long_probability=[.9-i/1000 for i in range(200)],
        long_auc=[.4]+[.7]*199,long_model_available_date='2026-10-15'))
    result=rank_retrospective(frame,200)
    assert result[result.selected].symbol.tolist()==['S01','S02','S03','S04']
    assert result[result.selected].long_model_available_date.eq('2026-10-15').all()
    assert result.evaluation_mode.eq(MODE).all()
    assert not result[result.selected].symbol.isin(['S05','S20']).any()


def test_native_q051_rules_unchanged_despite_authorized_model_lookahead():
    cfg=replay_config(date(2021,1,1),date(2026,11,13))
    r=cfg.risk_config;p=cfg.exec_config.winner_pyramiding
    assert r.risk_per_trade_pct==.0125 and r.max_position_weight==.2 and r.max_gross_exposure==1.
    assert r.min_position_notional==50. and not r.enable_factor_model and not r.correlation_check_enabled
    assert cfg.winner_daily_entry_enabled and not cfg.winner_drawdown_controller_enabled
    assert cfg.risk_overlay.regime_filter.enabled and cfg.risk_overlay.regime_filter.sma_window==200
    assert cfg.risk_overlay.regime_filter.bear_threshold==-.02
    assert p.stop_loss_pct==.05 and p.horizon_sessions==10 and p.confirmation_bars==0
    assert p.take_profit_pct is None and p.trailing_stop_pct is None and not p.reinforcement_enabled
