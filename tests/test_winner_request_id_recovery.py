from copy import deepcopy

import pytest

from scripts.operations.recover_winner_request_id_20261028 import (
    CAMPAIGN,CLIENT,RISK,EXEC,RESERVED_AT,repaired_state)


def state():
    return dict(campaign_id=CAMPAIGN,risk_run_id=RISK,exec_run_id=EXEC,symbol='P',
        account_id='default',broker_mode='paper',status='PENDING',lots=[],initial_attempted=True,
        initial_quantity=1,parents={CLIENT:dict(action='ENTRY',booked_quantity=0,booked_notional=0.)},
        policy={'stop_loss_pct':.07},entry_policy={'max_entry_gap_pct':.03},
        operations=[dict(key=CAMPAIGN+'-entry',action='ENTRY',quantity=1,status='UNKNOWN',
            reserved_at=RESERVED_AT,intent=dict(intent_id=CLIENT,submission_key=CLIENT,
                risk_run_id=RISK,exec_run_id=EXEC,winner_campaign_id=CAMPAIGN,symbol='P',
                qty=1,side='buy',limit_price=142.89,order_type='limit',time_in_force='day'))])


def proof():
    return dict(zero_counts={key:0 for key in ('sql_requests','sql_fills','broker_positions',
        'broker_open_orders','broker_orders_today','broker_fills_today')},
        old_client_order_absent=True,pre_http_width_error=True,request_id_max_length=32,log_sha256='exact-log')


def test_fixed_recovery_preserves_original_intent_history_and_frozen_terms():
    original=state(); before=deepcopy(original)
    result=repaired_state(original,proof())
    assert original==before
    assert result['operations'][0]['intent']==before['operations'][0]['intent']
    assert result['operations'][0]['status']=='ABORTED_BEFORE_SUBMIT'
    assert len(result['operations'])==1 and not result['initial_attempted']
    assert result['parents']==before['parents'] and result['policy']==before['policy']
    assert result['entry_policy']==before['entry_policy']
    assert result['operator_recoveries'][0]['client_order_id_preserved']==CLIENT
    with pytest.raises(ValueError):repaired_state(result,proof())


@pytest.mark.parametrize('kind', ['404_only','broker_order','sql_request','fill','wrong_account',
    'wrong_campaign','wrong_risk','already_filled','other_reservation','other_intent_risk'])
def test_unknown_or_effectful_submission_is_never_released(kind):
    sample=state();evidence=proof()
    if kind=='404_only':evidence['pre_http_width_error']=False
    elif kind=='broker_order':evidence['zero_counts']['broker_orders_today']=1
    elif kind=='sql_request':evidence['zero_counts']['sql_requests']=1
    elif kind=='fill':evidence['zero_counts']['broker_fills_today']=1
    elif kind=='wrong_account':sample['account_id']='test1'
    elif kind=='wrong_campaign':sample['campaign_id']='other'
    elif kind=='wrong_risk':sample['risk_run_id']='other'
    elif kind=='already_filled':sample['parents'][CLIENT]['booked_quantity']=1
    elif kind=='other_reservation':sample['operations'][0]['reserved_at']='2026-10-28T16:00:00+00:00'
    else:sample['operations'][0]['intent']['risk_run_id']='other'
    with pytest.raises(ValueError):repaired_state(sample,evidence)
