"""Read-only received EODHD consensus reliability and short matured association.

Separate from immutable Oct19 revenue H10 pilot; no provider/LLM or PnL.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from common.market_calendar import get_market_calendar
from scripts.research.us_news_symbol_sensitivity import digest, save
from scripts.research.us_consensus_observed_revision_pilot import (
    connect_readonly, payload_hash, utc,
)
from service.eodhd.consensus_snapshot import FIELDS, COUNTS, number
from service.eodhd.symbols import to_eodhd
from modelFactory.oracle.security_continuity import load_security_discontinuities

ROOT = Path('artifacts/research/us_consensus_reliability/20261022-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
PROTOCOL = Path('doc/ml/consensus_fiabilite_protocole_20261022.md')
SUPPORTED = {'DOCN','FUN','TWLO','FIVN','ENTG','AKAM'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def query(conn, sql, symbols=None, **params):
    if not sql.strip().upper().startswith('SELECT'):
        raise ValueError('SELECT only')
    stmt = text(sql)
    if symbols is not None:
        stmt = stmt.bindparams(bindparam('symbols', expanding=True))
        params['symbols'] = symbols
    return [dict(r) for r in conn.execute(stmt, params).mappings()]


def prepare(root):
    if root.exists():
        raise FileExistsError('Fresh directory required')
    symbols = sorted(set(re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig').strip())))
    root.mkdir(parents=True)
    files = [Path(__file__),PROTOCOL,UNIVERSE,Path('service/eodhd/consensus_snapshot.py'),
             Path('scripts/research/us_consensus_observed_revision_pilot.py'),
             Path('scripts/research/us_news_symbol_sensitivity.py'),
             Path('tests/test_us_consensus_reliability_20261022.py'),
             Path('service/eodhd/symbols.py'),Path('config/data_quality/security_discontinuities.json')]
    save(root/'protocol.json',dict(version='CONSENSUS_RELIABILITY_20261022_V1',
        cutoff_utc=datetime.now(timezone.utc).isoformat(),symbols=symbols,max_rows=300000,
        snapshot_start='2026-10-11',fiscal_start='2026-06-01',fiscal_end='2027-06-30',
        primary='Revenue 0q mean change, same period, completed actual receipts before consecutive opens; unchanged analyst count>=3',
        short_primary_horizon=1,secondary_horizons=[3,5],h10_maturity_only=True,
        api_calls=0,llm_calls=0,sql_writes=False,training=False,pnl=False,orders=False,
        sources={str(p):digest(p) for p in files}))


def check(root):
    p = read(root/'protocol.json')
    for name, expected in p['sources'].items():
        if digest(name) != expected:
            raise ValueError('Frozen source changed: '+name)
    return p


def snapshot(root):
    p = check(root)
    if (root/'snapshot-ready.json').exists():
        raise FileExistsError('Snapshot already sealed')
    cutoff = utc(p['cutoff_utc']).tz_localize(None).to_pydatetime()
    engine, conn = connect_readonly()
    try:
        totals = query(conn,'''SELECT COUNT(*) n,COUNT(DISTINCT symbol) symbols,
            MIN(snapshot_date) first_snapshot,MAX(snapshot_date) last_snapshot,
            MIN(observed_at) first_observed,MAX(observed_at) last_observed
            FROM stock_analyst_consensus_eodhd_history WHERE provider='eodhd' AND observed_at<:cutoff''',cutoff=cutoff)
        daily = query(conn,'''SELECT snapshot_date,COUNT(*) n,COUNT(DISTINCT symbol) symbols,
            MIN(observed_at) first_observed,MAX(observed_at) last_observed,
            SUM(currency IS NULL) currency_missing,SUM(fiscal_identity_qualified) fiscal_qualified,
            SUM(units_qualified) units_qualified,SUM(eps_avg IS NULL) eps_missing,
            SUM(revenue_avg IS NULL) revenue_missing,
            SUM(eps_low>eps_high OR eps_avg<eps_low OR eps_avg>eps_high) eps_range_bad,
            SUM(revenue_low>revenue_high OR revenue_avg<revenue_low OR revenue_avg>revenue_high) revenue_range_bad
            FROM stock_analyst_consensus_eodhd_history WHERE provider='eodhd'
            AND symbol IN :symbols AND observed_at<:cutoff GROUP BY snapshot_date ORDER BY snapshot_date''',
            p['symbols'],cutoff=cutoff)
        runs = query(conn,'''SELECT run_id,status,started_at,finished_at,requested_count,
            received_count,persisted_count,failed_count,empty_count FROM pit_collection_runs
            WHERE batch_name='eodhd_consensus_snapshot' AND started_at<:cutoff ORDER BY started_at''',cutoff=cutoff)
        conditions = '''provider='eodhd' AND symbol IN :symbols AND snapshot_date>=:start
            AND fiscal_period_end BETWEEN :lo AND :hi AND horizon_raw IN ('0q','0y') AND observed_at<:cutoff'''
        params = dict(start=p['snapshot_start'],lo=p['fiscal_start'],hi=p['fiscal_end'],cutoff=cutoff)
        count = query(conn,'SELECT COUNT(*) n FROM stock_analyst_consensus_eodhd_history WHERE '+conditions,
                      p['symbols'],**params)[0]['n']
        if count > p['max_rows']:
            raise ValueError('Explicit row bound exceeded; partition required')
        rows = query(conn,'SELECT * FROM stock_analyst_consensus_eodhd_history WHERE '+conditions+
                     ' ORDER BY symbol,fiscal_period_end,horizon_raw,observed_at,id',p['symbols'],**params)
        if len(rows) != count:
            raise ValueError('Repeatable snapshot count mismatch')
        pd.DataFrame(rows).to_parquet(root/'consensus.parquet',index=False)
        pd.DataFrame(runs).to_parquet(root/'runs.parquet',index=False)
        save(root/'inventory.json',dict(global_counts=totals[0],daily_tradable=daily,runs=runs,
            export_rows=len(rows),export_symbols=len({r['symbol'] for r in rows})))
        # Schema only at this stage; prices themselves are not opened before features freeze.
        columns = query(conn,'''SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='stock_bars_daily' ORDER BY ORDINAL_POSITION''')
        save(root/'price-schema.json',[r['COLUMN_NAME'] for r in columns])
        conn.rollback()
    finally:
        conn.close();engine.dispose()
    save(root/'snapshot-ready.json',dict(files={n:digest(root/n) for n in
        ['inventory.json','consensus.parquet','runs.parquet','price-schema.json']}))
    print('SNAPSHOT',len(rows),'rows',flush=True)


def row_quality(row, runs):
    errors=[]
    try:
        raw=json.loads(row['raw_payload_json'])
        if payload_hash(raw)!=row['raw_hash']:
            errors.append('RAW_HASH_MISMATCH')
        if (raw.get('code')!=to_eodhd(row['symbol']) or raw.get('period')!=row['horizon_raw']
                or str(raw.get('date'))!=str(row['fiscal_period_end'])[:10]):
            errors.append('RAW_IDENTITY_MISMATCH')
        for field,native in FIELDS.items():
            actual=number(raw.get(native),count=field in COUNTS)
            stored=None if pd.isna(row.get(field)) else float(row[field])
            if (actual is None)!=(stored is None) or (actual is not None and not np.isclose(actual,stored,rtol=0,atol=1e-8)):
                errors.append('NORMALIZATION:'+field)
    except (TypeError,ValueError,KeyError):
        errors.append('INVALID_RAW')
    ranges={}
    for metric in ('eps','revenue'):
        lo,avg,hi=[row.get(metric+'_'+x) for x in ('low','avg','high')]
        bad=((pd.notna(lo) and pd.notna(hi) and lo>hi) or
             (pd.notna(avg) and pd.notna(lo) and avg<lo) or
             (pd.notna(avg) and pd.notna(hi) and avg>hi))
        ranges[metric+'_range_ok']=not bad
    run=runs.get(row['run_id'],{})
    stamps=[utc(row.get(k)) for k in ('observed_at','available_at','ingestion_at')]+[utc(run.get('finished_at'))]
    timing=(run.get('status')=='COMPLETED' and all(s is not None for s in stamps)
        and stamps[1]>=stamps[0] and stamps[3]>=stamps[0])
    return dict(errors=errors,raw_normalization_ok=not errors,run_receipt_ok=bool(timing),
        conservative_available=max(stamps) if timing else pd.NaT,**ranges)


def schedule():
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    rows=[s for s in cal.sessions(date(2026,10,1),date(2026,12,1)) if s.is_open]
    return pd.DataFrame(dict(day=pd.to_datetime([s.session_date for s in rows]),
        opening=pd.to_datetime([s.open_at_utc for s in rows],utc=True),
        closing=pd.to_datetime([s.close_at_utc for s in rows],utc=True)))


def changes(old,new):
    if (old['symbol'],str(old['fiscal_period_end']),old['horizon_raw']) != (new['symbol'],str(new['fiscal_period_end']),new['horizon_raw']):
        raise ValueError('Do not bridge fiscal identities')
    result={}
    for metric in ('revenue','eps'):
        a,b=old.get(metric+'_avg'),new.get(metric+'_avg')
        valid=pd.notna(a) and pd.notna(b) and np.isfinite([a,b]).all()
        if metric=='revenue':valid=valid and min(a,b)>0
        delta=float(b-a) if valid else None
        result[metric+'_delta']=delta
        result[metric+'_relative']=delta/abs(float(a)) if valid and a!=0 else None
        result[metric+'_sign']=int(np.sign(delta)) if valid else 0
        c,d=old.get(metric+'_analyst_count'),new.get(metric+'_analyst_count')
        counts=all(pd.notna(x) and x>=3 and float(x).is_integer() for x in (c,d))
        result[metric+'_count_group']='MISSING_OR_LT3' if not counts else 'UNCHANGED_COUNT' if c==d else 'CHANGED_COUNT'
    result['revision_imbalance_sign']=(int(np.sign(new['revisions_up_7d']-new['revisions_down_7d']))
        if pd.notna(new.get('revisions_up_7d')) and pd.notna(new.get('revisions_down_7d')) else 0)
    return result


def decision_features(frame,runs,sched,cutoff):
    checks={int(r['id']):row_quality(r,runs) for r in frame.to_dict('records')}
    f=frame[frame.horizon_raw.eq('0q')].copy()
    f['fiscal_period_end']=pd.to_datetime(f.fiscal_period_end)
    f['known_at']=pd.to_datetime([checks[int(i)]['conservative_available'] for i in f.id],utc=True)
    if f.duplicated(['provider','symbol','snapshot_date','fiscal_period_end','horizon_raw']).any():
        raise ValueError('Duplicate logical snapshots')
    records={int(r['id']):r for r in frame.to_dict('records')}
    output=[]
    for i in range(1,len(sched)):
        entry=sched.iloc[i]
        prior=sched.iloc[i-1].opening
        if entry.opening>=cutoff:
            continue
        available=f[f.known_at.lt(entry.opening)&f.known_at.ge(entry.opening-pd.Timedelta(days=4))]
        available=available[available.fiscal_period_end.between(entry.day-pd.Timedelta(days=100),entry.day+pd.Timedelta(days=100))]
        current=available.sort_values(['symbol','fiscal_period_end','known_at','id']).drop_duplicates('symbol',keep='last')
        previous=f[f.known_at.lt(prior)&f.known_at.ge(prior-pd.Timedelta(days=4))]
        previous=previous.sort_values(['known_at','id']).drop_duplicates(['symbol','fiscal_period_end'],keep='last')
        lookup={(r.symbol,r.fiscal_period_end):r.id for r in previous.itertuples()}
        for new in current.itertuples():
            old_id=lookup.get((new.symbol,new.fiscal_period_end))
            if old_id is None:continue
            old,newrow=records[int(old_id)],records[int(new.id)]
            a,b=checks[int(old_id)],checks[int(new.id)]
            raw_ok=a['raw_normalization_ok'] and b['raw_normalization_ok']
            revenue_ok=raw_ok and a['revenue_range_ok'] and b['revenue_range_ok']
            eps_ok=raw_ok and a['eps_range_ok'] and b['eps_range_ok']
            output.append(dict(symbol=new.symbol,entry_date=entry.day,entry_idx=i,entry_open=entry.opening,
                prior_open=prior,old_id=int(old_id),new_id=int(new.id),fiscal_anchor=new.fiscal_period_end,
                old_available=a['conservative_available'],new_available=b['conservative_available'],
                old_revenue=old['revenue_avg'],new_revenue=newrow['revenue_avg'],
                old_eps=old['eps_avg'],new_eps=newrow['eps_avg'],
                old_revenue_count=old['revenue_analyst_count'],new_revenue_count=newrow['revenue_analyst_count'],
                old_eps_count=old['eps_analyst_count'],new_eps_count=newrow['eps_analyst_count'],
                revenue_technical_ok=bool(revenue_ok),eps_technical_ok=bool(eps_ok),
                context_previously_documented=(new.symbol in SUPPORTED and new.fiscal_period_end==pd.Timestamp('2026-09-30')),
                production_qualified=False,**changes(old,newrow)))
    return pd.DataFrame(output),checks


def features(root):
    p=check(root)
    if (root/'features-ready.json').exists():raise FileExistsError('Features already frozen')
    for n,h in read(root/'snapshot-ready.json')['files'].items():
        if digest(root/n)!=h:raise ValueError('Snapshot changed')
    f=pd.read_parquet(root/'consensus.parquet')
    runs={r['run_id']:r for r in pd.read_parquet(root/'runs.parquet').to_dict('records')}
    result,checks=decision_features(f,runs,schedule(),utc(p['cutoff_utc']))
    result.to_parquet(root/'features.parquet',index=False)
    quality=pd.DataFrame([dict(id=i,**v) for i,v in checks.items()])
    quality.to_parquet(root/'row-quality.parquet',index=False)
    changed=result[result.revenue_sign.ne(0)].sort_values(['symbol','entry_date']).drop_duplicates('symbol').head(20)
    stable=result[result.revenue_sign.eq(0)&result.revenue_delta.eq(0)].sort_values(['symbol','entry_date']).drop_duplicates('symbol').head(10)
    supported=result[result.symbol.isin(SUPPORTED)]
    proof=pd.concat([changed,stable,supported]).drop_duplicates(['old_id','new_id'])
    ids=sorted(set(proof.old_id)|set(proof.new_id))
    sample=f[f.id.isin(ids)][['id','run_id','observed_at','raw_hash']]
    sample.to_parquet(root/'proof-request.parquet',index=False)
    save(root/'features-ready.json',dict(rows=len(result),dates=int(result.entry_date.nunique()),
        proof_rows=len(sample),files={n:digest(root/n) for n in ['features.parquet','row-quality.parquet','proof-request.parquet']}))
    print('FEATURES',len(result),'decisions',result.entry_date.nunique(),'dates',flush=True)


def export_prices_and_proofs(root):
    p=check(root)
    if (root/'prices-ready.json').exists():raise FileExistsError('Prices already frozen')
    for n,h in read(root/'features-ready.json')['files'].items():
        if digest(root/n)!=h:raise ValueError('Features changed')
    cols=read(root/'price-schema.json')
    required=['symbol','date','open','high','low','close','volume','is_filled','data_adjustment']
    if not set(required).issubset(cols):raise ValueError('Missing daily price fields')
    selected=required+[c for c in ('instrument_id','data_source','provider','last_updated','updated_at') if c in cols]
    request=pd.read_parquet(root/'proof-request.parquet')
    engine,conn=connect_readonly()
    try:
        prices=query(conn,'SELECT '+','.join('`'+c+'`' for c in selected)+''' FROM stock_bars_daily
            WHERE symbol IN :symbols AND date BETWEEN :start AND :finish ORDER BY symbol,date''',
            p['symbols']+['SPY'],start='2026-10-01',finish=str(utc(p['cutoff_utc']).date()))
        pd.DataFrame(prices).to_parquet(root/'prices.parquet',index=False)
        # Match exact existing receipt timestamps, grouped per run, no provider calls.
        receipts=[]
        for run,group in request.groupby('run_id'):
            stamps=[utc(x).tz_localize(None).to_pydatetime() for x in group.observed_at.unique()]
            stmt=text('''SELECT id,run_id,observed_at,available_at,http_status,payload_hash,payload_json
                FROM pit_raw_payloads WHERE batch_name='eodhd_consensus_snapshot' AND provider='eodhd'
                AND endpoint='/calendar/trends' AND run_id=:run AND observed_at IN :stamps
                ORDER BY id LIMIT 5001''').bindparams(bindparam('stamps',expanding=True))
            part=[dict(r) for r in conn.execute(stmt,dict(run=run,stamps=stamps)).mappings()]
            if len(part)>5000:raise ValueError('Proof envelope cap exceeded')
            receipts.extend(part)
        pd.DataFrame(receipts).to_parquet(root/'raw-proof-receipts.parquet',index=False)
        conn.rollback()
    finally:conn.close();engine.dispose()
    save(root/'prices-ready.json',dict(rows=len(prices),envelopes=len(receipts),
        files={n:digest(root/n) for n in ['prices.parquet','raw-proof-receipts.parquet']}))
    print('PRICES',len(prices),'PROOF ENVELOPES',len(receipts),flush=True)


def score_prices(features,prices,sched,cutoff,horizon):
    f=features.copy().reset_index(drop=True)
    f['exit_idx']=f.entry_idx+horizon-1
    f['maturity']=pd.to_datetime(f.exit_idx.map(sched.closing.to_dict()),utc=True)
    f['mature']=f.maturity.lt(cutoff)
    f['price_status']='IMMATURE'
    f['return_pct']=np.nan
    f['spy_return_pct']=np.nan
    b=prices.copy()
    b['date']=pd.to_datetime(b.date)
    if b.duplicated(['symbol','date']).any():raise ValueError('Duplicate daily bars')
    for k in ('open','high','low','close','volume'):
        b[k]=pd.to_numeric(b[k],errors='coerce')
    groups={s:g.set_index('date') for s,g in b.groupby('symbol')}
    registry=load_security_discontinuities()
    def price_path(symbol,days):
        part=groups.get(symbol)
        if part is None:return None,'MISSING_SYMBOL'
        g=part.reindex(days)
        valid=(g.is_filled.eq(0)&g[['open','high','low','close','volume']].gt(0).all(axis=1)&
            np.isfinite(g[['open','high','low','close','volume']]).all(axis=1)&
            g.high.ge(g[['open','close','low']].max(axis=1))&g.low.le(g[['open','close','high']].min(axis=1)))
        if not valid.all():return None,'MISSING_OR_INVALID_BARS'
        if g.data_adjustment.nunique()!=1 or not g.data_adjustment.iloc[0] in ('split','raw'):
            return None,'ADJUSTMENT_CHANGED_OR_UNKNOWN'
        if 'data_source' in g and (g.data_source.isna().any() or g.data_source.nunique()!=1):
            return None,'PROVENANCE_CHANGED_OR_UNKNOWN'
        if 'instrument_id' in g and (g.instrument_id.isna().any() or g.instrument_id.nunique()!=1):
            return None,'IDENTITY_CHANGED_OR_UNKNOWN'
        if any(e.crosses(days[0],days[-1]) for e in registry.get(symbol,())):
            return None,'KNOWN_IDENTITY_BREAK'
        return float((g.close.iloc[-1]/g.open.iloc[0]-1)*100),'AVAILABLE_RESEARCH_NOT_FULLY_QUALIFIED'
    for r in f[f.mature].itertuples():
        days=sched.day.iloc[r.entry_idx:r.exit_idx+1]
        value,status=price_path(r.symbol,days)
        f.loc[r.Index,'price_status']=status
        if value is None:continue
        spy,spy_status=price_path('SPY',days)
        if spy is None:
            f.loc[r.Index,'price_status']='SPY_'+spy_status
            continue
        f.loc[r.Index,['return_pct','spy_return_pct']]=[value,spy]
    return f


def reserve_windows(frame):
    keep=[];last={}
    for r in frame.sort_values(['entry_idx','symbol']).itertuples():
        if r.entry_idx>last.get(r.symbol,-1):
            keep.append(r.Index);last[r.symbol]=r.exit_idx
    return frame.loc[keep]


def metric(frame,sign_column):
    f=frame[frame[sign_column].ne(0)&frame.return_pct.notna()].copy()
    if f.empty:return dict(n=0,dates=0,symbols=0)
    f['signed']=f[sign_column]*f.return_pct
    f['excess']=f[sign_column]*(f.return_pct-f.spy_return_pct)
    daily=f.groupby('entry_date').agg(signed=('signed','mean'),excess=('excess','mean'))
    return dict(n=len(f),dates=len(daily),symbols=int(f.symbol.nunique()),
        correct_sign_pct=float(f.signed.gt(0).mean()*100),
        correct_excess_spy_pct=float(f.excess.gt(0).mean()*100),
        signed_mean_pct=float(f.signed.mean()),signed_median_pct=float(f.signed.median()),
        after_16bps_mean_pct=float(f.signed.mean()-.16),equal_date_signed_mean_pct=float(daily.signed.mean()),
        equal_date_excess_spy_mean_pct=float(daily.excess.mean()),
        positive_signed_dates=int(daily.signed.gt(0).sum()),
        always_long_same_cases_mean_pct=float(f.return_pct.mean()),
        always_short_same_cases_mean_pct=float(-f.return_pct.mean()),
        changes_up=int(f[sign_column].gt(0).sum()),changes_down=int(f[sign_column].lt(0).sum()),
        largest_symbol_share_pct=float(f.symbol.value_counts(normalize=True).iloc[0]*100))


def finalize(root):
    p=check(root)
    if (root/'report.json').exists():raise FileExistsError('Report exists')
    for ready in ('snapshot-ready.json','features-ready.json','prices-ready.json'):
        for name,h in read(root/ready)['files'].items():
            if digest(root/name)!=h:raise ValueError('Sealed artifact changed')
    f=pd.read_parquet(root/'features.parquet')
    q=pd.read_parquet(root/'row-quality.parquet')
    request=pd.read_parquet(root/'proof-request.parquet')
    receipts=pd.read_parquet(root/'raw-proof-receipts.parquet')
    matches=set();bad_envelopes=[]
    for row in receipts.to_dict('records'):
        try:
            obj=json.loads(row['payload_json'])
            if row['http_status']!=200 or payload_hash(obj)!=row['payload_hash'] or utc(row['available_at'])<utc(row['observed_at']):
                raise ValueError('Invalid envelope')
            for group in obj['trends']:
                for item in group:matches.add((row['run_id'],utc(row['observed_at']),payload_hash(item)))
        except (ValueError,TypeError,KeyError):bad_envelopes.append(int(row['id']))
    verified={int(r.id) for r in request.itertuples() if (r.run_id,utc(r.observed_at),r.raw_hash) in matches}
    f['proof_sample_verified']=f.old_id.isin(verified)&f.new_id.isin(verified)
    f['joint_sign']=np.where(f.eps_sign.eq(f.revenue_sign),f.revenue_sign,0)
    quality_errors=Counter(x for errors in q.errors for x in errors)
    report=dict(status='COMPLETED_RELIABILITY_AND_SHORT_DESCRIPTIVE_ONLY',cutoff_utc=p['cutoff_utc'],
        inventory=read(root/'inventory.json'),export_rows=len(q),raw_normalization_good=int(q.raw_normalization_ok.sum()),
        eps_ranges_bad=int((~q.eps_range_ok).sum()),revenue_ranges_bad=int((~q.revenue_range_ok).sum()),
        run_receipts_good=int(q.run_receipt_ok.sum()),technical_errors=dict(quality_errors),
        proof_rows_requested=len(request),proof_rows_verified=len(verified),proof_envelopes=len(receipts),bad_envelopes=bad_envelopes,
        decision_pairs=len(f),decision_dates=int(f.entry_date.nunique()),symbols=int(f.symbol.nunique()),
        count_strata={f'{k[0]}:{k[1]}':int(v) for k,v in f.groupby(['revenue_count_group','revenue_sign']).size().items()},
        horizons={},minimum_independent_confirmation_met=False,live_qualified=False,
        eps_basis_unknown=True,analyst_identities_unknown=True,full_currency_period_qualification=False,
        sql_writes=False,api_calls=0,llm_calls=0,pnl=False,training=False)
    prices=pd.read_parquet(root/'prices.parquet')
    report['prices']=dict(rows=len(prices),symbols=int(prices.symbol.nunique()),
        first=str(prices.date.min()),last=str(prices.date.max()),
        data_sources=prices.data_source.value_counts(dropna=False).to_dict() if 'data_source' in prices else {})
    for horizon in (1,3,5,10):
        if horizon==10:
            # No H10 returns in this separate short audit, even if some mature.
            cal=schedule()
            maturity=pd.to_datetime((f.entry_idx+9).map(cal.closing.to_dict()),utc=True)
            report['horizons']['10']=dict(mature_calendar_pairs=int(maturity.lt(utc(p['cutoff_utc'])).sum()),
                earliest_maturity=str(maturity.min()),outcomes_reported=False,
                old_frozen_oct19_cohort_maturity='2026-10-30T20:00:00+00:00')
            continue
        scored=score_prices(f,prices,schedule(),utc(p['cutoff_utc']),horizon)
        scored.to_parquet(root/f'diagnostic-H{horizon}.parquet',index=False)
        independent=reserve_windows(scored)
        summary=dict(price_status=scored.price_status.value_counts().to_dict(),groups={})
        for name,mask,sign_col in (
            ('REVENUE_UNCHANGED_COUNT_PRIMARY',scored.revenue_technical_ok&scored.revenue_count_group.eq('UNCHANGED_COUNT'),'revenue_sign'),
            ('REVENUE_CHANGED_COUNT_DIAGNOSTIC',scored.revenue_technical_ok&scored.revenue_count_group.eq('CHANGED_COUNT'),'revenue_sign'),
            ('DOCUMENTED_CONTEXT_ONLY',scored.revenue_technical_ok&scored.revenue_count_group.eq('UNCHANGED_COUNT')&scored.context_previously_documented,'revenue_sign'),
            ('EPS_UNCHANGED_COUNT_BASIS_UNKNOWN',scored.eps_technical_ok&scored.eps_count_group.eq('UNCHANGED_COUNT'),'eps_sign'),
            ('EPS_AND_REVENUE_CONCORDANT_RESERVED',scored.eps_technical_ok&scored.revenue_technical_ok&scored.eps_count_group.eq('UNCHANGED_COUNT')&scored.revenue_count_group.eq('UNCHANGED_COUNT'),'joint_sign'),
            ('REVISION_IMBALANCE_7D_SECONDARY',scored.eps_technical_ok&scored.eps_count_group.eq('UNCHANGED_COUNT'),'revision_imbalance_sign')):
            group=scored[mask]
            summary['groups'][name]=dict(all=metric(group,sign_col),
                no_overlap=metric(independent.loc[independent.index.intersection(group.index)],sign_col))
        report['horizons'][str(horizon)]=summary
    f.to_parquet(root/'qualified-features-research-only.parquet',index=False)
    # Source errors or counts do not become labels. Large movements kept as reserves.
    large=f[f.revenue_relative.abs().gt(.25)|f.eps_relative.abs().gt(1)].copy()
    large.to_csv(root/'large-changes-reserve.csv',index=False)
    report['large_change_pairs']=len(large)
    report['files']={n.name:digest(n) for n in root.iterdir() if n.is_file() and n.name!='report.json'}
    save(root/'report.json',report)
    print(report['status'],'pairs',len(f),'dates',f.entry_date.nunique(),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True,choices=('prepare','snapshot','features','prices','finalize'))
    parser.add_argument('--output-dir',type=Path,default=ROOT)
    a=parser.parse_args()
    dict(prepare=prepare,snapshot=snapshot,features=features,prices=export_prices_and_proofs,finalize=finalize)[a.phase](a.output_dir)
