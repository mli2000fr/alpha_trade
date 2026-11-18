from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from backtesting.risk_overlay import RegimeFilterConfig
from scripts.research.us_q051_b_sl10_vol20_regime_20261117 import protected_configuration,protected_run


def test_configuration_changes_only_entry_regime():
    cfg=SimpleNamespace(risk_overlay=SimpleNamespace(regime_filter=RegimeFilterConfig()),
        risk_config={'risk_per_trade_pct':.0125,'gross':1},winner={'SL':.05,'horizon':10})
    risk=cfg.risk_config.copy();winner=cfg.winner.copy()
    actual=protected_configuration(lambda *a,**k:cfg)('reference','case')
    assert actual is cfg
    assert asdict(actual.risk_overlay.regime_filter)==dict(enabled=True,sma_window=200,bear_threshold=-.02)
    assert actual.risk_config==risk and actual.winner==winner


def test_actual_callbacks_forwarded_and_receipts_saved_in_case(tmp_path):
    policy=SimpleNamespace(receipts=[{'native_quantity':10,'final_quantity':6}])
    gate=SimpleNamespace(receipts=[{'entry_allowed':False}]);close=pd.DataFrame({'SPY':[100.]})
    seen={};engine=object();result=object()
    def native(self,**kwargs):
        assert self is engine;seen.update(kwargs);return result
    with patch('backtesting.winner_portfolio_budget.replay_protections',return_value=(policy,gate)) as build:
        actual=protected_run(native,tmp_path)(engine,close=close,signals_df='unchanged')
    assert actual is result and seen['signals_df']=='unchanged'
    assert seen['winner_entry_risk_policy'] is policy and seen['winner_selection_source'] is gate
    build.assert_called_once_with(close,daily_entry=True,target=.20,lookback=60,regime=True,sma_window=200,bear_threshold=-.02)
    assert pd.read_csv(tmp_path/'portfolio-risk-decisions.csv').final_quantity.tolist()==[6]
    assert pd.read_csv(tmp_path/'regime-decisions.csv').entry_allowed.tolist()==[False]


@pytest.mark.parametrize('name',['winner_entry_risk_policy','winner_selection_source'])
def test_double_policy_cannot_silently_replace_existing_gate(tmp_path,name):
    with pytest.raises(ValueError,match='double protection'):
        protected_run(lambda *a,**k:None,tmp_path)(object(),close=None,**{name:object()})
