"""V10 explicit LONG event, subjective probability, independent evidence gates."""
import math


def probability_schema(value,*,breakdown=False):
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
    if breakdown:
        fields.update(
            probability_stop_touch={'type':['number','null'],'minimum':0,'maximum':1},
            probability_positive_exit={'type':['number','null'],'minimum':0,'maximum':1},
            stop_touch_explanation={'type':'string'},positive_exit_explanation={'type':'string'})
    value['properties'].update(fields)
    value['required'] += list(fields)
    return value


def normalize(result,*,breakdown=False):
    p = result['probability_up_without_stop']
    if ((result['probability_status']=='UNDETERMINABLE') != (p is None)
            or p is not None and (type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1)):
        raise ValueError('Probabilité manquante/non finie ou état incohérent')
    for field in ['probability_explanation','evidence_explanation']:
        if not result[field].strip():
            raise ValueError('Explication de probabilité et preuves obligatoire')
    if breakdown:
        _validate_breakdown(result)
    result['decision'] = 'LONG' if p is not None else 'ABSTAIN'


def _validate_breakdown(result):
    joint=result['probability_up_without_stop']
    stop=result['probability_stop_touch'];up=result['probability_positive_exit']
    for field in ['probability_stop_touch','probability_positive_exit']:
        value=result[field]
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1):
            raise ValueError('Probabilité séparée non finie ou hors [0,1]')
    for field in ['stop_touch_explanation','positive_exit_explanation']:
        if not result[field].strip():raise ValueError('Explication des probabilités séparées obligatoire')
    # U = hypothetical positive exit even if a stop would have closed the trade;
    # S = stop touched before that same exit. Joint = P(U AND NOT S).
    if joint is not None:
        low=max(0.,up-stop) if up is not None and stop is not None else 0.
        high=min(up if up is not None else 1.,1-stop if stop is not None else 1.)
        if not low-1e-12<=joint<=high+1e-12:
            raise ValueError('Probabilités incohérentes : hausse sans SL incompatible avec hausse et touche SL')


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
