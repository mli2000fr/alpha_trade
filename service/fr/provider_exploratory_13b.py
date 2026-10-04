"""Versioned FR supplier exploration. Local archives only; no SQL/network/fit."""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import yaml

from common.market_calendar import get_market_calendar
from service.fr.corporate_actions_audit import _rows
from service.fr.economic_preflight_11a import selection_ledger
from service.fr.economic_qualification_12a import dividend_check
from service.fr.execution_costs import load_cost_profile
from service.fr.exploitable_scope_12e import sha
from service.fr.provider_exploratory_engine_13b import ReplayBlocked, replay_assumed
from service.fr.provider_exploratory_metrics_13b import ledger_metrics
from service.fr.universe_liquidity_6b import _load_symbol_bars


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def repair_prices(rows,symbol,repairs):
    rows=dict(rows)
    for repair in (repairs or {}).get('prices',[]):
        if repair['symbol']==symbol:
            if repair['date'] in rows:
                raise ValueError('Repair cannot silently replace an existing provider price')
            rows[repair['date']]=dict(repair['bar'])
    return rows


def repair_dividend(row,symbol,repairs):
    matches=[r for r in (repairs or {}).get('dividends',[]) if r['symbol']==symbol and r['date']==row['date']]
    if len(matches)>1:
        raise ValueError('Ambiguous dividend repair')
    if not matches:
        return dict(row),None
    supplement=matches[0]
    if Decimal(str(row['unadjustedValue']))!=Decimal(supplement['cash']) or row.get('currency')!='EUR':
        raise ValueError('Dividend amount/currency repair mismatch')
    payment=date.fromisoformat(supplement['payment_date'])
    if payment<date.fromisoformat(row['date']):
        raise ValueError('Payment repair precedes ex date')
    return dict(row,paymentDate=supplement['payment_date']),supplement


def load_frozen(config):
    frozen = Path(config['frozen'])
    report = json.loads((frozen/'report.json').read_text(encoding='utf-8'))
    for name, expected in report['input_hashes'].items():
        if sha(Path(name)) != expected:
            raise ValueError(f'Frozen input changed: {name}')
    cfg = report['protocol']['development_protocol']
    preflight = Path(config['preflight'])
    anchors = {Path(p).resolve():v for p,v in report['input_hashes'].items()}
    for name in ('selection_intents.parquet','decision_candidates_scored.parquet'):
        path = preflight/name
        if anchors.get(path.resolve()) != sha(path):
            raise ValueError(f'Preflight not anchored to frozen protocol: {path}')
    scores = pd.read_parquet(preflight/'decision_candidates_scored.parquet')
    intents = pd.read_parquet(preflight/'selection_intents.parquet')
    # Reconstruct the complete intents; no future qualification mask allowed.
    order = ['fold','decision_session_date','policy','candidate_rank']
    pd.testing.assert_frame_equal(intents.sort_values(order).reset_index(drop=True),
        selection_ledger(scores,cfg).sort_values(order).reset_index(drop=True))
    if scores.decision_session_date.gt('2025-12-31').any() or intents.future_label_used.any():
        raise ValueError('Reserved confirmation or future selection')
    return cfg, scores, intents, report


