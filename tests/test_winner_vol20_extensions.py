from dataclasses import asdict
import pandas as pd

from scripts.research.us_winner_vol20_extensions_20261109 import CASES,select_oracle_only,shared


def test_no_per_symbol_means_all_oracle_candidates_in_original_amplitude_order():
    frame=pd.DataFrame({'date':pd.to_datetime(['2025-01-02']*4),'symbol':['A','B','C','D'],
        'proba_extreme':[.5,.9,.8,.7],'long_probability':[.99,.01,.03,.04],
        'long_auc':[.99,.2,.3,.4],'selected':[True,False,False,False]})
    chosen=select_oracle_only(frame,3)
    assert chosen.symbol.tolist()==['B','C','D']
    assert chosen['rank'].tolist()==[1,2,3] and chosen.side.eq('long').all()
    assert chosen.selected.all()
    frame['long_probability']=0.;frame['long_auc']=0.
    pd.testing.assert_frame_equal(chosen[['symbol','rank']],select_oracle_only(frame,3)[['symbol','rank']])


def test_five_variants_keep_the_requested_risk_profiles_and_same_exit_policy():
    from tests.test_winner_continuous_q051_q088 import reference
    ref=reference()
    assert len(CASES)==5
    for name,case in CASES.items():
        cfg=shared.configuration(ref,case)
        assert cfg.winner_daily_entry_enabled and cfg.exec_config.leverage.max_leverage==2.
        assert cfg.risk_config.max_gross_exposure==case['gross']
        assert cfg.risk_config.risk_per_trade_pct==.0125 and cfg.risk_config.max_position_weight==.2
        assert cfg.winner_drawdown_controller_enabled==case['controller']
        assert cfg.risk_config.force_close_on_breaker==case['controller']
        assert cfg.exec_config.winner_pyramiding.stop_loss_pct==.05
        assert cfg.exec_config.winner_pyramiding.horizon_sessions==10
        assert not cfg.exec_config.winner_pyramiding.reinforcement_enabled
        if 'NO_PER' in name:
            assert not case['per_symbol'] and case['score'] is None and case['auc'] is None
        if name.startswith('Q088'):
            assert case['controller'] and case['pool']==.2 and case['gross']==2.
        else:assert not case['controller'] and case['pool']==.1
