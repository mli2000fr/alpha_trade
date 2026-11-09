from concurrent.futures import ThreadPoolExecutor

import pytest

from common.config_loader import load_market_registry, replay_market_registry
from common.market_context import MarketCompatibilityError, MarketRegistry


def test_scoped_registry_survives_unavailable_directory_and_restores_on_failure(monkeypatch,tmp_path):
    registry=load_market_registry()
    def unavailable(cls,path):raise MarketCompatibilityError('Le registre de marchés est vide')
    monkeypatch.setattr(MarketRegistry,'from_directory',classmethod(unavailable))
    with pytest.raises(RuntimeError,match='restore'):
        with replay_market_registry(registry):
            assert load_market_registry() is registry
            with ThreadPoolExecutor(max_workers=1) as pool:
                with pytest.raises(MarketCompatibilityError):pool.submit(load_market_registry).result()
            with pytest.raises(MarketCompatibilityError):load_market_registry(tmp_path)
            raise RuntimeError('restore')
    with pytest.raises(MarketCompatibilityError):load_market_registry()
    with pytest.raises(TypeError):
        with replay_market_registry(None):pass


@pytest.mark.usefixtures('isolated_winner_config')
def test_native_winner_keeps_stops_horizon_and_accounting_when_registry_listing_disappears(monkeypatch):
    from backtesting.simulator import BacktestEngine
    from tests.test_winner_daily_protection import setup
    cfg,args,raw=setup(horizon_sessions=1)
    expected=BacktestEngine(cfg).run(**args)
    original=MarketRegistry.from_directory;calls=[]
    def once(cls,path):
        calls.append(path)
        if len(calls)>1:raise MarketCompatibilityError('Le registre de marchés est vide')
        return original(path)
    monkeypatch.setattr(MarketRegistry,'from_directory',classmethod(once))
    result=BacktestEngine(cfg).run(**args)
    assert len(calls)==1
    import pandas as pd
    pd.testing.assert_frame_equal(expected.closed_trades_df,result.closed_trades_df)
    pd.testing.assert_series_equal(expected.equity_curve,result.equity_curve)
    assert result.closed_trades_df.iloc[0].exit_reason=='HORIZON_OPEN'
    assert result.tracker_snapshot['winner_replay']['market_registry']['mode']=='VALIDATED_ONCE_PINNED_FOR_REPLAY'
    with pytest.raises(MarketCompatibilityError):load_market_registry()
