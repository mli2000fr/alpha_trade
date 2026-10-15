from copy import deepcopy

import pytest

from scripts.research.us_three_oracle_comparison import validate_contract


def fixture(arm):
    reference=dict(universe=['A'],columns=['f'],options={'feature_set':'expert'})
    profile=dict(feature_columns=['f'],generator_options=reference['options'])
    head=dict(status='TRAINED',train_available_max='2022-07-06',val_available_max='2023-01-04')
    if arm=='PATH_H20':
        protocol=dict(universe=['A'],mode='oracle_path_h20',horizon=20,target='oracle_path_extreme20')
        done=dict(metrics=head)
    else:
        protocol=dict(universe=['A'],mode='oracle_tp_before_sl',barriers=dict(
            take_profit_pct=.2,stop_loss_pct=.07 if arm=='TRAIN_TP20_SL7' else .1,max_sessions=20))
        done=dict(metrics={'heads':{'long':head,'short':deepcopy(head)}})
    return protocol,profile,dict(status='completed'),done,reference,arm


@pytest.mark.parametrize('arm',['PATH_H20','TRAIN_TP20_SL7','TRAIN_TP20_SL10'])
def test_compatible_contracts(arm):
    validate_contract(*fixture(arm))


def test_path_is_not_terminal_oracle():
    args=fixture('PATH_H20')
    args[0]['mode']='oracle_extreme_h20'
    with pytest.raises(ValueError,match='path H20'):
        validate_contract(*args)


def test_training_barriers_do_not_silently_change():
    args=fixture('TRAIN_TP20_SL7')
    args[0]['barriers']['stop_loss_pct']=.1
    with pytest.raises(ValueError,match='trained barriers'):
        validate_contract(*args)


def test_incompatible_features_are_not_reused():
    args=fixture('PATH_H20')
    args[1]['feature_columns']=['g']
    with pytest.raises(ValueError,match='feature contract'):
        validate_contract(*args)


def test_external_validation_labels_are_rejected():
    args=fixture('TRAIN_TP20_SL10')
    args[3]['metrics']['heads']['long']['val_available_max']='2024-01-01'
    with pytest.raises(ValueError,match='external test'):
        validate_contract(*args)


def test_result_audit_rejects_partial_comparison(tmp_path):
    from scripts.research.us_three_oracle_result_audit import audit
    from scripts.research.us_concentrated_historical_tapes import atomic_json
    atomic_json(tmp_path/'report.json',dict(status='PARTIAL_FAILED',completed=8,failed=1))
    atomic_json(tmp_path/'manifest.json',{})
    with pytest.raises(ValueError,match='Nine completed'):
        audit(tmp_path)
