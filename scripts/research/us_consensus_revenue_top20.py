"""Separate frozen TOP20% revenue-only cohort; no prices, fit, API or SQL writes."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from sqlalchemy import bindparam, text

from scripts.research.us_consensus_revenue_only import check_row, revision, known_metadata
from scripts.research.us_consensus_observed_revision_pilot import utc, payload_hash, connect_readonly, BATCH
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_directional_information_readiness import UNIVERSE
from common.universe_files import load_universe_file_symbols

PARENT = Path('artifacts/research/us_consensus_revenue_only/20261019-v1')
SOURCE = Path('artifacts/research/us_directional_information/20261019-v2/observed-revisions-v1')
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))


def rank_cohort(scores, prior, cutoff, universe):
    """Denominator = finite, causal scores in the frozen universe, not consensus coverage."""
    f = scores[pd.to_datetime(scores.prediction_date).eq(prior)].copy()
    if f.empty:
        return f.assign(oracle_rank=pd.Series(dtype=int), arm=pd.Series(dtype=str)), 0
    if f.symbol.duplicated().any():
        raise ValueError('Duplicate Oracle symbol')
    if not (f.batch_id.eq(BATCH) & f.target_name.eq('oracle_path_extreme20') & f.target_horizon.eq(20)).all():
        raise ValueError('Wrong Oracle model or target')
    if not pd.to_datetime(f.model_available_date).lt(pd.to_datetime(f.prediction_date)).all():
        raise ValueError('Model unavailable before prediction')
    if f.model_sha256.isna().any() or f.model_sha256.nunique()!=1 or f.feature_profile_sha256.nunique()!=1:
        raise ValueError('Ambiguous model lineage')
    values=pd.to_numeric(f.proba_extreme,errors='coerce')
    if not (np.isfinite(values) & values.between(0,1)).all():
        raise ValueError('Invalid Oracle probability')
    f=f[f.symbol.isin(universe) & pd.to_datetime(f.created_at,utc=True).lt(cutoff)]
    n=len(f)
    if n<20:
        return f.iloc[:0].assign(oracle_rank=pd.Series(dtype=int),arm=pd.Series(dtype=str)), n
    f=f.sort_values(['proba_extreme','symbol'],ascending=[False,True]).head(math.ceil(n*.2))
    f['oracle_rank']=range(1,len(f)+1)
    f['arm']=np.where(f.oracle_rank.le(10),'TOP10','RANK11_TO_TOP20_PERCENT')
    return f,n


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():
        raise ValueError('Fresh output directory required')
    old=READ(PARENT/'protocol.json')
    verify_hashes(Path('.'),old['sources'])
    verify_hashes(PARENT,READ(PARENT/'report.json')['files'])
    if not READ(PARENT/'final-audit.json')['status'].startswith('PASS_'):
        raise ValueError('Parent pilot not audited')
    files=[Path(__file__),Path('tests/test_us_consensus_revenue_top20.py'),
        Path('scripts/research/us_consensus_revenue_only.py'),
        Path('scripts/research/us_consensus_revenue_only_audit.py'),
        Path('scripts/research/us_consensus_observed_revision_pilot.py'),UNIVERSE,
        PARENT/'protocol.json',PARENT/'report.json',PARENT/'final-audit.json',PARENT/'qualified-features.parquet',
        SOURCE/'oracle-scores.parquet',SOURCE/'consensus.parquet',SOURCE/'runs.parquet']
    root.mkdir(parents=True)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),parent=str(PARENT),source=str(SOURCE),
        sources={str(p):digest(p) for p in files},oracle_batch=BATCH,
        scope='TOP20_PERCENT ceil(0.20*N) of exact prior-session causal Oracle scores in frozen tradable file; fixed membership BEFORE consensus eligibility, no replacement.',
        arms=['TOP10','RANK11_TO_TOP20_PERCENT','ALL_TOP20_PERCENT_DESCRIPTIVE_OVERLAPPING_UNION'],
        hypothesis='Identical frozen revenue-only rule: 0q same issuer/quarter; strict up LONG, down SHORT, stable/missing abstain. No EPS.',
        pairing='Reuse immutable decision-to-decision features of 11-18Oct receipts; availability max(row receipts, completed run finish) before successive NYSE opens.',
        qualification='Raw envelopes for ALL selected comparable pairs; >=3 revenue analysts at each end, unchanged count primary, changed count separate; currency/fiscal support only as documented, no blanket USD.',
        metadata='DOCN/FUN Q3 only supported in frozen dossier; latest fiscal anchor for others is an unverified candidate, not evidence of an unannounced current period.',
        evaluation='TP10 before SL5, ten NYSE sessions from entry open, expiry tenth close, gap-aware and loss-first intraday ambiguity. Same costs/reference arms later. No outcomes read now.',
        inference='New exploratory scope after inspecting TOP10 features, not a fresh independent confirmation. More stocks do not add entry dates; clustering by date/issuer, nonoverlapping episodes required.',
        future_confirmation='At least50 NEW entry sessions after protocol and100 nonoverlapping qualified episodes; TOP10 requirement remains separate. No promotion from the larger scope to TOP10.',
        proof_scope='SELECT existing eodhd_consensus_snapshot /calendar/trends envelopes for selected row run/timestamps; UTC READ ONLY REPEATABLE READ thenROLLBACK.',
        no_outputs=['prices or performance','training','supplier or LLM calls','SQL writes','production changes','orders'],
        api_calls=0,llm_calls=0,sql_writes=False,training=False,orders=False)
    atomic_json(root/'protocol.json',p)
    return p


def build(root):
    prepare(root)
    if (root/'build-ready.json').exists():
        raise ValueError('Immutable cohort')
    base=pd.read_parquet(PARENT/'qualified-features.parquet')
    scores=pd.read_parquet(SOURCE/'oracle-scores.parquet')
    universe=set(load_universe_file_symbols('universe-file:'+UNIVERSE.as_posix()))
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2026-10-01',end_date='2026-11-20')
    frames=[];coverage=[]
    for entry in schedule.loc['2026-10-12':'2026-10-19'].index:
        position=schedule.index.get_loc(entry);prior=schedule.index[position-1];cutoff=schedule.loc[entry].market_open
        ranked,n=rank_cohort(scores,prior,cutoff,universe)
        coverage.append(dict(entry_date=entry,prior_session=prior,eligible_scores=n,selected=len(ranked),
            status='AVAILABLE' if len(ranked) else 'MISSING_PRIOR_SESSION_ORACLE'))
        if ranked.empty:
            continue
        cohort=ranked[['symbol','proba_extreme','oracle_rank','arm','prediction_date','created_at']].copy()
        cohort['entry_date']=entry
        prior_features=base[base.entry_date.eq(entry)].drop(columns=['oracle_rank','in_top10'])
        cohort=cohort.merge(prior_features,on=['entry_date','symbol'],how='left',validate='one_to_one',indicator=True)
        cohort['pair_present']=cohort.pop('_merge').eq('both')
        cohort['maturity_utc']=schedule.iloc[position+9].market_close
        # The membership remains complete even when consensus has no comparable pair.
        frames.append(cohort)
    if not frames:
        raise ValueError('No contemporaneous Oracle cohort in frozen source')
    frame=pd.concat(frames,ignore_index=True)
    frame.to_parquet(root/'cohort.parquet',index=False)
    source=pd.read_parquet(SOURCE/'consensus.parquet')
    present=frame[frame.pair_present]
    ids=sorted(set(present.old_id.astype(int))|set(present.new_id.astype(int)))
    request=source[source.id.isin(ids)][['run_id','observed_at']].drop_duplicates()
    atomic_json(root/'proof-request.json',dict(row_ids=ids,receipts=request.to_dict('records')))
    atomic_json(root/'oracle-coverage.json',dict(rows=coverage))
    atomic_json(root/'build-ready.json',dict(files={n:digest(root/n) for n in
        ['cohort.parquet','proof-request.json','oracle-coverage.json']}))
    print(json.dumps(dict(cohort_rows=len(frame),comparable_pairs=len(present),proof_rows=len(ids))),flush=True)


def proofs(root):
    prepare(root);verify_hashes(root,READ(root/'build-ready.json')['files'])
    if (root/'proof-ready.json').exists():
        raise ValueError('Immutable raw proofs')
    request=READ(root/'proof-request.json')
    runids=sorted({r['run_id'] for r in request['receipts']})
    stamps=sorted({utc(r['observed_at']).tz_localize(None).to_pydatetime() for r in request['receipts']})
    engine,conn=connect_readonly()
    try:
        query=text('''SELECT id,run_id,observed_at,available_at,http_status,payload_hash,payload_json
            FROM pit_raw_payloads WHERE batch_name='eodhd_consensus_snapshot'
            AND provider='eodhd' AND endpoint='/calendar/trends'
            AND run_id IN :runs AND observed_at IN :stamps ORDER BY id''').bindparams(
                bindparam('runs',expanding=True),bindparam('stamps',expanding=True))
        records=[dict(r) for r in conn.execute(query,dict(runs=runids,stamps=stamps)).mappings()]
        conn.rollback()
    finally:
        conn.close();engine.dispose()
    pd.DataFrame(records).to_parquet(root/'raw-receipts.parquet',index=False)
    atomic_json(root/'proof-ready.json',dict(envelopes=len(records),files={'raw-receipts.parquet':digest(root/'raw-receipts.parquet')}))
    print('Archived envelopes',len(records),flush=True)


def receipt_index(records):
    index={};bad=[]
    for row in records:
        try:
            obj=json.loads(row['payload_json']);available=utc(row['available_at']);observed=utc(row['observed_at'])
            if row['http_status']!=200 or payload_hash(obj)!=row['payload_hash'] or available is None or observed is None or available<observed:
                raise ValueError('Invalid envelope')
            for group in obj.get('trends',[]):
                for item in group:
                    key=(row['run_id'],observed,payload_hash(item))
                    index[key]=min(index.get(key,available),available)
        except (TypeError,ValueError,KeyError):
            bad.append(int(row['id']))
    return index,bad


def qualify(frame,source,runs,receipts):
    index,bad=receipt_index(receipts)
    lookup={int(r['id']):r for r in source.to_dict('records')}
    rows=[]
    for row in frame.to_dict('records'):
        reasons=[];verified=False;pattern='ABSTAIN';count_group='NO_PAIR'
        metadata=known_metadata(row['symbol'],str(row.get('fiscal_anchor')))
        if not row['pair_present']:
            reasons.append('MISSING_COMPARABLE_0Q_PAIR')
        else:
            old,new=lookup[int(row['old_id'])],lookup[int(row['new_id'])]
            a,b=check_row(old,runs),check_row(new,runs)
            rev=revision(old,new);pattern=rev['pattern'];count_group=rev['count_group']
            reasons+=a['reasons']+b['reasons']+rev['reasons']
            if a['available_at'] is None or b['available_at'] is None or not a['available_at']<row['prior_entry_open_utc'] or not b['available_at']<row['entry_open_utc']:
                reasons.append('AFTER_DECISION_CUTOFF')
            keys=[(r['run_id'],utc(r['observed_at']),r['raw_hash']) for r in (old,new)]
            verified=all(key in index and index[key]<cutoff for key,cutoff in zip(keys,[row['prior_entry_open_utc'],row['entry_open_utc']]))
            if not verified:
                reasons.append('RAW_ENVELOPE_NOT_VERIFIED_BEFORE_DECISION')
            if count_group!='UNCHANGED_COUNT':
                reasons.append('REVENUE_ANALYSTS_'+count_group)
        if not metadata['currency_supported']:
            reasons.append('CURRENCY_NOT_VERIFIED')
        if not metadata['period_supported']:
            reasons.append('FISCAL_PERIOD_NOT_VERIFIED')
        rows.append({**row,**metadata,'envelope_verified':verified,'count_group':count_group,
            'numeric_pattern':pattern,'qualified_pattern':pattern if not reasons else 'ABSTAIN',
            'supported_research_feature':not reasons,'reservation_reasons':sorted(set(reasons)),
            'live_admission':False,'definition_known_before_entry':False})
    return pd.DataFrame(rows),bad


def arm_summary(frame):
    good=frame[frame.pair_present]
    technical=good[good.technical_pair.eq(True)]
    strata=technical.groupby(['count_group','numeric_pattern']).size()
    return dict(selected=len(frame),comparable_pairs=len(good),missing_pairs=len(frame)-len(good),
        technical_pairs=len(technical),
        numeric_patterns=good.numeric_pattern.value_counts().to_dict(),
        count_strata={f'{a}:{b}':int(n) for (a,b),n in strata.items()},
        envelope_verified=int(frame.envelope_verified.sum()),
        supported_features=int(frame.supported_research_feature.sum()),
        qualified_patterns=frame.qualified_pattern.value_counts().to_dict())


def finalize(root):
    p=prepare(root)
    if (root/'report.json').exists():
        raise ValueError('Immutable completed extension')
    for name in ('build-ready.json','proof-ready.json'):
        verify_hashes(root,READ(root/name)['files'])
    frame=pd.read_parquet(root/'cohort.parquet');source=pd.read_parquet(SOURCE/'consensus.parquet')
    runs={r['run_id']:r for r in pd.read_parquet(SOURCE/'runs.parquet').to_dict('records')}
    qualified,bad=qualify(frame,source,runs,pd.read_parquet(root/'raw-receipts.parquet').to_dict('records'))
    qualified.to_parquet(root/'qualified-cohort.parquet',index=False)
    # Human-readable inventory, no outcome prices or inferred trading advice.
    columns=['entry_date','symbol','oracle_rank','arm','pair_present','fiscal_anchor','old_revenue','new_revenue',
        'relative','old_count','new_count','numeric_pattern','qualified_pattern','reservation_reasons']
    qualified[columns].sort_values(['entry_date','oracle_rank']).to_csv(root/'cohort.csv',index=False)
    signals=qualified[qualified.qualified_pattern.ne('ABSTAIN')]
    arms={arm:arm_summary(qualified[qualified.arm.eq(arm)]) for arm in ['TOP10','RANK11_TO_TOP20_PERCENT']}
    arms['ALL_TOP20_PERCENT']=arm_summary(qualified)
    reservations=qualified.explode('reservation_reasons').reservation_reasons.dropna().value_counts().to_dict()
    result=dict(status='TOP20_PERCENT_EXTENSION_COMPLETED_NO_H10_EFFICACY_RESULT',
        protocol_asof_utc=p['created_at_utc'],cohorts=int(qualified.entry_date.nunique()),
        arms=arms,reservation_counts=reservations,bad_envelopes=bad,
        oracle_coverage=READ(root/'oracle-coverage.json')['rows'],
        evidence_envelopes=len(pd.read_parquet(root/'raw-receipts.parquet')),
        requested_proof_rows=len(READ(root/'proof-request.json')['row_ids']),
        supported_signals=signals[['symbol','entry_date','oracle_rank','arm','relative','qualified_pattern']].to_dict('records'),
        mature_h10_selected=int(pd.to_datetime(qualified.maturity_utc,utc=True).le(utc(p['created_at_utc'])).sum()),
        mature_h10_signals=int(pd.to_datetime(signals.maturity_utc,utc=True).le(utc(p['created_at_utc'])).sum()),
        earliest_h10_maturity=str(qualified.maturity_utc.min()),
        minimum_confirmation_met=False,scope_exploratory=True,prices_read=False,pnl_computed=False,
        api_calls=0,llm_calls=0,training=False,sql_writes=False,production_changes=False,orders=False,
        files={n:digest(root/n) for n in ['protocol.json','build-ready.json','proof-ready.json',
            'qualified-cohort.parquet','cohort.csv']})
    atomic_json(root/'report.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','oracle_coverage')},default=str),flush=True)


def audit(root):
    p=prepare(root);r=READ(root/'report.json')
    if (root/'audit.json').exists():
        raise ValueError('Immutable audit')
    verify_hashes(root,r['files'])
    source=pd.read_parquet(SOURCE/'consensus.parquet')
    lookup={int(x['id']):x for x in source.to_dict('records')}
    runs={x['run_id']:x for x in pd.read_parquet(SOURCE/'runs.parquet').to_dict('records')}
    frame=pd.read_parquet(root/'qualified-cohort.parquet');scores=pd.read_parquet(SOURCE/'oracle-scores.parquet')
    universe=set(load_universe_file_symbols('universe-file:'+UNIVERSE.as_posix()))
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2026-10-01',end_date='2026-11-20')
    assert not frame.duplicated(['entry_date','symbol']).any()
    for entry,group in frame.groupby('entry_date'):
        cutoff=schedule.loc[entry].market_open;pos=schedule.index.get_loc(entry);prior=schedule.index[pos-1]
        causal=scores[pd.to_datetime(scores.prediction_date).eq(prior)&pd.to_datetime(scores.created_at,utc=True).lt(cutoff)&scores.symbol.isin(universe)]
        expected=causal.sort_values(['proba_extreme','symbol'],ascending=[False,True]).head((len(causal)+4)//5)
        ordered=group.sort_values('oracle_rank')
        assert ordered.symbol.tolist()==expected.symbol.tolist()
        assert ordered.oracle_rank.tolist()==list(range(1,len(expected)+1))
        for row in ordered.itertuples():
            assert row.arm==('TOP10' if row.oracle_rank<=10 else 'RANK11_TO_TOP20_PERCENT')
            assert row.maturity_utc==schedule.iloc[pos+9].market_close
            assert not row.live_admission and not row.definition_known_before_entry
            if row.pair_present:
                a,b=lookup[int(row.old_id)],lookup[int(row.new_id)]
                for item,bound in [(a,row.prior_entry_open_utc),(b,row.entry_open_utc)]:
                    assert item['symbol']==row.symbol and item['horizon_raw']=='0q'
                    assert str(item['fiscal_period_end'])[:10]==row.fiscal_anchor
                    assert runs[item['run_id']]['status']=='COMPLETED'
                    available=max([utc(item[k]) for k in ('observed_at','available_at','ingestion_at')]+[utc(runs[item['run_id']]['finished_at'])])
                    assert available<bound
                if row.technical_pair:
                    delta=float(b['revenue_avg'])-float(a['revenue_avg'])
                    assert abs(delta-row.delta)<1e-8
                    assert row.numeric_pattern==('LONG' if delta>0 else 'SHORT' if delta<0 else 'ABSTAIN')
            else:
                assert row.qualified_pattern=='ABSTAIN'
            if row.supported_research_feature:
                assert row.symbol in ('DOCN','FUN') and row.fiscal_anchor=='2026-09-30'
                assert row.currency=='USD' and row.envelope_verified and row.count_group=='UNCHANGED_COUNT'
                assert row.old_count==row.new_count>=3
                assert len(row.reservation_reasons)==0
    assert sum(r['arms'][a]['selected'] for a in ('TOP10','RANK11_TO_TOP20_PERCENT'))==len(frame)
    assert r['arms']['ALL_TOP20_PERCENT']['selected']==len(frame)
    assert int(frame.qualified_pattern.ne('ABSTAIN').sum())==len(r['supported_signals'])
    assert r['mature_h10_selected']==r['mature_h10_signals']==0
    assert not r['prices_read'] and not r['pnl_computed'] and not r['bad_envelopes']
    result=dict(status='PASS_TOP20_PERCENT_COHORT_CAUSAL_FEATURES_NO_OUTCOMES',
        rows_checked=len(frame),report_sha256=digest(root/'report.json'),
        finished_at_utc=datetime.now(timezone.utc).isoformat(),same_assistant_review=True,
        human_independent_review=False,prices_read=False,sql_writes=False,training=False)
    atomic_json(root/'audit.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','build','proofs','finalize','audit'],required=True)
    args=parser.parse_args()
    globals()[args.phase](args.output)
