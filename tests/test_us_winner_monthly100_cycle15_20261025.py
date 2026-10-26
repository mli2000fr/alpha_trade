from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_winner_monthly100_cycle15_20261025 as experiment


def parent_protocol():
    return dict(variant='cycle15_no_hard',TOP=20,effective_gross_cap=1.,effective_initial_fraction=1.,
        profiles=deepcopy(experiment.study.PROFILES),global_liquidation=dict(cycle_drawdown_pct=.15,
        hard_drawdown_pct=None,cooldown_calendar_months=3,total_liquidation=True,soft_partial_liquidation=False))


def test_exact_parent_contract_passes():
    experiment.validate_parent(parent_protocol())


@pytest.mark.parametrize('key,value',[('cycle_drawdown_pct',.20),('hard_drawdown_pct',.25),
    ('cooldown_calendar_months',2),('total_liquidation',False),('soft_partial_liquidation',True)])
def test_wrong_reference_policy_is_rejected(key,value):
    protocol = parent_protocol(); protocol['global_liquidation'][key] = value
    with pytest.raises(ValueError,match='exact requested'):
        experiment.validate_parent(protocol)


def curves():
    dates = pd.DatetimeIndex([pd.Timestamp(s.session_date) for s in experiment.study.inputs.sessions()
        if experiment.study.inputs.SHADOW_START <= s.session_date <= experiment.study.inputs.END])
    return {name:pd.Series(4000.*(1.+(i+1)*.0001)**np.arange(len(dates)),index=dates)
        for i,name in enumerate(experiment.study.CATALOG)}


def test_hundred_sessions_is_100_returns_not_100_closes():
    data = curves(); result = experiment.decisions_100(data)
    first = result['2020-01']; series = next(iter(data.values())).loc[:'2019-12-31']
    assert len(result) == 60 and first['window'] == 100
    assert first['window_start'] == str(series.index[-101].date())
    assert first['cutoff'] == '2019-12-31' and first['first_session'] == '2020-01-02'


def test_january_decision_cannot_change_when_future_curves_are_changed():
    data = curves(); before = experiment.decisions_100(data)['2020-01']
    for series in data.values():
        series.loc[series.index >= pd.Timestamp('2020-01-01')] = .01
    after = experiment.decisions_100(data)['2020-01']
    assert before == after


def test_common_missing_session_is_not_treated_as_a_valid_100_day_history():
    series = next(iter(curves().values()))
    experiment.validate_curve(series,series.index)
    with pytest.raises(ValueError,match='every exact official'):
        experiment.validate_curve(series.drop(series.index[5]),series.index)


@pytest.mark.parametrize('bad',[0.,float('nan'),float('inf')])
def test_invalid_reference_valuation_fails_closed(bad):
    series = next(iter(curves().values()))
    expected = series.index.copy(); series.iloc[3] = bad
    with pytest.raises(ValueError,match='invalid reference'):
        experiment.validate_curve(series,expected)


def test_single_account_scope_does_not_redirect_parent_or_other_arms():
    study,cycle = experiment.study,experiment.cycle
    before = study.ROOT,study.ARMS,study.audit,study.run_case,cycle.CURRENT_FOLDER
    parent_root = cycle.ROOT
    with experiment.single_account_scope():
        assert study.ROOT == experiment.ROOT and study.ARMS == ['MONTHLY_100']
        assert study.audit is cycle.audit and study.configuration is cycle.configuration
        assert cycle.CURRENT_FOLDER == experiment.ROOT/'cases'/'MONTHLY_100'
        assert cycle.ROOT == parent_root
    assert before == (study.ROOT,study.ARMS,study.audit,study.run_case,cycle.CURRENT_FOLDER)


def test_dependency_waits_for_six_shadows_only_not_remaining_parent_accounts(tmp_path,monkeypatch):
    from backtesting.winner_campaign_replay import atomic_json
    for arm in experiment.SHADOWS:
        folder = tmp_path/'cases'/arm; folder.mkdir(parents=True)
        atomic_json(folder/'report.json',{})  # Presence check only; sealing audits contents separately.
    atomic_json(tmp_path/'progress.json',dict(status='RUNNING',arm='MONTHLY_30'))
    ready,missing,_ = experiment.reference_state(tmp_path)
    assert len(ready) == 6 and missing == []
    assert not (tmp_path/'cases'/'MONTHLY_30'/'report.json').exists()


def test_failed_upstream_does_not_start_duplicates_or_silently_retry(tmp_path):
    from backtesting.winner_campaign_replay import atomic_json
    atomic_json(tmp_path/'progress.json',dict(status='FAILED',error='reference failed'))
    with pytest.raises(RuntimeError,match='no automatic restart'):
        experiment.reference_state(tmp_path)


def test_completed_upstream_cannot_wait_forever_with_missing_references(tmp_path):
    from backtesting.winner_campaign_replay import atomic_json
    atomic_json(tmp_path/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY'))
    with pytest.raises(RuntimeError,match='reports are missing'):
        experiment.reference_state(tmp_path)
