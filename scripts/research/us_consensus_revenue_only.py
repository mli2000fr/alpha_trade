"""Frozen revenue-only observed-snapshot pilot, no EPS, fit or SQL writes.

Decision-to-decision changes between last receipts BEFORE successive NYSE opens.
Current Oracle must predate entry and refer to prior session; never backfill
earlier membership from the sole Oct16 cohort. H10 outcomes remain separate.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from sqlalchemy import bindparam,text

from scripts.research.us_consensus_observed_revision_pilot import utc,payload_hash,connect_readonly
from scripts.research.us_directional_information_readiness import UNIVERSE
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from service.eodhd.consensus_snapshot import number
from service.eodhd.symbols import to_eodhd

PARENT=Path('artifacts/research/us_directional_information/20261019-v2/observed-revisions-v1')
SUPPORT=Path('doc/ml/sources/reponse_support_eodhd_trends_docn_fun_20261019.md')
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
FIELDS={'revenue_avg':'revenueEstimateAvg','revenue_low':'revenueEstimateLow',
    'revenue_high':'revenueEstimateHigh','revenue_analyst_count':'revenueEstimateNumberOfAnalysts'}


def check_row(r,runs):
    reasons=[]
    if r.get('provider')!='eodhd':reasons.append('WRONG_PROVIDER')
    try:
        raw=json.loads(r['raw_payload_json'])
        if payload_hash(raw)!=r['raw_hash']:reasons.append('RAW_HASH_MISMATCH')
        if raw.get('code')!=to_eodhd(r['symbol']) or raw.get('period')!='0q' or r['horizon_raw']!='0q' or str(raw.get('date'))!=str(r['fiscal_period_end'])[:10]:
            reasons.append('WRONG_RAW_PERIOD_OR_ISSUER')
        for k,native in FIELDS.items():
            a=number(raw.get(native),count=k.endswith('count'))
            b=None if pd.isna(r.get(k)) else float(r[k])
            if (a is None)!=(b is None) or (a is not None and not np.isclose(a,b,rtol=0,atol=1e-8)):
                reasons.append('NORMALIZED_REVENUE_MISMATCH:'+k)
    except (ValueError,TypeError,KeyError):reasons.append('INVALID_REVENUE_ITEM')
    lo,avg,hi=[r.get('revenue_'+k) for k in ('low','avg','high')]
    if avg is None or pd.isna(avg) or not np.isfinite(float(avg)) or avg<=0:reasons.append('MISSING_OR_NONPOSITIVE_REVENUE')
    if pd.notna(lo) and pd.notna(hi) and lo>hi:reasons.append('REVENUE_RANGE_INVALID')
    if pd.notna(avg) and ((pd.notna(lo) and avg<lo) or (pd.notna(hi) and avg>hi)):reasons.append('REVENUE_RANGE_INVALID')
    run=runs.get(r.get('run_id'),{});finished=utc(run.get('finished_at'))
    stamps=[utc(r.get(k)) for k in ('observed_at','available_at','ingestion_at')]+[finished]
    if run.get('status')!='COMPLETED' or any(x is None for x in stamps):reasons.append('RUN_OR_RECEIPT_UNQUALIFIED')
    elif stamps[1]<stamps[0] or finished<stamps[0]:reasons.append('NONCAUSAL_RECEIPT')
    return dict(reasons=sorted(set(reasons)),available_at=max(stamps) if all(x is not None for x in stamps) else None)


def revision(old,new):
    if old['provider']!=new['provider'] or old['symbol']!=new['symbol'] or str(old['fiscal_period_end'])!=str(new['fiscal_period_end']) or old['horizon_raw']!=new['horizon_raw'] or new['horizon_raw']!='0q':
        return dict(pattern='ABSTAIN',delta=None,relative=None,count_group='IDENTITY_BREAK',reasons=['NO_PERIOD_OR_HORIZON_BRIDGE'])
    a,b=old.get('revenue_avg'),new.get('revenue_avg');c,d=old.get('revenue_analyst_count'),new.get('revenue_analyst_count')
    valid=all(x is not None and pd.notna(x) and np.isfinite(float(x)) and x>0 for x in (a,b))
    counts=all(x is not None and pd.notna(x) and x>=3 and float(x).is_integer() for x in (c,d))
    group='MISSING_OR_LT3' if not counts else 'UNCHANGED_COUNT' if c==d else 'CHANGED_COUNT'
    delta=float(b-a) if valid else None;relative=delta/float(a) if valid else None
    pattern='LONG' if valid and delta>0 else 'SHORT' if valid and delta<0 else 'ABSTAIN'
    return dict(pattern=pattern,delta=delta,relative=relative,count_group=group,
        reasons=[] if valid else ['MISSING_OR_NONPOSITIVE_REVENUE'])


def known_metadata(symbol,period):
    # Explicit support scope only; no blanket USD assumption for US listings.
    ok=symbol in ('DOCN','FUN') and str(period)[:10]=='2026-09-30'
    return dict(currency='USD' if ok else None,period_supported=ok,currency_supported=ok,
        actual_fiscal_end_known=symbol=='DOCN' and ok,
        support_scope='USER_TRANSMITTED_EODHD_REPLY_DOCN_FUN_Q3_2026' if ok else 'NOT_VERIFIED')


def top10_for_entry(scores,prior_session,cutoff):
    f=scores[scores.prediction_date.eq(prior_session)].copy()
    if f.empty:return f
    if f.symbol.duplicated().any():raise ValueError('Duplicate Oracle symbol')
    if not (f.target_name.eq('oracle_path_extreme20') & f.target_horizon.eq(20)).all():raise ValueError('Wrong Oracle target')
    if not pd.to_datetime(f.model_available_date).lt(pd.to_datetime(f.prediction_date)).all():raise ValueError('Model unavailable before prediction')
    f=f[pd.to_datetime(f.created_at,utc=True).lt(cutoff)]
    if len(f)<20:return f.iloc[:0]
    f=f.sort_values(['proba_extreme','symbol'],ascending=[False,True]).head(10)
    return f


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh directory required')
    old=READ(PARENT/'protocol.json');verify_hashes(Path('.'),old['sources'])
    for n in ('snapshot-ready.json','pair-ready.json','proof-ready.json','report.json'):verify_hashes(PARENT,READ(PARENT/n)['files'])
    files=[Path(__file__),Path('tests/test_us_consensus_revenue_only.py'),SUPPORT,UNIVERSE,
        PARENT/'protocol.json',PARENT/'consensus.parquet',PARENT/'runs.parquet',PARENT/'oracle-scores.parquet',
        PARENT/'raw-proof-receipts.parquet',Path('artifacts/research/us_consensus_identity_review/20261019-v1/raw-receipts.parquet')]
    root.mkdir(parents=True)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},parent=str(PARENT),
        hypothesis='Current revenue consensus strictly up => LONG; strictly down => SHORT; unchanged/missing => abstain. EPS excluded completely.',
        observation_scope='Existing immutable eight daily observations11-18Oct2026, near-period export1760issuers; not a full newly refreshed database inventory.',
        primary='TOP10 of exact H20 cohort at previous-session date, created before entry; no replacement or reuse of Oct16 score for earlier/later session membership.',
        pairing='Latest fully available0q per symbol BEFORE each consecutive NYSE OPEN. Latest fiscal anchor in current observation; prior same anchor only. Changes between decision cutoffs, not adjacent weekend copies.',
        period='Latest0q anchor is only a candidate fiscal record for unreviewed issuers. Support validates DOCN/FUN Q3 anchor2026-09-30; do not invent actual FUN endpoint or pending-announcement status.',
        feature_support='Currency/units/fiscal anchor explicitly supported only DOCN/FUN Q3. Other universe changes descriptive, not qualified signals. Raw item/source receipt required. Not operational admission.',
        count_control='>=3 revenue analysts at both ends; UNCHANGED_COUNT primary; CHANGED_COUNT separate diagnostic,never pooled. Constant count does not prove identical contributors.',
        raw_proof_sample='All availableTOP10 pairs plus first20 changed and10 unchanged issuers, sorted entry/symbol/period,one pair per issuer/sample before outcome access.',
        availability='max(observed,available,ingestion,completed run finished) strictly before entry open; neither0q fiscal end nor+1q state supplies a historical snapshot date.',
        evaluation='Primary TP10 before SL5 over10NYSEsessions from entry open, expiry tenth close, gap-aware loss-first ambiguous day. Later same costs/benchmark for all arms. No outcomes read in this immature pilot.',
        minimum_confirmation='50 distinct future entry dates and100 nonoverlappingTOP10 episodes. Existing viewed eight-day feature sample is exploratory; protocol is AFTER its entry dates,not ex-ante independent validation.',
        freeze='All eligibility and rules fixed before any H10 outcome calculation; no optimizer or training. Future confirmations require new dates after this protocol and new contemporaneousOracle scores.',
        sql_scope='Only existing raw consensus envelopes for bounded proof sample,READ ONLY UTC REPEATABLE READ thenROLLBACK; no supplier calls.',
        no_outputs=['EPS or EPS-based eligibility','historical vintages invented from+1q/7/30/90d','PnL or training','production/SQL mutation','orders'],
        api_calls=0,llm_calls=0,training=False,sql_writes=False,production_changes=False,orders=False)
    atomic_json(root/'protocol.json',p);return p


def build(root):
    p=prepare(root)
    if (root/'features-ready.json').exists():raise ValueError('Immutable features')
    frame=pd.read_parquet(PARENT/'consensus.parquet');frame=frame[frame.horizon_raw.eq('0q')].copy()
    if frame.duplicated(['symbol','fiscal_period_end','snapshot_date']).any():raise ValueError('Duplicate logical0q snapshot')
    runs={r['run_id']:r for r in pd.read_parquet(PARENT/'runs.parquet').to_dict('records')}
    records={int(r['id']):r for r in frame.to_dict('records')};checks={i:check_row(r,runs) for i,r in records.items()}
    frame['decision_available']=[checks[int(i)]['available_at'] for i in frame.id]
    frame['fiscal_period_end']=pd.to_datetime(frame.fiscal_period_end)
    scores=pd.read_parquet(PARENT/'oracle-scores.parquet');scores['prediction_date']=pd.to_datetime(scores.prediction_date)
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2026-10-01',end_date='2026-11-20')
    sessiondays=schedule.index
    entries=schedule.loc['2026-10-12':'2026-10-19'];rows=[];coverage=[]
    for entry,market in entries.iterrows():
        pos=sessiondays.get_loc(entry);prior=sessiondays[pos-1]
        oldcut=schedule.loc[prior].market_open;newcut=market.market_open
        available=frame[frame.decision_available.notna() & frame.decision_available.lt(newcut)]
        available_old=frame[frame.decision_available.notna() & frame.decision_available.lt(oldcut)]
        current=available.sort_values(['symbol','fiscal_period_end','decision_available','id']).drop_duplicates('symbol',keep='last')
        previous=available_old.sort_values(['decision_available','id']).drop_duplicates(['symbol','fiscal_period_end'],keep='last')
        previous={(r['symbol'],str(r['fiscal_period_end'])[:10]):r for r in previous.to_dict('records')}
        top=top10_for_entry(scores,prior,newcut);rank={s:i+1 for i,s in enumerate(top.symbol)}
        coverage.append(dict(entry_date=entry,previous_session=prior,oracle_scores=len(top),oracle_status='AVAILABLE' if len(top)==10 else 'MISSING_PREVIOUS_SESSION_ORACLE',
            consensus_symbols=len(current),prior_consensus_symbols=len(available_old.symbol.unique())))
        for current_row in current.to_dict('records'):
            key=(current_row['symbol'],str(current_row['fiscal_period_end'])[:10]);old=previous.get(key)
            if old is None:continue
            # A rollover cannot be bridged to another quarter/horizon.
            old_id,new_id=int(old['id']),int(current_row['id']);raw=records[new_id];oldraw=records[old_id]
            rev=revision(oldraw,raw);problems=checks[old_id]['reasons']+checks[new_id]['reasons']+rev.pop('reasons')
            if checks[old_id]['available_at']>=oldcut or checks[new_id]['available_at']>=newcut:problems.append('AFTER_ENTRY_CUTOFF')
            metadata=known_metadata(raw['symbol'],raw['fiscal_period_end'])
            mature=schedule.iloc[pos+9].market_close if pos+9<len(schedule) else None
            rows.append(dict(symbol=key[0],fiscal_anchor=key[1],entry_date=entry,entry_open_utc=newcut,prior_entry_open_utc=oldcut,
                old_id=old_id,new_id=new_id,old_snapshot=str(oldraw['snapshot_date'])[:10],new_snapshot=str(raw['snapshot_date'])[:10],
                old_available=checks[old_id]['available_at'],new_available=checks[new_id]['available_at'],
                old_revenue=oldraw['revenue_avg'],new_revenue=raw['revenue_avg'],old_count=oldraw['revenue_analyst_count'],new_count=raw['revenue_analyst_count'],
                **rev,**metadata,technical_reasons=sorted(set(problems)),technical_pair=not problems,
                in_top10=key[0] in rank,oracle_rank=rank.get(key[0]),maturity_utc=mature,
                live_admission=False,definition_known_before_entry=False))
    features=pd.DataFrame(rows);features.to_parquet(root/'features.parquet',index=False)
    atomic_json(root/'oracle-coverage.json',dict(rows=coverage))
    changed=features[features.pattern.ne('ABSTAIN')].sort_values(['entry_date','symbol','fiscal_anchor']).drop_duplicates('symbol').head(20)
    unchanged=features[features.pattern.eq('ABSTAIN') & features.delta.eq(0)].sort_values(['entry_date','symbol','fiscal_anchor']).drop_duplicates('symbol').head(10)
    sample=pd.concat([features[features.in_top10],changed,unchanged],ignore_index=True).drop_duplicates(['entry_date','symbol','fiscal_anchor'])
    ids=sorted(set(sample.old_id)|set(sample.new_id));sample.to_parquet(root/'proof-sample.parquet',index=False)
    request=frame[frame.id.isin(ids)][['run_id','observed_at']].drop_duplicates()
    atomic_json(root/'proof-request.json',dict(row_ids=ids,receipts=request.to_dict('records')))
    atomic_json(root/'features-ready.json',dict(rows=len(features),sample_pairs=len(sample),sample_rows=len(ids),
        files={n:digest(root/n) for n in ['features.parquet','oracle-coverage.json','proof-sample.parquet','proof-request.json']}))
    print('Revenue-only features',len(features),'; proof pairs',len(sample),flush=True)


def proofs(root):
    prepare(root);verify_hashes(root,READ(root/'features-ready.json')['files'])
    if (root/'proof-ready.json').exists():raise ValueError('Immutable proofs')
    request=READ(root/'proof-request.json');runids=sorted({r['run_id'] for r in request['receipts']})
    stamps=sorted({utc(r['observed_at']).tz_localize(None).to_pydatetime() for r in request['receipts']})
    engine,conn=connect_readonly()
    try:
        stmt=text("""SELECT id,run_id,observed_at,available_at,http_status,payload_hash,payload_json FROM pit_raw_payloads
            WHERE batch_name='eodhd_consensus_snapshot' AND provider='eodhd' AND endpoint='/calendar/trends'
            AND run_id IN :runs AND observed_at IN :stamps ORDER BY id""").bindparams(bindparam('runs',expanding=True),bindparam('stamps',expanding=True))
        rows=[dict(r) for r in conn.execute(stmt,dict(runs=runids,stamps=stamps)).mappings()];conn.rollback()
    finally:conn.close();engine.dispose()
    pd.DataFrame(rows).to_parquet(root/'raw-receipts.parquet',index=False)
    atomic_json(root/'proof-ready.json',dict(receipts=len(rows),files={'raw-receipts.parquet':digest(root/'raw-receipts.parquet')}))
    print('Existing raw envelopes',len(rows),flush=True)


def finalize(root):
    p=prepare(root)
    if (root/'report.json').exists():raise ValueError('Immutable completed pilot')
    for n in ('features-ready.json','proof-ready.json'):verify_hashes(root,READ(root/n)['files'])
    raw=pd.read_parquet(root/'raw-receipts.parquet');matches=set();bad=[]
    for r in raw.to_dict('records'):
        obj=json.loads(r['payload_json'])
        if r['http_status']!=200 or payload_hash(obj)!=r['payload_hash'] or utc(r['available_at'])<utc(r['observed_at']):bad.append(r['id']);continue
        for group in obj.get('trends',[]):
            for item in group:matches.add((r['run_id'],utc(r['observed_at']),payload_hash(item)))
    request=READ(root/'proof-request.json');source=pd.read_parquet(PARENT/'consensus.parquet')
    matching={int(r['id']) for r in source[source.id.isin(request['row_ids'])].to_dict('records')
        if (r['run_id'],utc(r['observed_at']),r['raw_hash']) in matches}
    f=pd.read_parquet(root/'features.parquet')
    f['envelope_verified']=f.old_id.isin(matching)&f.new_id.isin(matching)
    f['supported_research_feature']=f.technical_pair & f.envelope_verified & f.currency_supported & f.period_supported & f.count_group.eq('UNCHANGED_COUNT')
    f['primary_research_pattern']=np.where(f.supported_research_feature & f.in_top10,f.pattern,'ABSTAIN')
    asof=utc(p['created_at_utc']);f['mature_at_protocol']=pd.to_datetime(f.maturity_utc,utc=True).le(asof)
    f.to_parquet(root/'qualified-features.parquet',index=False)
    primary=f[f.in_top10];signals=primary[primary.primary_research_pattern.ne('ABSTAIN')]
    universe=f[f.technical_pair]
    coverage=READ(root/'oracle-coverage.json')['rows']
    result=dict(status='REVENUE_ONLY_PILOT_COMPLETED_H10_IMMATURE_NOT_AN_EFFICACY_RESULT',
        protocol_asof_utc=p['created_at_utc'],rows=len(f),symbols=int(f.symbol.nunique()),decision_dates=int(f.entry_date.nunique()),
        snapshots='11-18Oct2026',changed_numeric_pairs=int(universe.pattern.ne('ABSTAIN').sum()),
        count_strata=universe.groupby(['count_group','pattern']).size().to_dict(),
        proof_rows=len(request['row_ids']),matched_proof_rows=len(matching),source_envelopes=len(raw),bad_envelopes=bad,
        top10_pairs=len(primary),top10_cohorts=int(primary.entry_date.nunique()),top10_numeric_patterns=primary.pattern.value_counts().to_dict(),
        supported_top10_features=int((primary.supported_research_feature).sum()),supported_top10_patterns=primary.primary_research_pattern.value_counts().to_dict(),
        signals=signals[['symbol','entry_date','oracle_rank','fiscal_anchor','old_snapshot','new_snapshot','old_revenue','new_revenue','old_count','new_count','relative','primary_research_pattern']].to_dict('records'),
        top10_feature_table=primary[['symbol','entry_date','oracle_rank','fiscal_anchor','old_revenue','new_revenue','relative','count_group','pattern','currency_supported','period_supported','primary_research_pattern']].to_dict('records'),
        missing_oracle_entry_dates=[str(x['entry_date'])[:10] for x in coverage if x['oracle_scores']!=10],
        h10_mature_primary_signals=int(signals.mature_at_protocol.sum()),
        earliest_universe_h10_maturity=str(f.maturity_utc.min()),earliest_primary_signal_maturity=str(signals.maturity_utc.min()) if len(signals) else None,
        minimum_independent_history_met=False,pnl_computed=False,training=False,sql_writes=False,api_calls=0,llm_calls=0,orders=False,
        next='Preserve current collect; add contemporaneousOracle scores and reporting-currency/fiscal metadata prospectively. Evaluate H10 only after maturity with qualified price paths. No retrospective membership or old+1q vintage invented.',
        files={n:digest(root/n) for n in ['protocol.json','features-ready.json','proof-ready.json','qualified-features.parquet','oracle-coverage.json']} )
    # JSON keys cannot be tuples; explicit labels retain every stratum.
    result['count_strata']={f'{k[0]}:{k[1]}':int(v) for k,v in result['count_strata'].items()}
    atomic_json(root/'report.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','top10_feature_table')},default=str),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--phase',choices=['prepare','build','proofs','finalize'],required=True);args=a.parse_args()
    {'prepare':prepare,'build':build,'proofs':proofs,'finalize':finalize}[args.phase](args.output)
