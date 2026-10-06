"""FR 13-B preparation: immutable intentions, shared tapes, ledger reporting.

No SQL or fit. Preparation templates are not executable economic evidence.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd

from service.fr.exploitable_scope_12e import sha


def validate_intents(intents, cfg):
    keys = ['fold', 'decision_session_date', 'policy', 'research_uid']
    if intents.empty or intents.duplicated(keys).any() or intents.future_label_used.any():
        raise ValueError('Intentions vides/dupliquées ou utilisant le futur')
    if set(intents.policy) != set(cfg['policies']) or set(intents.fold) != set(cfg['folds']):
        raise ValueError('Politiques/folds divergents du protocole')
    if not intents.execution_state.eq('INTENT_NOT_FILL').all() or intents.candidate_rank.le(0).any():
        raise ValueError('Rangs ou état d’intention invalide')
    if intents.decision_session_date.gt(cfg['development_end']).any():
        raise ValueError('Confirmation réservée')
    if intents.duplicated(['fold','decision_session_date','policy','candidate_rank']).any():
        raise ValueError('Rangs ambigus')


def assemble_tape(shared: dict, intentions: pd.DataFrame, cfg: dict, fold: int, policy: str) -> dict:
    """Attach ALL original policy intents to a common execution dataset.

    Availability is supplied as qualified evidence, never fabricated from dates.
    Structural assembly is not a certification of the evidence's authenticity.
    """
    validate_intents(intentions, cfg)
    if fold not in cfg['folds'] or policy not in cfg['policies']:
        raise ValueError('Fold/politique non figé')
    if shared.get('fold') != fold or shared.get('evidence_state') != 'QUALIFIED_EXECUTION_INPUT':
        raise ValueError('Données communes non qualifiées ou fold divergent')
    expected = {'market_code':'FR_EQ','currency':'EUR','horizon':cfg['horizon'],
                'max_positions':cfg['portfolio']['max_positions'],
                'canonical_writes_enabled':False,'serving_enabled':False}
    if any(shared.get(k) != v for k,v in expected.items()) or Decimal(str(shared['initial_equity'])) != Decimal(str(cfg['portfolio']['initial_equity'])):
        raise ValueError('Contrat de tape divergent')
    sessions = shared['sessions']
    if not sessions or sessions != sorted(set(sessions)) or sessions[-1] > cfg['development_end']:
        raise ValueError('Calendrier invalide ou confirmation réservée')
    if shared.get('candidates'):
        raise ValueError('Les candidats doivent provenir des intentions figées uniquement')
    # All policies see the same instrument/calendar/evidence population.
    fold_intents = intentions[intentions.fold.eq(fold)]
    if not set(fold_intents.research_uid).issubset(shared['instruments']):
        raise ValueError('Population commune amputée')
    selected = fold_intents[fold_intents.policy.eq(policy)].sort_values(['decision_session_date','candidate_rank'])
    candidates = []
    for row in selected.itertuples():
        day, uid = row.decision_session_date, row.research_uid
        if day not in sessions:
            raise ValueError('Séance d’intention absente de la tape')
        evidence = shared.get('candidate_availability', {}).get(day, {}).get(uid)
        if not evidence or not evidence.get('available_at') or not evidence.get('evidence'):
            raise ValueError(f'Disponibilité du signal non qualifiée : {uid}/{day}')
        available = datetime.fromisoformat(evidence['available_at'])
        decision = datetime.fromisoformat(shared['decision_at'][day])
        entry = datetime.fromisoformat(shared['entry_at'][day])
        if any(t.tzinfo is None for t in (available,decision,entry)) or not available <= decision <= entry:
            raise ValueError('Signal futur/horodatage naïf ou entrée avant décision')
        candidates.append({'session':day,'uid':uid,'rank':int(row.candidate_rank),
                           'available_at':evidence['available_at']})
    output = deepcopy(shared)
    output['candidates'] = candidates
    output['policy'] = policy
    return output


def ledger_metrics(result: dict, *, data_kind: str) -> dict:
    """Metrics from a completed, reconciled LONG EUR ledger, never a partial one."""
    if data_kind not in {'SYNTHETIC_TEST_ONLY','QUALIFIED_RESEARCH'}:
        raise ValueError('Origine des données explicite requise')
    if result.get('status') != 'COMPLETED_ASSUMED_COST_RESEARCH':
        raise ValueError('Ledger bloqué/partiel : aucune performance calculable')
    initial = Decimal(str(result['initial_equity']))
    rows = result['ledger']['equity']
    if not rows or [r['session'] for r in rows] != sorted({r['session'] for r in rows}):
        raise ValueError('Courbe d’equity absente/dupliquée/non ordonnée')
    if rows[-1]['session'] > '2025-12-31':
        raise ValueError('Confirmation réservée')
    values = np.array([float(r['equity']) for r in rows])
    if initial <= 0 or not np.isfinite(values).all() or (values <= 0).any() \
            or any(float(r['market_value'])<0 or float(r['cash'])<0 for r in rows):
        raise ValueError('Equity positive finie requise')
    final = Decimal(str(rows[-1]['equity']))
    if final != Decimal(str(result['final_equity'])) or final-initial != Decimal(str(result['net_pnl'])):
        raise ValueError('PnL/equity non réconciliés')
    trades = result['ledger']['trades']
    if sum((Decimal(str(t['net_pnl'])) for t in trades), Decimal(0)) != final-initial:
        raise ValueError('Trades/equity non réconciliés')
    equity = np.r_[float(initial),values]
    returns = equity[1:]/equity[:-1]-1
    sigma = returns.std(ddof=1) if len(returns)>1 else 0
    orders = [r for r in result['ledger']['orders'] if r['side'] in ('BUY','SELL')]
    costs = {k:sum((Decimal(str(o[k])) for o in orders),Decimal(0)) for k in ('commission','spread','slippage','taxes')}
    if any(costs[k] != Decimal(str(result['costs'][k])) for k in costs):
        raise ValueError('Frais du ledger non réconciliés')
    exposure = np.array([float(r['market_value'])/float(r['equity']) for r in rows])
    dividends = sum((Decimal(str(m['amount'])) for m in result['ledger']['cash_movements']
                     if m['kind']=='DIVIDEND_PAYMENT'),Decimal(0))
    by_symbol = {}
    for t in trades:
        by_symbol[t['uid']] = by_symbol.get(t['uid'],Decimal(0))+Decimal(str(t['net_pnl']))
    by_semester = []
    previous = initial
    for semester in sorted({r['session'][:4]+'H'+('1' if int(r['session'][5:7])<=6 else '2') for r in rows}):
        group = [r for r in rows if r['session'][:4]+'H'+('1' if int(r['session'][5:7])<=6 else '2')==semester]
        end = Decimal(str(group[-1]['equity']))
        by_semester.append({'semester':semester,'net_pnl_eur':str(end-previous),
                            'net_return_pct':float((end/previous-1)*100),'sessions':len(group)})
        previous = end
    return {'data_kind':data_kind,'not_production_evidence':True,'net_pnl_eur':str(final-initial),
            'net_return_pct':float((final/initial-1)*100),
            'daily_sharpe':float(returns.mean()/sigma*np.sqrt(252)) if sigma>0 else None,
            'sharpe_convention':'sample_std_ddof1_rf0_252_sessions_including_initial_to_first_close',
            'max_drawdown_pct':float((1-equity/np.maximum.accumulate(equity)).max()*100),
            'mean_gross_exposure_pct':float(exposure.mean()*100),
            'mean_net_exposure_pct':float(exposure.mean()*100),
            'turnover':float(sum((Decimal(str(o['notional'])) for o in orders),Decimal(0)))/values.mean(),
            'turnover_convention':'two_way_notional_divided_by_mean_closing_equity_not_annualized',
            'executed_orders':len(orders),'closed_trades':len(trades),
            'win_rate':sum(Decimal(str(t['net_pnl']))>0 for t in trades)/len(trades) if trades else None,
            'costs_eur':{k:str(v) for k,v in costs.items()},'dividend_cashflows_eur':str(dividends),
            'by_symbol_net_pnl_eur':{k:str(v) for k,v in by_symbol.items()}, 'by_semester':by_semester,
            'serving_enabled':False,'economic_go_allowed':False}


def prepare(output: Path, frozen: Path) -> dict:
    if output.exists():
        raise ValueError('Choisir un nouveau dossier de sortie')
    prior = json.loads((frozen/'report.json').read_text(encoding='utf-8'))
    protocol = json.loads((frozen/'protocol.json').read_text(encoding='utf-8'))
    if protocol != prior['protocol'] or prior['serving_enabled'] is not False:
        raise ValueError('Gel 13-A incohérent')
    for name, expected in prior['input_hashes'].items():
        if sha(Path(name)) != expected:
            raise ValueError(f'Entrée gelée modifiée : {name}')
    intent_paths = [Path(p) for p in prior['input_hashes'] if Path(p).name=='selection_intents.parquet']
    if len(intent_paths)!=1:
        raise ValueError('Ledger d’intentions non identifiable')
    intents = pd.read_parquet(intent_paths[0])
    cfg = protocol['development_protocol']
    validate_intents(intents,cfg)
    output.mkdir(parents=True,exist_ok=False)
    tasks = []
    for fold in cfg['folds']:
        group = intents[intents.fold.eq(fold)]
        template = {'schema_version':1,'fold':fold,'market_code':'FR_EQ','currency':'EUR',
                    'evidence_state':'UNQUALIFIED_TEMPLATE_DO_NOT_REPLAY',
                    'horizon':cfg['horizon'],'max_positions':cfg['portfolio']['max_positions'],
                    'initial_equity':str(cfg['portfolio']['initial_equity']),
                    'canonical_writes_enabled':False,'serving_enabled':False,
                    'sessions':[], 'calendar_evidence':None,'instruments':{},'bars':{},'events':[],
                    'corporate_action_coverage':{},'settlements':{},'candidate_availability':{},
                    'decision_at':{},'entry_at':{},
                    'required_uids':sorted(set(group.research_uid)),
                    'required_decision_sessions':sorted(set(group.decision_session_date))}
        name=f'fold-{fold}-shared-template.json'
        (output/name).write_text(json.dumps(template,ensure_ascii=False,indent=2),encoding='utf-8')
        for policy in cfg['policies']:
            selected=group[group.policy.eq(policy)].sort_values(['decision_session_date','candidate_rank'])
            filename=f'fold-{fold}-{policy}-intentions.parquet'
            selected.to_parquet(output/filename,index=False)
            tasks.append({'fold':fold,'policy':policy,'intentions':len(selected),'shared_template':name,
                          'intentions_file':filename,'intentions_sha256':sha(output/filename),
                          'shared_template_sha256':sha(output/name), 'scenarios':[1,2],
                          'status':'BLOCKED_UNQUALIFIED_EXECUTION_INPUT','net_pnl':None})
    result={'status':'PREPARED_REPLAY_BLOCKED','tasks':tasks,'frozen_report_sha256':sha(frozen/'report.json'),
            'frozen_protocol_sha256':sha(frozen/'protocol.json'),
            'implementation_sha256':sha(Path(__file__)),'executed_orders':0,'net_pnl':None,
            'models_refit':0,'canonical_writes':False,'serving_enabled':False,
            'confirmation_2026_evaluated':False,'benchmark_state':protocol['benchmark_state']}
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