def build_shared(scores, cfg, archive, fold, repairs=None):
    group = scores[scores.fold.eq(fold)]
    calendar = get_market_calendar('FR_EQ')
    start = date.fromisoformat(group.decision_session_date.min())
    last = date.fromisoformat(group.decision_session_date.max())
    # A valid supplier payment date can be much later than the H5 liquidation.
    # Calendar extends only for settlement lookup; prices/performance stay in 2025.
    session_objects = [s for s in calendar.sessions(start, date(2026,1,15)) if s.is_open]
    days = [s.session_date.isoformat() for s in session_objects]
    end_index = days.index(last.isoformat())+cfg['horizon']
    # Extra cashflow sessions do not admit new candidates or inspect 2026.
    end = days[end_index]
    archives, instruments, events, hashes = {}, {}, [], {}
    for uid, frame in group.groupby('research_uid',sort=True):
        symbol = frame.provider_symbol.iloc[0]
        meta_path = archive/'symbols'/f'{hashlib.sha256(symbol.encode()).hexdigest()[:16]}.json'
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        instruments[uid] = {'isin':meta['record']['Isin'],'ticker':symbol}
        archives[uid] = repair_prices(_load_symbol_bars(archive,symbol),symbol,repairs)
        hashes[symbol] = {k:meta['payloads'][k]['sha256'] for k in ('eod','div','splits')}
        for kind, source in [('DIVIDEND','div'),('SPLIT','splits')]:
            for row in _rows(archive,meta,source):
                ex = row['date']
                if not start.isoformat() <= ex <= end:
                    continue
                event = {'id':f'{uid}/{kind}/{ex}','uid':uid,'session':ex,'kind':kind,
                         'supplier_assumption_accepted':True,'evidence':'EODHD_ARCHIVE_ASSUMPTION_NOT_OFFICIAL'}
                if kind == 'DIVIDEND':
                    row,supplement=repair_dividend(row,symbol,repairs)
                    if supplement:
                        event['evidence']=supplement['state']+':'+supplement['source_path']
                    problems = dividend_check(row)
                    payment = row.get('paymentDate')
                    if not problems and payment:
                        future = [d for d in days if d >= payment]
                        if not future or future[0] > '2025-12-31':
                            problems.append('PAYMENT_OUTSIDE_SUPPORTED_CALENDAR')
                        else:
                            event.update(cash_per_share=row['unadjustedValue'],currency='EUR',payment_session=future[0])
                            end_index = max(end_index,days.index(future[0]))
                    if problems:
                        event['kind'] = 'UNSUPPORTED_DIVIDEND_FIELDS'
                        event['problems'] = problems
                else:
                    try:
                        n,d = row['split'].split('/')
                        event.update(numerator=int(n),denominator=int(d))
                    except (ValueError,KeyError):
                        event['kind'] = 'UNSUPPORTED_SPLIT_RATIO'
                events.append(event)
    sessions = days[:end_index+1]
    if sessions[-1] > '2025-12-31':
        raise ValueError('Confirmation reserved')
    bars = {}
    for day in sessions:
        bars[day] = {}
        for uid, rows in archives.items():
            row = rows.get(day)
            if row is not None:
                bars[day][uid] = {'open':row.get('open'),'close':row.get('close'),
                    'tradable':float(row.get('volume') or 0)>0,
                    'supplier_assumption_accepted':True,'evidence':'EODHD_UNADJUSTED_ASSUMED_EXECUTABLE_NOT_VERIFIED'}
            # Honor stronger public no-opening evidence; never use the EOD proxy as a fill.
            if instruments[uid]['ticker']=='ARTO.PA' and day=='2024-10-10':
                bars[day][uid] = {'open':None,'close':(row or {}).get('close'),
                    'tradable':False,'supplier_assumption_accepted':True,
                    'evidence':'PUBLIC_ARTO_NO_OPENING_2024-10-10',
                    'opening_execution':{'status':'NO_OPENING_TRANSACTION',
                        'evidence':'artifacts/fr/research/opening_evidence_overlay/artois-20261004'}}
    decisions = {s.session_date.isoformat():s.open_at_utc.isoformat() for s in session_objects if s.session_date.isoformat() in sessions}
    settlements = {d:{'date':days[days.index(d)+2],'evidence':'ASSUMED_CALENDAR_T_PLUS_2_NOT_OBSERVED_SETTLEMENT'} for d in sessions}
    return {'schema_version':1,'market_code':'FR_EQ','currency':'EUR',
        'evidence_state':'EXPLORATORY_PROVIDER_ASSUMED','fold':fold,
        'horizon':cfg['horizon'],'max_positions':cfg['portfolio']['max_positions'],
        'initial_equity':str(cfg['portfolio']['initial_equity']),
        'canonical_writes_enabled':False,'serving_enabled':False,
        'sessions':sessions,'calendar_evidence':'LIBRARY_XPAR_RESEARCH_CALENDAR',
        'instruments':instruments,'bars':bars,'events':events,'settlements':settlements,
        'decision_at':decisions,'entry_at':decisions,
        'corporate_action_coverage':{u:{'from':sessions[0],'to':sessions[-1],
            'supplier_assumption_accepted':True,'evidence':'PROVIDER_EVENT_LIST_ASSUMED_COMPLETE_NOT_PROOF_OF_ABSENCE'} for u in instruments}}, hashes


