"""TP15/SL7 is a versioned target change, not a new fit or reused old PnL."""
from copy import deepcopy
import json

import pytest

from scripts.research import us_oracle_path_profit_filter_tp15_sl7_protocol as study


def test_target_changed_and_parent_unchanged():
    before = study.original.read(study.original.SPEC)
    spec = study.resolve_spec()
    assert spec['target']['take_profit_pct'] == .15
    assert spec['target']['stop_loss_pct'] == .07
    assert before == study.original.read(study.original.SPEC)
    assert before['target']['take_profit_pct'] == before['target']['stop_loss_pct'] == .1


def test_only_requested_amendment_no_feature_threshold_or_period_tuning():
    expected = deepcopy(study.original.read(study.original.SPEC))
    expected['experiment'] = study.EXPERIMENT
    expected['target'].update(take_profit_pct=.15, stop_loss_pct=.07)
    expected['future_portfolio_comparison'].update(study.COMPARISON_AMENDMENT)
    assert study.resolve_spec() == expected
    assert not expected['target']['trailing'] and expected['target']['holding_sessions'] == 20
    assert expected['learner']['threshold'] == .5 and expected['population']['top_titles'] == 20


def test_new_control_required_and_risk_budget_follows_SL():
    spec = study.resolve_spec()
    control = spec['future_portfolio_comparison']
    assert control['fresh_all_long_control_required']
    assert not control['reuse_parent_economic_results']
    assert control['risk_budget_pct_before_native_guards'] == pytest.approx(.4*spec['target']['stop_loss_pct'])
    assert spec['safety']['new_GO_required_before_label_engine_and_training']


@pytest.mark.parametrize('change', ['learner', 'stop', 'old_results'])
def test_unrequested_changes_fail(tmp_path, change):
    value = study.original.read(study.SPEC)
    if change == 'learner': value['learner'] = {'threshold': .4}
    if change == 'stop': value['target_overrides']['stop_loss_pct'] = .1
    if change == 'old_results': value['comparison_amendment']['reuse_parent_economic_results'] = True
    path = tmp_path/'amendment.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError): study.resolve_spec(path)


def test_cannot_overwrite_parent_preparation():
    with pytest.raises(ValueError, match='Never overwrite'):
        study.prepare(study.PARENT)
