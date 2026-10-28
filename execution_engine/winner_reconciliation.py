"""Distinguish durable unsubmitted campaigns from expected broker holdings."""


def defer_unsubmitted_campaign_targets(targets, records, *, exec_run_id, risk_run_id, account_id, broker_mode):
    """Only an exact PENDING plan with zero operations/lots/parents is deferred.

    The caller separately verifies empty OMS requests/fills. Broker positions
    remain compared, so an unexpected real holding still raises an alert.
    """
    pending = set()
    for record in records:
        state = record['state']
        if (state.get('exec_run_id') == exec_run_id and state.get('risk_run_id') == risk_run_id
                and state.get('account_id') == account_id and state.get('broker_mode') == broker_mode
                and state.get('status') == 'PENDING' and state.get('admission') == 'STEP11_APPROVED_RECHECK_REQUIRED'
                and state.get('lots') == [] and state.get('operations') == [] and state.get('parents') == {}
                and not state.get('initial_attempted') and state.get('first_fill_at') is None):
            pending.add(state['symbol'])
    deferred = [target for target in targets if target['symbol'] in pending]
    return [target for target in targets if target['symbol'] not in pending], deferred
