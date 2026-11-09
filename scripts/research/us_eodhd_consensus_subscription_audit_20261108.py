"""Read-only received consensus audit before subscription cancellation.

Fixed signals and H5/H10/H20; no fitting, inference, provider or broker calls.
All observations, missing paths and maturity counts are retained.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil

import numpy as np
import pandas as pd
from sqlalchemy import text, bindparam
from sklearn.metrics import roc_auc_score

from common.market_calendar import get_market_calendar
from scripts.research.us_consensus_observed_revision_pilot import connect_readonly, utc
from scripts.research.us_consensus_reliability_20261022 import row_quality
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT = Path('artifacts/research/us_eodhd_subscription_audit/20261108-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
BATCH = 'model-factory-20261107222627-db80b0'
SIGNALS = ['eps30', 'revisions30', 'revenue_observed']


def query(c, sql, symbols=None, **params):
    stmt = text(sql)
    if symbols is not None:
        stmt = stmt.bindparams(bindparam('symbols', expanding=True))
        params['symbols'] = symbols
    return pd.DataFrame(c.execute(stmt, params).mappings().all())


def calendar():
    items = [s for s in get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        .sessions(date(2026,10,1), date(2026,12,31)) if s.is_open]
    return pd.DataFrame(dict(day=pd.to_datetime([s.session_date for s in items]),
        opening=pd.to_datetime([s.open_at_utc for s in items], utc=True),
        closing=pd.to_datetime([s.close_at_utc for s in items], utc=True)))


def build_features(raw, runs, schedule, cutoff):
    f = raw.copy()
    runmap = {r['run_id']: r for r in runs.to_dict('records')}
    stamps = pd.concat([pd.to_datetime(f[k], utc=True) for k in ('observed_at','available_at','ingestion_at')]
        + [pd.to_datetime(f.run_id.map({k:v['finished_at'] for k,v in runmap.items()}), utc=True)], axis=1)
    f['known_at'] = stamps.max(axis=1)
    f['completed'] = f.run_id.map({k:v['status'] for k,v in runmap.items()}).eq('COMPLETED') & stamps.notna().all(axis=1)
    f['fiscal_period_end'] = pd.to_datetime(f.fiscal_period_end)
    records = {int(r['id']): r for r in f.to_dict('records')}
    checks = {}
    rows = []
    for i in range(1, len(schedule)):
        session = schedule.iloc[i]
        if session.opening >= cutoff:
            continue
        eligible = f[f.completed & f.known_at.lt(session.opening)
            & f.known_at.ge(session.opening-pd.Timedelta(days=4))
            & f.fiscal_period_end.between(session.day-pd.Timedelta(days=100), session.day+pd.Timedelta(days=100))]
        chosen = eligible.sort_values(['symbol','fiscal_period_end','known_at','id']).drop_duplicates('symbol',keep='last')
        prior_open = schedule.iloc[i-1].opening
        previous = f[f.completed & f.known_at.lt(prior_open) & f.known_at.ge(prior_open-pd.Timedelta(days=4))]
        oldmap = {(r.symbol,r.fiscal_period_end):int(r.id) for r in previous.sort_values(['known_at','id'])
            .drop_duplicates(['symbol','fiscal_period_end'],keep='last').itertuples()}
        for row in chosen.to_dict('records'):
            ident = int(row['id'])
            if ident not in checks:
                checks[ident] = row_quality(records[ident], runmap)
            q = checks[ident]
            valid = q['raw_normalization_ok'] and q['run_receipt_ok']
            item = dict(symbol=row['symbol'],entry_day=session.day,entry_idx=i,decision_at=session.opening,
                consensus_id=ident,known_at=row['known_at'],fiscal_period=row['fiscal_period_end'],
                technical_ok=bool(valid),eps30=np.nan,revisions30=np.nan,revenue_observed=np.nan,old_id=None)
            count = row['eps_analyst_count']
            if valid and q['eps_range_ok'] and pd.notna(count) and count >= 3:
                now, old = row['eps_current'], row['eps_30d_ago']
                if pd.notna(now) and pd.notna(old) and np.isfinite([now,old]).all() and old != 0:
                    item['eps30'] = (float(now)-float(old))/abs(float(old))
                up, down = row['revisions_up_30d'], row['revisions_down_30d']
                if pd.notna(up) and pd.notna(down) and np.isfinite([up,down]).all() and min(up,down) >= 0:
                    item['revisions30'] = (float(up)-float(down))/(up+down) if up+down else 0.
            old_id = oldmap.get((row['symbol'],row['fiscal_period_end']))
            if old_id is not None:
                if old_id not in checks:
                    checks[old_id] = row_quality(records[old_id],runmap)
                old = records[old_id]
                a = checks[old_id]
                item['old_id'] = old_id
                counts = [old['revenue_analyst_count'],row['revenue_analyst_count']]
                values = [old['revenue_avg'],row['revenue_avg']]
                if (valid and a['raw_normalization_ok'] and a['run_receipt_ok'] and q['revenue_range_ok']
                        and a['revenue_range_ok'] and all(pd.notna(v) and v >= 3 for v in counts)
                        and counts[0] == counts[1] and all(pd.notna(v) and v > 0 for v in values)):
                    item['revenue_observed'] = float(values[1]/values[0]-1)
            rows.append(item)
    quality = pd.DataFrame([dict(id=k,**v) for k,v in checks.items()])
    return pd.DataFrame(rows),quality


def oracle_ranks(raw, universe):
    from modelFactory.oracle_path.predict import load_contract
    model, contract, profile, folds = load_contract('artifacts/models',BATCH)
    if contract['horizon'] != 10 or set(contract['universe']) != set(universe):
        raise ValueError('Contrat Oracle H10/univers différent')
    f = raw.copy()
    if f.empty:
        return pd.DataFrame(columns=['signal_day','symbol','oracle_rank']), dict(qualified_dates=0)
    f['signal_day'] = pd.to_datetime(f.signal_day)
    if f.duplicated(['signal_day','symbol']).any():
        raise ValueError('Prédictions Oracle dupliquées')
    # Cache checksum outside row loop.
    fhash = digest(model/'feature_profile.json')
    expected = {key:v['model_sha256'] for key,v in folds.items()}
    mask = (f.fold_start.astype(str).str[:10].map(expected).eq(f.model_sha256)
        & f.target_horizon.eq(10) & f.target_name.eq(contract['target'])
        & f.feature_profile_sha256.eq(fhash) & f.proba_extreme.between(0,1)
        & pd.to_datetime(f.model_available_date).le(f.signal_day))
    bad = int((~mask).sum())
    f = f[mask & f.symbol.isin(universe)].copy()
    counts = f.groupby('signal_day').symbol.transform('size')
    f = f[counts.ge(math.ceil(.93*len(universe)))].copy()
    f = f.sort_values(['signal_day','proba_extreme','symbol'],ascending=[True,False,True])
    f['oracle_rank'] = f.groupby('signal_day').cumcount()+1
    return f,dict(batch=BATCH,qualified_dates=int(f.signal_day.nunique()),invalid_lineage_rows=bad,
        minimum_coverage=.93,feature_profile_sha256=fhash,physical_historical_score_availability_not_certified=True)


def outcome(path, tp=.1, sl=.1):
    path = path[['open','high','low','close']].astype(float)
    entry = float(path.open.iloc[0])
    # Adverse-first if both barriers touched within one daily candle.
    result = 'TIME'
    realized = float(path.close.iloc[-1]/entry-1)
    for r in path.itertuples():
        if r.open <= entry*(1-sl):
            result,realized = 'SL',float(r.open/entry-1);break
        if r.open >= entry*(1+tp):
            result,realized = 'TP',float(r.open/entry-1);break
        if r.low <= entry*(1-sl):
            result,realized = 'SL',-sl;break
        if r.high >= entry*(1+tp):
            result,realized = 'TP',tp;break
    up = float(path.high.max()/entry-1)
    down = float(path.low.min()/entry-1)
    return dict(close_return=float(path.close.iloc[-1]/entry-1),max_up=up,max_down=down,
        max_abs_long=up > abs(down),barrier_status=result,barrier_return=realized,
        barrier_net_return=realized-.0016)


def measure(features, prices, schedule, cutoff):
    p = prices.copy()
    p['date'] = pd.to_datetime(p.date)
    if p.duplicated(['symbol','date']).any():
        raise ValueError('Doublons SIP par séance')
    groups = {s:g.set_index('date').sort_index() for s,g in p.groupby('symbol')}
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    registry = load_security_discontinuities()
    rows = []
    for r in features.to_dict('records'):
        for h in (5,10,20):
            end = r['entry_idx']+h-1
            item = {**r,'horizon':h,'status':'IMMATURE'}
            if end >= len(schedule) or schedule.iloc[end].closing >= cutoff:
                rows.append(item);continue
            days = schedule.day.iloc[r['entry_idx']:end+1]
            item['end_day'] = days.iloc[-1]
            g = groups.get(r['symbol'])
            if g is None:
                item['status']='MISSING_PRICES';rows.append(item);continue
            path = g.reindex(days)
            numeric = path[['open','high','low','close']].astype(float)
            path[numeric.columns] = numeric
            ok = (np.isfinite(numeric).all(axis=1) & numeric.gt(0).all(axis=1) & path.is_filled.eq(0)
                & path.data_adjustment.eq('split') & path.instrument_id.notna()
                & path.high.ge(path[['open','close','low']].max(axis=1))
                & path.low.le(path[['open','close','high']].min(axis=1)))
            if (not ok.all() or path.instrument_id.nunique()!=1
                    or any(e.crosses(days.iloc[0],days.iloc[-1]) for e in registry.get(r['symbol'],()))):
                item['status']='MISSING_OR_UNQUALIFIED_PATH';rows.append(item);continue
            item.update(status='MATURE',**outcome(path))
            rows.append(item)
    return pd.DataFrame(rows)


def summary(panel):
    output = []
    for scope in ['TRADABLE','TOP10','TOP20','TOP50']:
        f = panel if scope == 'TRADABLE' else panel[panel.oracle_rank.le(int(scope[3:]))]
        for h in (5,10,20):
            g = f[f.horizon.eq(h)]
            for signal in SIGNALS:
                available = g[g[signal].notna()]
                valid = available[available.status.eq('MATURE')]
                def metrics(x):
                    return dict(n=len(x),symbols=int(x.symbol.nunique()),dates=int(x.entry_day.nunique()),
                        close_win_pct=float(x.close_return.gt(0).mean()*100) if len(x) else None,
                        peak_long_pct=float(x.max_abs_long.mean()*100) if len(x) else None,
                        TP10_before_SL10_pct=float(x.barrier_status.eq('TP').mean()*100) if len(x) else None,
                        barrier_net_win_pct=float(x.barrier_net_return.gt(0).mean()*100) if len(x) else None,
                        barrier_mean_net_pct=float(x.barrier_net_return.mean()*100) if len(x) else None)
                positive = valid[valid[signal].gt(0)]
                negative = valid[valid[signal].lt(0)]
                daily = valid.groupby('entry_day')
                aucs = [float(roc_auc_score(x.max_abs_long.astype(int),x[signal].astype(float)))
                    for _,x in daily if x.max_abs_long.nunique()==2]
                last = {};keep=[]
                for idx,r in positive.sort_values(['entry_day','symbol']).iterrows():
                    if r.entry_idx > last.get(r.symbol,-1):
                        keep.append(idx);last[r.symbol]=r.entry_idx+h-1
                output.append(dict(scope=scope,horizon=h,signal=signal,available=len(available),
                    status_counts=available.status.value_counts().to_dict(),all_same_eligible=metrics(valid),
                    positive=metrics(positive),negative=metrics(negative),nonoverlap_positive=metrics(positive.loc[keep]),
                    mean_daily_peak_auc=float(np.mean(aucs)) if aucs else None,informative_auc_dates=len(aucs)))
    return output


def run(root,reuse=None):
    root.mkdir(parents=True,exist_ok=False)
    cutoff = pd.Timestamp.now(tz='UTC')
    if reuse is not None:
        cutoff = pd.Timestamp(json.loads((reuse/'protocol.json').read_text(encoding='utf-8'))['cutoff'])
    symbols = sorted({s for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig')) if s})
    sched = calendar()
    protocol = dict(cutoff=str(cutoff),universe_file=str(UNIVERSE),universe_size=len(symbols),
        signals=SIGNALS,horizons=[5,10,20],only_0q=True,min_analysts=3,max_age_days=4,
        fiscal_anchor='latest within +/-100 days, then latest technically qualified completed receipt',
        favorable_rule='strict positive; zero neutral; no fitted weights',
        price_source='alpaca_sip split only, complete OHLC and stable instrument_id; no volume filter',
        trade_measure='LONG TP10/SL10, entry next eligible open, exit H close if no barrier; adverse-first OHLC; cost16bps',
        peak_measure='larger absolute HIGH/LOW excursion anywhere in H; not tradable summit return',
        close_measure='close H vs entry open; not peak',repeated_dates_not_independent=True,
        eps_basis_currency_fiscal_and_analyst_composition_reserves=True,strict_PIT=False,
        provider_calls=0,LLM_calls=0,SQL_writes=0,orders=0,training=False,
        sources={str(p):digest(p) for p in [Path(__file__),UNIVERSE,Path('service/eodhd/consensus_snapshot.py')]})
    protocol['oracle_scope'] = 'Existing causal annual H10 2026 model only; TOP scopes limited to dates already present, no new inference'
    if reuse is not None:
        protocol['reused_consensus_snapshot'] = dict(source=str(reuse),files={n:digest(reuse/n) for n in ['protocol.json','consensus.parquet','runs.parquet']})
    atomic_json(root/'protocol.json',protocol)
    atomic_json(root/'progress.json',dict(status='SNAPSHOT_READ_ONLY'))
    engine,c = connect_readonly()
    try:
        if reuse is None:
            params=dict(cutoff=cutoff.tz_localize(None).to_pydatetime())
            conditions="provider='eodhd' AND symbol IN :symbols AND horizon_raw='0q' AND snapshot_date>='2026-10-11' AND fiscal_period_end BETWEEN '2026-06-01' AND '2027-03-31' AND observed_at<:cutoff"
            n=query(c,'SELECT COUNT(*) n FROM stock_analyst_consensus_eodhd_history WHERE '+conditions,symbols,**params).n.iloc[0]
            if n > 300000:raise ValueError('Borne 300000 dépassée; partition explicite nécessaire')
            raw=query(c,'SELECT * FROM stock_analyst_consensus_eodhd_history WHERE '+conditions+' ORDER BY symbol,observed_at,id',symbols,**params)
            if len(raw)!=n:raise ValueError('Snapshot tronqué')
            raw.to_parquet(root/'consensus.parquet',index=False)
            runs=query(c,"SELECT run_id,status,started_at,finished_at,requested_count,received_count,persisted_count,failed_count FROM pit_collection_runs WHERE batch_name='eodhd_consensus_snapshot' AND started_at<:cutoff",**params)
            runs.to_parquet(root/'runs.parquet',index=False)
        else:
            for name in ['consensus.parquet','runs.parquet']:shutil.copyfile(reuse/name,root/name)
            raw=pd.read_parquet(root/'consensus.parquet');runs=pd.read_parquet(root/'runs.parquet')
        atomic_json(root/'progress.json',dict(status='QUALIFYING_RECEIPTS',snapshot_rows=len(raw)))
        features,quality=build_features(raw,runs,sched,cutoff)
        # Freeze observable features and ranks BEFORE opening future price paths.
        features['signal_day']=features.entry_idx.map(lambda i:sched.iloc[i-1].day)
        scores=query(c,"""SELECT p.prediction_date signal_day,p.symbol,p.proba_extreme,p.fold_start,
            l.model_available_date,l.target_horizon,l.target_name,l.model_sha256,l.feature_profile_sha256
            FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l
            ON p.batch_id=l.batch_id AND p.symbol=l.symbol AND p.prediction_date=l.prediction_date
            WHERE p.batch_id=:batch AND p.prediction_date BETWEEN '2026-10-09' AND :end""",
            batch=BATCH,end=cutoff.date())
        scores.to_parquet(root/'oracle-scores.parquet',index=False)
        ranks,oracle_info=oracle_ranks(scores,symbols)
        features=features.merge(ranks[['signal_day','symbol','oracle_rank']],on=['signal_day','symbol'],how='left',validate='many_to_one')
        features.to_parquet(root/'features.parquet',index=False)
        quality.to_parquet(root/'quality.parquet',index=False)
        atomic_json(root/'features-seal.json',dict(files={n:digest(root/n) for n in ['features.parquet','quality.parquet','consensus.parquet','runs.parquet','oracle-scores.parquet']}))
        atomic_json(root/'progress.json',dict(status='READING_SIP_PRICES',features=len(features)))
        prices=query(c,"SELECT symbol,date,open,high,low,close,volume,is_filled,data_adjustment,instrument_id,data_source FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN '2026-10-01' AND :end AND data_source='alpaca_sip'",symbols,end=cutoff.date())
        prices.to_parquet(root/'prices.parquet',index=False)
        c.rollback()
    finally:c.close();engine.dispose()
    evaluate(root,cutoff,raw,features,quality,prices,oracle_info)


def evaluate(root,cutoff,raw,features,quality,prices,oracle_info,panel=None):
    atomic_json(root/'progress.json',dict(status='MEASURING_H5_H10_H20',features=len(features)))
    sched=calendar()
    if panel is None:
        panel=measure(features,prices,sched,cutoff)
    panel.to_parquet(root/'panel.parquet',index=False)
    report=dict(status='COMPLETED_EXPLORATORY',cutoff=str(cutoff),raw_rows=len(raw),
        raw_symbols=int(raw.symbol.nunique()),first_snapshot=str(raw.snapshot_date.min()),last_snapshot=str(raw.snapshot_date.max()),
        feature_rows=len(features),feature_dates=int(features.entry_day.nunique()),
        first_entry=str(features.entry_day.min()),last_entry=str(features.entry_day.max()),
        first_SIP_price=str(prices.date.min()),last_SIP_price=str(prices.date.max()),
        quality_rows=len(quality),raw_invalid=int((~quality.raw_normalization_ok).sum()),
        receipt_invalid=int((~quality.run_receipt_ok).sum()),oracle=oracle_info,results=summary(panel),
        no_independent_validation=True,strict_PIT=False,provider_calls=0,LLM_calls=0,orders=0,SQL_writes=0)
    atomic_json(root/'report.json',report)
    flat=[]
    for row in report['results']:
        for cohort in ('all_same_eligible','positive','negative','nonoverlap_positive'):
            flat.append(dict(scope=row['scope'],horizon=row['horizon'],signal=row['signal'],cohort=cohort,**row[cohort]))
    pd.DataFrame(flat).to_csv(root/'comparison.csv',index=False)
    atomic_json(root/'progress.json',dict(status=report['status'],feature_rows=len(features),report=str(root/'report.json')))
    print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False),flush=True)


def offline(root,parent):
    root.mkdir(parents=True,exist_ok=False)
    p=json.loads((parent/'protocol.json').read_text(encoding='utf-8'))
    names=['consensus.parquet','runs.parquet','features.parquet','quality.parquet','prices.parquet','oracle-scores.parquet']
    seal_path=parent/'features-seal.json'
    if not seal_path.exists():
        seal_path=Path(p['offline_parent'])/'features-seal.json'
    seal=json.loads(seal_path.read_text(encoding='utf-8'))
    for name,expected in seal['files'].items():
        if digest(parent/name)!=expected:raise ValueError('Snapshot parent modifié : '+name)
    if (parent/'panel.parquet').exists():names.append('panel.parquet')
    p.update(offline_parent=str(parent),offline_only=True,amendment='SQL numeric/null normalization and explicit integer AUC target; frozen inputs and per-case outcomes unchanged',
        sources={str(Path(__file__)):digest(Path(__file__))},parent_hashes={n:digest(parent/n) for n in names})
    atomic_json(root/'protocol.json',p)
    for name in names:shutil.copyfile(parent/name,root/name)
    raw=pd.read_parquet(root/'consensus.parquet');features=pd.read_parquet(root/'features.parquet')
    quality=pd.read_parquet(root/'quality.parquet');prices=pd.read_parquet(root/'prices.parquet')
    symbols=sorted({s for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig')) if s})
    _,info=oracle_ranks(pd.read_parquet(root/'oracle-scores.parquet'),symbols)
    panel=pd.read_parquet(root/'panel.parquet') if (root/'panel.parquet').exists() else None
    if panel is not None and len(panel)!=3*len(features):raise ValueError('Panel d’horizons incomplet')
    evaluate(root,pd.Timestamp(p['cutoff']),raw,features,quality,prices,info,panel=panel)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT)
    parser.add_argument('--reuse-snapshot',type=Path)
    parser.add_argument('--offline-parent',type=Path)
    args=parser.parse_args()
    try:
        if args.offline_parent:offline(args.output_dir,args.offline_parent)
        else:run(args.output_dir,args.reuse_snapshot)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
