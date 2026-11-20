"""V10 explicit LONG event, subjective probability, independent evidence gates."""
import math


def probability_schema(value):
    value['properties'].pop('decision')
    value['required'].remove('decision')
    fields = dict(
        probability_status={'type':'string','enum':['ESTIMATED','UNDETERMINABLE']},
        probability_up_without_stop={'type':['number','null'],'minimum':0,'maximum':1},
        horizon_sessions={'type':'integer','minimum':1,'maximum':60},
        stop_loss_pct={'type':'number','minimum':0.00000001,'maximum':0.99999999},
        evidence_quality={'type':'string','enum':['SUFFICIENT','PARTIAL','INSUFFICIENT']},
        evidence_explanation={'type':'string'}, probability_explanation={'type':'string'},
        risk_factors={'type':'array','items':{'type':'string'}})
    value['properties'].update(fields)
    value['required'] += list(fields)
    return value


def normalize(result):
    p = result['probability_up_without_stop']
    if ((result['probability_status']=='UNDETERMINABLE') != (p is None)
            or p is not None and (type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1)):
        raise ValueError('Probabilité manquante/non finie ou état incohérent')
    for field in ['probability_explanation','evidence_explanation']:
        if not result[field].strip():
            raise ValueError('Explication de probabilité et preuves obligatoire')
    result['decision'] = 'LONG' if p is not None else 'ABSTAIN'


def qualify(result, context):
    contract=context['long_without_stop_contract']
    if (result['horizon_sessions'] != contract['horizon_sessions']
            or abs(result['stop_loss_pct']-contract['stop_loss_pct'])>1e-12):
        raise ValueError('Horizon ou SL retourné différent du contrat Winner')
    reported=result['evidence_quality']
    effective=reported
    if not result['identity_verified'] or result['probability_up_without_stop'] is None:
        effective='INSUFFICIENT'
    elif result['selection_blockers'] and reported=='SUFFICIENT':
        effective='PARTIAL'
    result.update(reported_evidence_quality=reported,evidence_quality=effective)
    if effective!='SUFFICIENT':
        result['selection_blockers'].append('evidence_'+effective.lower())
    if result['probability_up_without_stop'] is None:
        result['selection_blockers'].append('probability_undeterminable')
    result['probability_is_calibrated']=False
