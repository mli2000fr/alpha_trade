"""B4 monetary boundaries: floating noise must not alter risk decisions.

No relaxed allocation audit, price rounding, or change to percentage thresholds.
The sealed pre-remediation module supplies a B0..B3 non-regression reference.
"""
from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest

from backtesting import adaptive_breaker as core
from backtesting.production_risk_replay import ProductionRiskController
from backtesting.risk_overlay import DrawdownCircuitBreaker
from tests.test_production_risk_replay import fields


@pytest.mark.parametrize('policy,expected', [('b4', .5), ('b4a', .75)])
@pytest.mark.parametrize('noise', [-4.09e-12, 0., 4.09e-12])
def test_reported_false_new_trough_does_not_reset_rearm(policy, expected, noise):
    trough = 2962.909589372622
    episode = core.BreakerEpisode(peak=4419.986558852381, trough=trough,
        allocation=expected, favorable_streak=3, tripped=True,
        rearm_start_dd=(4419.986558852381-trough)/4419.986558852381)
    core.trip_or_recover(episode, trough+noise, episode.peak, policy=policy, max_dd_pct=.2)
    assert episode.trough == trough
    assert episode.favorable_streak == 3 and not episode.relapse_day
    assert core.allocate(policy, episode, trough+noise, regime='BULL') == expected


@pytest.mark.parametrize('loss', [1e-5, .01, 1.])
@pytest.mark.parametrize('policy', ['b4', 'b4a'])
def test_real_new_trough_still_triggers_relapse(policy, loss):
    episode = core.BreakerEpisode(peak=4000., trough=3000., allocation=.5,
        favorable_streak=3, tripped=True, rearm_start_dd=.25)
    core.trip_or_recover(episode, 3000.-loss, 4000., policy=policy, max_dd_pct=.2)
    assert episode.trough == 3000.-loss and episode.favorable_streak == 0
    assert episode.relapse_day
    assert core.allocate(policy, episode, 3000.-loss, regime='BULL') == .1


def test_sub_tolerance_moves_do_not_accumulate_hidden_trough_drift():
    episode = core.BreakerEpisode(peak=4000., trough=3000., allocation=.5,
        favorable_streak=3, tripped=True, rearm_start_dd=.25)
    for step in range(1, 6):
        core.trip_or_recover(episode, 3000.-step*1e-7, 4000., policy='b4', max_dd_pct=.2)
        assert episode.trough == 3000. and not episode.relapse_day
    core.trip_or_recover(episode, 3000.-2e-6, 4000., policy='b4', max_dd_pct=.2)
    assert episode.relapse_day and episode.trough < 3000.


@pytest.mark.parametrize('policy', ['b4', 'b4a'])
@pytest.mark.parametrize('offset,trip', [(-.01, True), (-1e-11, True), (0., True), (1e-11, True), (.01, False)])
def test_twenty_percent_trip_boundary(policy, offset, trip):
    episode = core.BreakerEpisode()
    core.trip_or_recover(episode, 3200.+offset, 4000., policy=policy, max_dd_pct=.2)
    assert episode.tripped is trip


@pytest.mark.parametrize('policy', ['b4', 'b4a'])
@pytest.mark.parametrize('fraction,regime,expected,below', [(.25, 'REBOUND', .5, .1), (.5, 'BULL', 1., .75)])
@pytest.mark.parametrize('offset', [-1e-11, 0., 1e-11])
def test_recovery_allocation_boundary(policy, fraction, regime, expected, below, offset):
    episode = core.BreakerEpisode(peak=4000., trough=3000., tripped=True)
    equity = 3000.+fraction*1000.+offset
    assert core.allocate(policy, episode, equity, regime=regime) == expected
    episode = core.BreakerEpisode(peak=4000., trough=3000., tripped=True)
    assert core.allocate(policy, episode, equity-.01, regime=regime) == below


@pytest.mark.parametrize('policy', ['b4', 'b4a'])
@pytest.mark.parametrize('offset,recovered', [(-.01, False), (-1e-11, True), (0., True), (1e-11, True)])
def test_ninety_percent_episode_recovery_boundary(policy, offset, recovered):
    episode = core.BreakerEpisode(peak=4000., trough=3000., allocation=1., tripped=True)
    core.trip_or_recover(episode, 3900.+offset, 4000., policy=policy, max_dd_pct=.2)
    assert episode.tripped is not recovered


@pytest.mark.parametrize('policy', ['b4', 'b4a'])
@pytest.mark.parametrize('offset,relapse', [(-.01, True), (-1e-11, True), (0., True), (1e-11, True), (.01, False)])
def test_three_point_drawdown_relapse_boundary(policy, offset, relapse):
    episode = core.BreakerEpisode(peak=4000., trough=2500., allocation=.5,
        favorable_streak=3, tripped=True, rearm_start_dd=.2)
    core.trip_or_recover(episode, 3080.+offset, 4000., policy=policy, max_dd_pct=.2)
    assert episode.relapse_day is relapse
    assert episode.trough == 2500.


@pytest.mark.parametrize('policy', ['b4', 'b4a'])
def test_real_production_and_backtest_machines_keep_same_allocations_despite_noise(policy):
    f=fields(); f['policy']=policy; f['rolling_peak_window_days']=0
    prod=ProductionRiskController(f)
    bt=DrawdownCircuitBreaker(enabled=True, policy=policy, max_dd_pct=.2,
        rolling_peak_window_days=0, regime_ramp_up_enabled=True)
    sequence=[4000., 3000., 3000., 3000., 3000., 3100., 3250., 3500., 3900., 4100.]
    allocations=[]
    for i, equity in enumerate(sequence):
        day=pd.Timestamp('2025-01-02')+pd.Timedelta(days=i)
        # Independent summation orders observed in runtime vs cash reconstruction.
        observed=equity+(-4e-12 if i==4 else 0.)
        bt._regime_today='BULL'; bt.update(equity, max(4000., equity))
        bt.just_tripped(); bt.update_regime_streak('normal', equity)
        event=prod.evaluate(day, observed, 'BULL')
        assert event['allocation_scale'] == bt.allocation_scale('normal')
        allocations.append(event['allocation_scale']); prod.finish(day, observed)
    assert allocations[4] == (.5 if policy=='b4' else .75)


@pytest.mark.parametrize('policy', ['b0', 'b1', 'b2', 'b3'])
def test_other_policies_bit_for_bit_equal_to_sealed_original(policy):
    source=Path('artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v1/source-snapshot/backtesting/adaptive_breaker.py')
    assert source.is_file(), 'Explicit sealed pre-remediation reference is required'
    name='_sealed_legacy_breaker_nonregression'
    spec=importlib.util.spec_from_file_location(name, source)
    old=importlib.util.module_from_spec(spec); sys.modules[name]=old
    try:
        spec.loader.exec_module(old)
        original=old.BreakerEpisode(); repaired=core.BreakerEpisode()
        sequence=[4000., 3100., 3000., 3000.-4e-12, 3100., 3250., 3500., 3750., 3900., 4100.]
        for equity in sequence:
            for module, episode in [(old, original), (core, repaired)]:
                module.trip_or_recover(episode, equity, max(4000., equity), policy=policy, max_dd_pct=.2)
                module.update_streak(episode, True)
                episode.allocation=module.allocate(policy, episode, equity, regime='BULL')
            assert asdict(original) == asdict(repaired)
    finally:
        sys.modules.pop(name, None)