def run(output: Path, config_path: Path):
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    if config['profile']!='EXPLORATORY_PROVIDER_ASSUMED' or config['serving_enabled'] or config['canonical_writes']:
        raise ValueError('Exploratory only')
    if config['tax_scenarios'] != ['unknown_untaxed','unknown_taxed'] or config['cost_scenarios'] != {'nominal':1,'stress_execution_x2':2}:
        raise ValueError('Versioned tax/cost scenarios must not change silently')
    cfg,scores,intents,frozen = load_frozen(config)
    output.mkdir(parents=True,exist_ok=False)
    protocol = {'config':config,'inherited':cfg,'input_hashes':frozen['input_hashes'],
                'local_hashes':{str(p):sha(p) for p in (config_path,Path(__file__),
                    Path('service/fr/provider_exploratory_engine_13b.py'),Path('service/fr/provider_exploratory_metrics_13b.py'),
                    Path(config['tax_review']),Path(config['cost_profile']))}}
    repairs=None
    if config.get('repair_overlay'):
        path=Path(config['repair_overlay'])
        repairs=json.loads(path.read_text(encoding='utf-8'))
        if repairs['state']!='EXPLORATORY_ONLY_NOT_QUALIFIED':
            raise ValueError('Repair source qualification must not be promoted')
        protocol['local_hashes'][str(path)]=sha(path)
        for item in repairs.get('prices',[])+repairs.get('dividends',[]):
            source=Path(item['source_path'])
            if sha(source)!=item['source_sha256']:
                raise ValueError('Repair source hash mismatch')
            protocol['local_hashes'][str(source)]=sha(source)
            for reference in item.get('references',[]):
                if sha(Path(reference['path']))!=reference['sha256']:
                    raise ValueError('Supplement reference hash mismatch')
                protocol['local_hashes'][reference['path']]=reference['sha256']
    write_json(output/'protocol.json',protocol)  # Written BEFORE any economic result.
    tax = pd.read_parquet(config['tax_review'])
    known = {f'{r.symbol}/{r.year}':True for r in tax.itertuples() if r.status.startswith('POSITIVE_')}
    costs = load_cost_profile(Path(config['cost_profile']))
    cells = []
    report = {'status':'RUNNING_EXPLORATORY','economic_go_allowed':False,'serving_enabled':False,
              'canonical_writes':False,'models_refit':0,'confirmation_2026_evaluated':False,
              'population_preserved':True,'policy_ranks_preserved':True,'candidate_paths':len(scores),'cells':cells}
    for fold in cfg['folds']:
        shared,hashes = build_shared(scores,cfg,Path(config['archive']),fold,repairs)
        if repairs:
            for repair in repairs.get('prices',[]):
                for uid,instrument in shared['instruments'].items():
                    if instrument['ticker']==repair['symbol'] and repair['date'] in shared['bars']:
                        shared['bars'][repair['date']][uid]['evidence']=repair['evidence']
        write_json(output/f'fold-{fold}-supplier-shared.json',shared)
        write_json(output/f'fold-{fold}-payload-hashes.json',hashes)
        for policy in cfg['policies']:
            selected = intents[intents.fold.eq(fold)&intents.policy.eq(policy)]
            tape = dict(shared)
            availability = scores[scores.fold.eq(fold)].set_index(['decision_session_date','research_uid']).max_input_available_at
            tape['candidates'] = [{'session':r.decision_session_date,'uid':r.research_uid,'rank':int(r.candidate_rank),
                                   'available_at':availability.loc[(r.decision_session_date,r.research_uid)]} for r in selected.itertuples()]
            for tax_name in config['tax_scenarios']:
                for cost_name,multiplier in config['cost_scenarios'].items():
                    cell = {'fold':fold,'policy':policy,'tax_scenario':tax_name,'cost_scenario':cost_name,
                            'intentions':len(selected),'metrics':None}
                    name = f'{fold}-{policy}-{tax_name}-{cost_name}'
                    try:
                        result = replay_assumed(tape,costs,{'known_positive':known,'unknown_liable':tax_name=='unknown_taxed'},
                                                stress_multiplier=Decimal(str(multiplier)))
                        cell['status'] = result['status']
                        cell['metrics'] = ledger_metrics(result,data_kind='EXPLORATORY_PROVIDER_ASSUMED')
                    except ReplayBlocked as exc:
                        result = {'status':'BLOCKED_EXPLORATORY_CELL','reason':str(exc),'ledger':exc.ledger}
                        cell.update(status=result['status'],reason=str(exc))
                    write_json(output/f'{name}-ledger.json',result)
                    cells.append(cell)
                    write_json(output/'progress.json',{'completed_cells':len(cells),'planned_cells':24,'last_cell':cell})
                    print(f'{name}: {cell["status"]}',flush=True)
    report['status'] = 'COMPLETED_EXPLORATORY_NOT_QUALIFIED'
    report['completed_performance_cells'] = sum(c['metrics'] is not None for c in cells)
    report['blocked_cells'] = sum(c['metrics'] is None for c in cells)
    report['comparison_state'] = 'INCOMPLETE_BLOCKED_NO_POLICY_RANKING' if report['blocked_cells'] else 'EXPLORATORY_ONLY_NOT_QUALIFIED'
    report['output_hashes'] = {p.name:sha(p) for p in sorted(output.glob('*.json')) if p.name!='report.json'}
    write_json(output/'report.json',report)
    return report
