from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

from backtesting.production_risk_replay import ProductionRiskController
from scripts.research import us_intraday_protection_grid_dd15 as runner


def reference_profile():
    return json.loads((runner.REFERENCE/'production-risk.json').read_text(encoding='utf-8'))


def test_profile_changes_only_threshold_without_mutating_reference():
    old = reference_profile(); before = deepcopy(old)
    fields = dict(old['guard_fields']); fields[runner.DD_FIELD] = .15
    new = runner.threshold_profile(old, fields, old['force_close_enabled'], old['force_close_fraction'])
    assert old == before
    expected = deepcopy(old)
    expected['guard_fields'][runner.DD_FIELD] = .15
    expected['canonical_risk_configuration'][runner.DD_FIELD] = .15
    expected['note'] = new['note']
    assert new == expected


@pytest.mark.parametrize('key,value', [('max_daily_loss_pct', .02), ('policy', 'b4a'),
    ('rolling_peak_window_days', 126), ('regime_ramp_up_max_pct', .5)])
def test_rejects_confounded_guard_changes(key, value):
    old = reference_profile(); fields = dict(old['guard_fields'])
    fields[runner.DD_FIELD] = .15; fields[key] = value
    with pytest.raises(ValueError, match='Only the drawdown'):
        runner.threshold_profile(old, fields, old['force_close_enabled'], old['force_close_fraction'])


@pytest.mark.parametrize('force,fraction', [(False, .5), (True, 1.)])
def test_rejects_changed_liquidation(force, fraction):
    old = reference_profile(); fields = dict(old['guard_fields']); fields[runner.DD_FIELD] = .15
    with pytest.raises(ValueError, match='Forced-close'):
        runner.threshold_profile(old, fields, force, fraction)


def test_old_twenty_percent_cannot_be_silently_reused():
    old = reference_profile()
    with pytest.raises(ValueError, match='configuredDD15'):
        runner.threshold_profile(old, old['guard_fields'], True, .5)


def test_real_controller_trips_earlier_at_fifteen_without_changing_policy():
    old = reference_profile(); fields = dict(old['guard_fields']); fields[runner.DD_FIELD] = .15
    day = pd.Timestamp('2025-01-02')
    dd20 = ProductionRiskController(old['guard_fields']).evaluate(day, 3300., 'SLIDE')
    dd15 = ProductionRiskController(fields).evaluate(day, 3300., 'SLIDE')
    assert not dd20['just_tripped'] and dd20['allocation_scale'] == 1.
    assert dd15['just_tripped'] and dd15['allocation_scale'] == .1
    assert not dd15['active']  # no invented hard halt


def test_sealed_runs_and_nested_outputs_are_protected():
    for path in [runner.REFERENCE, runner.REFERENCE/'nested-attempt']:
        with pytest.raises(ValueError, match='sealed research'):
            runner.prepare(path)


def test_parent_runner_is_restored_even_if_run_fails(monkeypatch, tmp_path):
    p, c = runner.risk.prepare, runner.risk.comparison
    def fail(*a, **k):
        assert runner.risk.prepare is runner.prepare
        assert runner.risk.comparison is runner.comparison
        raise RuntimeError('test failure')
    monkeypatch.setattr(runner.risk, 'run', fail)
    with pytest.raises(RuntimeError, match='test failure'):
        runner.run(tmp_path)
    assert runner.risk.prepare is p and runner.risk.comparison is c
