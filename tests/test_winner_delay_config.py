"""A publication safety margin must not be confused with a candle-grid offset."""
from datetime import timedelta

import pytest

from common.winner_pyramiding import WinnerPyramidingConfig, load_winner_pyramiding_config, confirmed_breakout
from common.winner_delayed import delayed_snapshot, delayed_price_limit


@pytest.mark.parametrize('seconds',[0,900,901,930,1199,3600])
def test_config_accepts_integer_publication_delays_without_grid_restriction(seconds):
    policy=load_winner_pyramiding_config({'winner_pyramiding':{'market_data_delay_seconds':seconds}})
    assert policy.market_data_delay_seconds==seconds


@pytest.mark.parametrize('seconds',[True,False,None,-1,15,899,3601,930.0,'930',float('nan')])
def test_invalid_delay_still_fails_closed_with_actionable_message(seconds):
    with pytest.raises(ValueError,match='winner_pyramiding.market_data_delay_seconds'):
        WinnerPyramidingConfig(market_data_delay_seconds=seconds)


@pytest.mark.usefixtures('isolated_winner_config')
def test_930s_releases_regular_grid_candles_thirty_seconds_later():
    from tests.test_winner_runtime import setup,market,NOW
    cfg,store,_,_=setup(market_data_delay_seconds=930)
    state=store.rows()[0]['state']
    # Original five-minute timestamps remain unchanged; only availability moves.
    bars=market(state,NOW-timedelta(minutes=15))['bars']
    available=NOW+timedelta(seconds=30)
    assert not confirmed_breakout(bars,99.,cfg.winner_pyramiding,now=available-timedelta(seconds=1))
    assert confirmed_breakout(bars,99.,cfg.winner_pyramiding,now=available)
    snapshot=delayed_snapshot(bars,cfg.winner_pyramiding,available)
    assert delayed_price_limit(state,snapshot,available)==102.01
    assert snapshot['bars']==bars and snapshot['ask'] is None


def test_bad_config_shows_error_without_rendering_launch_form(monkeypatch):
    from streamlit.testing.v1 import AppTest
    def invalid():
        raise ValueError('winner_pyramiding.market_data_delay_seconds : entier requis')
    monkeypatch.setattr('common.winner_pyramiding.load_winner_pyramiding_config',invalid)
    def app():
        from ihm.pages.backtesting import _build_run_options
        _build_run_options()
    at=AppTest.from_function(app).run(timeout=30)
    assert not at.exception
    assert len(at.error)==1 and 'config.yaml' in at.error[0].value
    assert 'market_data_delay_seconds' in at.error[0].value
    assert not at.checkbox and not at.button
