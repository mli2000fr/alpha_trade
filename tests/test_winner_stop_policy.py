from dataclasses import replace
from unittest.mock import Mock, MagicMock

import pandas as pd
import pytest

from risk_management.config import load_risk_config, RiskConfig
from risk_management.models import PriceInfo
from risk_management.position_sizer import PositionSizer


@pytest.mark.parametrize('enabled', [False, True])
def test_loader_uses_winner_stop_only_when_enabled(monkeypatch, enabled):
    monkeypatch.setattr('common.config_loader.load_config', lambda: dict(
        winner_pyramiding=dict(enabled=enabled, stop_loss_pct=.05), risk_management={}))
    cfg = load_risk_config(equity=1940.7, cli_overrides=dict(account_equity=1940.7,
        risk_per_trade_pct=.01, min_position_notional=50, allow_fractional_shares=False))
    assert cfg.fixed_stop_pct == (.05 if enabled else None)
    if enabled:
        assert cfg.stop_distance(100, 80) == 5
    else:
        assert cfg.stop_distance(100, 80) == 80*cfg.atr_stop_multiple_for()


@pytest.mark.parametrize('symbol,price,atr,qty', [
    ('BAND',53.11,4.439115,7), ('COHU',53.4,4.353515,7),
    ('UCTT',54.7,4.62375,7), ('SIMO',227.75,16.546125,1),
])
def test_whole_share_sizing_uses_five_percent_and_preserves_budget(symbol,price,atr,qty):
    cfg = RiskConfig(account_equity=1940.7, risk_per_trade_pct=.01,
        min_position_notional=50, fixed_stop_pct=.05, allow_fractional_shares=False)
    sizer = PositionSizer(cfg)
    for value in [atr, atr*10, None]:
        result = sizer.compute(PriceInfo(symbol=symbol,last_close=price,atr_20=value))
        assert result.proposed_shares == qty
        assert qty*price*.05 <= cfg.account_equity*cfg.risk_per_trade_pct
    assert sizer.compute(PriceInfo(symbol=symbol,last_close=price,atr_20=atr)).proposed_shares*price >= 50


def test_disabled_winner_preserves_atr_missing_and_minimum_guards():
    cfg = RiskConfig(account_equity=1940.7,risk_per_trade_pct=.01,min_position_notional=70)
    sizer = PositionSizer(cfg)
    assert sizer.compute(PriceInfo('BAND',53.11,None)).proposed_shares == 0
    assert PositionSizer(replace(cfg,fixed_stop_pct=.05,min_position_notional=1000)).compute(
        PriceInfo('BAND',53.11,None)).proposed_shares == 0


def test_legacy_watcher_cannot_rewrite_campaign_owned_protections(monkeypatch):
    from execution_engine.protection_watcher import ProtectionTransitionWatcher
    from execution_engine.config import ExecutionConfig
    from test_protection_watcher import _item
    item = _item()
    repo = MagicMock()
    repo.load_pending_protection_watch_items.return_value = [item]
    repo.load_unprotected_filled_entries.return_value = [dict(symbol=item.symbol,
        account_id=item.account_id,broker_mode=item.broker_mode,exec_run_id=item.source_exec_run_id)]
    watcher = ProtectionTransitionWatcher(repo,lambda *a:Mock(),lambda *a:ExecutionConfig())
    monkeypatch.setattr(watcher,'_run_winner_campaigns',lambda *a,**k:{(item.account_id,item.broker_mode,item.symbol)})
    legacy = Mock(side_effect=AssertionError('Legacy protection must not change Winner SL'))
    monkeypatch.setattr(watcher,'_process_item',legacy)
    monkeypatch.setattr(watcher,'_arm_missing_protections',legacy)
    monkeypatch.setattr(watcher,'_apply_time_stop_exits',Mock())
    watcher.run(exec_run_id=item.source_exec_run_id)
    legacy.assert_not_called()
