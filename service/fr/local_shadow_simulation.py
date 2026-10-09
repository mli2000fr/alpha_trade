"""Explicit local, unqualified FR research shadow. No SQL, broker or training.

A retrospective technical replay is never marked prospective. The production
preflight remains blocked; scores cannot authorize an order or imply direction.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, date, datetime
import hashlib
import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from common.market_calendar import get_market_calendar
from modelFactory.fr_oracle_h5_pilot import deterministic_score, feature_matrix
from service.fr.daily_feature_adapter_16b import (
    action_checks, identity_resolution, master_at, observed_payloads, select_bars,
)
from service.fr.feature_parity_16g import parity
from service.fr.prediction_contract_16a import ROOT, FEATURES, aware, prepare_manifest, scoped_path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def implementation_hashes():
    base = Path(__file__).resolve().parents[2]
    return {relative:digest(base/relative) for relative in (
        'service/fr/local_shadow_simulation.py', 'service/fr/daily_feature_adapter_16b.py',
        'service/fr/feature_parity_16g.py', 'modelFactory/fr_feature_panel.py',
        'modelFactory/fr_oracle_h5_pilot.py')}


def read_subset(path, manifest):
    payload = json.loads(path.read_text(encoding='utf-8'))
    if (payload.get('market_code') != 'FR_EQ' or payload.get('serving_enabled') is not False
            or payload.get('historical_selection_allowed') is not False):
        raise ValueError('FR research subset required')
    indexed = {r['research_uid']: r for r in manifest['universe']}
    rows = payload.get('instruments', [])
    if len(rows) != 164 or len({r['research_uid'] for r in rows}) != 164:
        raise ValueError('Exactly 164 unique frozen identities required')
    for row in rows:
        original = indexed.get(row['research_uid'])
        if (not original or row.get('resolved_mic') != 'XPAR' or
                row.get('orders_allowed') is not False or row.get('shadow_eligible') is not False or
                row.get('observed_provider_feature_inputs_usable') is not True or
                any(row.get(k) != original[k] for k in ('research_uid','isin')) or
                row.get('symbol') != original['provider_symbol']):
            raise ValueError('Subset identity or XPAR qualification mismatch')
    return payload, rows


def rank_scores(rows, probabilities, day, *, fraction=.20):
    probabilities = np.asarray(probabilities, dtype=float)
    if (probabilities.shape != (len(rows),) or not np.isfinite(probabilities).all()
            or ((probabilities < 0) | (probabilities > 1)).any()):
        raise ValueError('Invalid model scores')
    ranked = [{**row, 'oracle_score_raw': float(score),
        'tie': deterministic_score(str(day), row['research_uid'], 17)}
        for row, score in zip(rows, probabilities, strict=True)]
    ranked.sort(key=lambda r: (-r['oracle_score_raw'], -r['tie'], r['research_uid']))
    count = math.ceil(len(ranked)*fraction)
    for index, row in enumerate(ranked, 1):
        row.update(rank=index, selected_top20=index <= count)
        row.pop('tie')
    return ranked


def validate_protocol(protocol, manifest, source, bootstrap):
    required = {'schema_version':1,'market_code':'FR_EQ','purpose':'LOCAL_UNQUALIFIED_SHADOW',
        'universe_count':164,'mic':'XPAR','oracle_horizon':5,'selection_fraction':.20,
        'minimum_cross_section':20,'seed':17,'orders_allowed':False,'sql_writes':False,
        'serving_allowed':False,'training_allowed':False}
    if any(protocol.get(k) != v or type(protocol.get(k)) != type(v) for k,v in required.items()):
        raise ValueError('Local shadow protocol modified or unsafe')
    if (protocol['source_sha256'] != digest(source) or protocol['model_manifest'] != manifest
            or protocol['bootstrap_dir'] != str(bootstrap.relative_to(ROOT)).replace('\\','/')
            or protocol.get('implementation_sha256') != implementation_hashes()):
        raise ValueError('Frozen source/model/bootstrap lineage changed')
    calendar = get_market_calendar('FR_EQ', allow_us_weekday_fallback=False)
    cutoff = calendar.session(date.fromisoformat(protocol['decision_date'])).open_at_utc
    if aware(protocol['frozen_at']) >= cutoff:
        raise ValueError('Protocol must precede prospective decision')


def write(output, name, payload):
    (output/(name+'.json')).write_text(json.dumps(payload, ensure_ascii=False,
        indent=2, allow_nan=False, default=lambda v: v.isoformat()), encoding='utf-8')


def run(*, phase, output, subset, bootstrap, decision_day=None, protocol_path=None):
    now = datetime.now(UTC)
    output = output.resolve()
    base = (ROOT/'artifacts/fr/research/local_shadow_simulation').resolve()
    if output == base or not output.is_relative_to(base) or output.exists():
        raise ValueError('New isolated FR local_shadow_simulation directory required')
    source, bootstrap = (scoped_path(str(p), ROOT) for p in (subset, bootstrap))
    manifest = prepare_manifest()
    source_payload, targets = read_subset(source, manifest)
    calendar = get_market_calendar('FR_EQ', allow_us_weekday_fallback=False)
    if phase == 'freeze':
        cutoff = calendar.session(decision_day).open_at_utc
        if not now < cutoff or aware(source_payload['audit_at']) > now:
            raise ValueError('Freeze must be genuinely before future decision')
        protocol = {'schema_version':1,'market_code':'FR_EQ','purpose':'LOCAL_UNQUALIFIED_SHADOW',
            'frozen_at':now.isoformat(),'decision_date':str(decision_day),
            'source_path':str(source.relative_to(ROOT)).replace('\\','/'),
            'source_sha256':digest(source),'bootstrap_dir':str(bootstrap.relative_to(ROOT)).replace('\\','/'),
            'implementation_sha256':implementation_hashes(),
            'model_manifest':manifest,'universe_count':164,'mic':'XPAR','oracle_horizon':5,
            'selection_fraction':.20,'minimum_cross_section':20,'seed':17,
            'orders_allowed':False,'sql_writes':False,'serving_allowed':False,'training_allowed':False,
            'status':'FROZEN_WAITING_FOR_DECISION_AND_DATA'}
        output.mkdir(parents=True, exist_ok=False)
        write(output, 'protocol', protocol)
        return protocol
    prospective = phase == 'prospective'
    if prospective:
        protocol_path = scoped_path(str(protocol_path), ROOT)
        protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
        validate_protocol(protocol, manifest, source, bootstrap)
        decision_day = date.fromisoformat(protocol['decision_date'])
    cutoff = calendar.session(decision_day).open_at_utc
    if cutoff > now:
        raise ValueError('Decision not yet reached; no early prospective inference')
    if prospective and aware(source_payload['audit_at']) >= cutoff:
        raise ValueError('Subset unavailable before prospective decision')
    feature_day = calendar.previous_session(decision_day)
    sessions = calendar.session_dates(calendar.previous_session(feature_day, 20), feature_day)
    proofs, bars, actions, errors = {}, [], [], []
    for folder, destination in (
            (ROOT/'artifacts/fr/operations/eodhd_daily', bars), (bootstrap/'eodhd_daily',bars),
            (ROOT/'artifacts/fr/operations/fr_corporate_actions_sync', actions),
            (bootstrap/'corporate_actions', actions)):
        found, issues = observed_payloads(folder, cutoff, ROOT, proofs)
        destination.extend(found)
        errors.extend(issues)
    master, common_reserves, master_errors = master_at(
        ROOT/'artifacts/fr/operations/fr_security_master_sync', cutoff, feature_day, ROOT, proofs)
    errors.extend(master_errors)
    indexed = {r['research_uid']:r for r in manifest['universe']}
    accepted, excluded = [], []
    for target in targets:
        identity = indexed[target['research_uid']]
        reasons = []
        try:
            resolution = identity_resolution(master, identity, feature_day)
            reasons.extend(resolution['reasons'])
            if resolution['mic'] != 'XPAR':
                reasons.append('NOT_XPAR_AT_FEATURE_SESSION')
            reasons.extend(r for r in common_reserves if r != 'MASTER_CONTINUITY_UNQUALIFIED')
            selected, missing = select_bars(bars, target['symbol'], sessions, calendar, cutoff)
            if missing:
                reasons.append('INCOMPLETE_21_SESSION_WARMUP')
            reasons.extend(action_checks(actions, target['symbol'], sessions))
            if not reasons:
                checked = parity(selected, sessions)
                if checked['raw_mismatches'] or checked['transformed_mismatches']:
                    reasons.append('FEATURE_ARITHMETIC_PARITY_FAILURE')
            if errors:
                reasons.append('ARCHIVE_INTEGRITY_ERRORS')
            if not reasons:
                accepted.append({'symbol':target['symbol'],'isin':target['isin'],
                    'research_uid':target['research_uid'],'mic':'XPAR',
                    'feature_session':str(feature_day),'values':checked['adapter_raw'],
                    'input_available_at':max(r['available_at'] for r in selected).isoformat(),
                    'input_payload_sha256s':sorted({r['raw_sha256'] for r in selected}),
                    'release_reserves':sorted(set(common_reserves+target['release_reserves']))})
        except (ValueError, KeyError, TypeError) as exc:
            reasons.append('INVALID_INPUT: '+str(exc)[:140])
        if reasons:
            excluded.append({'symbol':target['symbol'],'reasons':sorted(set(reasons))})
    ranked = []
    if len(accepted) >= manifest['min_cross_section']:
        model_proof = manifest['evidence'][-2]
        model_path = scoped_path(model_proof['path'], ROOT)
        # Only the curated, hash-pinned local training artefact is deserialized.
        if digest(model_path) != model_proof['sha256']:
            raise ValueError('Model hash mismatch before local deserialization')
        model = joblib.load(model_path)
        matrix = feature_matrix(pd.DataFrame([r['values'] for r in accepted]))
        if list(model.feature_names_in_) != list(FEATURES) or list(model.classes_) != [0,1]:
            raise ValueError('Model feature/class schema mismatch')
        with threadpool_limits(limits=2):
            probabilities = model.predict_proba(matrix)[:,1]
        ranked = rank_scores(accepted, probabilities, decision_day)
    report = {'schema_version':1,'market_code':'FR_EQ','purpose':'LOCAL_UNQUALIFIED_SHADOW',
        'status':('PROSPECTIVE_LOCAL_RESEARCH_SCORED' if prospective else
                  'RETROSPECTIVE_TECHNICAL_REPLAY_SCORED') if ranked else 'BLOCKED_INPUTS_NO_SCORES',
        'created_at':datetime.now(UTC).isoformat(),'decision_at':cutoff.isoformat(),
        'decision_lag_seconds':(now-cutoff).total_seconds(),
        'scores_available_at_decision':False,
        'feature_session':str(feature_day),'required_sessions':[str(d) for d in sessions],
        'subset_frozen_before_decision':aware(source_payload['audit_at']) < cutoff,
        'prospective':prospective,'historical_selection_pit':prospective,
        'universe_count':164,'scored_count':len(ranked),'excluded_count':len(excluded),
        'selected_top20_count':sum(r['selected_top20'] for r in ranked),
        'oracle_horizon':5,'score_semantics':'UNCALIBRATED_AMPLITUDE_SCORE_NOT_LONG_SHORT',
        'model_manifest':manifest,'subset_sha256':digest(source),
        'implementation_sha256':implementation_hashes(),
        'protocol_sha256':digest(protocol_path) if prospective else None,
        'archive_errors':errors,'proofs_sha256':proofs,'common_release_reserves':common_reserves,
        'exclusion_reason_counts':dict(Counter(r for e in excluded for r in e['reasons'])),
        'independent_qualification_granted':False,'sql_writes':False,'training_launched':False,
        'orders_allowed':False,'serving_allowed':False,'performance_evaluated':False}
    output.mkdir(parents=True, exist_ok=False)
    for name,payload in [('report',report),('scores',ranked),('exclusions',excluded),
                         ('top20',[r for r in ranked if r['selected_top20']])]:
        write(output,name,payload)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('freeze','replay','prospective'),required=True)
    parser.add_argument('--decision-date',type=date.fromisoformat)
    parser.add_argument('--protocol',type=Path)
    parser.add_argument('--subset',type=Path,required=True)
    parser.add_argument('--bootstrap-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    if (args.phase=='prospective' and not args.protocol) or (args.phase!='prospective' and not args.decision_date):
        parser.error('Decision date required for freeze/replay; frozen protocol required for prospective')
    report = run(phase=args.phase,output=args.output_dir,subset=args.subset,
        bootstrap=args.bootstrap_dir,decision_day=args.decision_date,protocol_path=args.protocol)
    print(json.dumps({k:report[k] for k in ('status','universe_count','scored_count',
        'excluded_count','selected_top20_count','orders_allowed') if k in report}))


if __name__ == '__main__':
    main()
