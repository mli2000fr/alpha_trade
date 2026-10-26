"""Bounded FR P0/P1 inventory and protected-path diagnostics, READ ONLY.

Never backdate a reconstructed public export. H20 cannot be replaced by partial
paths; H5/H10 are separately labeled exploratory. No training, API, orders.
"""
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal
import argparse,csv,gzip,hashlib,json,math,os,shutil

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import text,bindparam

OPS=Path('artifacts/fr/operations')
OUTPUT=Path('artifacts/fr/research/p0_p1_directional/20261026-v1')
IDENTITIES=Path('artifacts/fr/sprint6c_reference/identities.jsonl.gz')
HORIZONS=(5,10,20)
SL=.10


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def stamp(v):
    t=pd.Timestamp(v)
    if t.tzinfo is None:raise ValueError('Explicit UTC/source timezone required')
    return t.tz_convert('UTC')
def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False,default=str),encoding='utf-8')


def protected_excursion(rows,side,sl=SL):
    """Daily OHLC gives bounds, not an invented high/low sequence on stop day."""
    entry=float(rows[0]['open']);best=0.;peak=None
    stop=float(Decimal(str(entry))*(Decimal('1')-Decimal(str(sl)) if side=='LONG'
        else Decimal('1')+Decimal(str(sl))))
    for row in rows:
        opened,high,low=map(float,[row['open'],row['high'],row['low']]);day=str(row['date'])
        if not (0<low<=min(opened,float(row['close']))<=max(opened,float(row['close']))<=high):
            raise ValueError('Unqualified OHLC')
        gap=opened<=stop if side=='LONG' else opened>=stop
        if gap:return dict(lower_pct=100*best,upper_pct=100*best,peak_day=peak,stop_day=day,stop_kind='GAP',ambiguous=False)
        move=max(0.,high/entry-1 if side=='LONG' else 1-low/entry)
        touched=low<=stop if side=='LONG' else high>=stop
        if touched:
            upper=max(best,move)
            return dict(lower_pct=100*best,upper_pct=100*upper,peak_day=peak,
                stop_day=day,stop_kind='INTRADAY',ambiguous=upper>best+1e-12)
        if move>best+1e-12:best,peak=move,day
    return dict(lower_pct=100*best,upper_pct=100*best,peak_day=peak,stop_day=None,stop_kind=None,ambiguous=False)


def compare_paths(long,short):
    if long['lower_pct']>short['upper_pct']+1e-9:direction='LONG'
    elif short['lower_pct']>long['upper_pct']+1e-9:direction='SHORT'
    else:direction='AMBIGUOUS_OR_TIE'
    if long['ambiguous'] or short['ambiguous']:first='INTRADAY_ORDER_UNKNOWN'
    elif not long['peak_day'] or not short['peak_day']:first='NO_TWO_POSITIVE_PEAKS'
    elif long['peak_day']==short['peak_day']:first='SAME_SESSION_ORDER_UNKNOWN'
    else:first='LONG' if long['peak_day']<short['peak_day'] else 'SHORT'
    return direction,first


def active_public_positions(rows,day,scope):
    holders=defaultdict(list)
    for r in rows:
        if (r['isin'] not in scope or r['publication_date']>str(day) or
                r['publication_end'] and r['publication_end']<=str(day)):continue
        holders[r['isin'],r['holder']].append(r)
    result=defaultdict(dict);ambiguous=0
    for (isin,holder),group in holders.items():
        latest=max((r['publication_date'],r['position_date']) for r in group)
        values={r['ratio_percent'] for r in group if (r['publication_date'],r['position_date'])==latest}
        if len(values)!=1:ambiguous+=1;continue
        ratio=next(iter(values))
        if ratio>=.5:result[isin][holder]=ratio
    return dict(result),ambiguous


def sql_snapshot(output,symbols,cutoff,last_day):
    from database.router import get_market_engine
    engine=get_market_engine('FR_EQ',database_alias='fr_primary')
    if engine.url.database!='alpha_trade_fr':raise ValueError('FR only; no fallback')
    tables={};start=date(2026,9,1)
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=30000'))
            conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade_fr':raise ValueError('Wrong database')
            for table in ['fr_provider_bars_staging','fr_provider_bars_daily','stock_bars_daily']:
                symbol='provider_symbol' if table=='fr_provider_bars_staging' else 'instrument_id'
                row=dict(conn.execute(text(f'SELECT COUNT(*) n,COUNT(DISTINCT {symbol}) symbols,'
                    f'MIN(session_date) first_session,MAX(session_date) last_session,'
                    f'MIN(available_at) first_available,MAX(available_at) last_available FROM {table}')).mappings().one())
                tables[table]=row
            query=text('''SELECT provider,provider_symbol,session_date,raw_payload_id,
                open_price,high_price,low_price,close_price,provider_volume_split_adjusted,
                quality_code,observed_at,available_at FROM fr_provider_bars_staging
                WHERE provider='eodhd' AND provider_symbol IN :symbols AND session_date BETWEEN :start AND :end
                AND available_at <= :cutoff ORDER BY provider_symbol,session_date,available_at,raw_payload_id''').bindparams(bindparam('symbols',expanding=True))
            rows=[dict(r) for r in conn.execute(query,dict(symbols=symbols,start=start,end=last_day,
                cutoff=cutoff.tz_localize(None).to_pydatetime())).mappings()]
            conn.rollback()
    finally:engine.dispose()
    frame=pd.DataFrame(rows)
    for col in ['open_price','high_price','low_price','close_price','provider_volume_split_adjusted']:
        frame[col]=pd.to_numeric(frame[col])
    for col in ['observed_at','available_at']:frame[col]=pd.to_datetime(frame[col],utc=True)
    frame['session_date']=pd.to_datetime(frame.session_date)
    frame.to_parquet(output/'staging-recent.parquet',index=False)
    return frame,tables


def inventory(output,cutoff,cfg,reference):
    from service.fr.event_data_qualification_11b import parse_positions,public_day
    selected={n:v for n,v in cfg.items() if isinstance(v,dict) and v.get('priority') in ('P0','P1')}
    report={'batches':{},'raw_hash_errors':[]};sources={};amf=[];dila={};actions=defaultdict(set)
    for batch,config in selected.items():
        root=OPS/batch
        rows=[]
        if batch=='fr_daily_bars_sync':root=OPS/'eodhd_daily'
        if batch=='fr_calendar_snapshot':root=OPS/'calendar'
        files=sorted((root/'observations').rglob('*.json')) if batch!='fr_calendar_snapshot' else sorted(root.glob('*.json'))
        for file in files:
            observation=read(file)
            rawstamp=observation.get('available_at') or observation.get('observed_at')
            if not rawstamp or stamp(rawstamp)>cutoff:continue
            rows.append(dict(path=str(file),at=stamp(rawstamp),payload=observation));sources[str(file)]=digest(file)
        item=dict(priority=config['priority'],enabled=config['enabled'],status=config['status'],
            observations=len(rows),observation_days=len({r['at'].date() for r in rows}),
            first_available=min((r['at'] for r in rows),default=None),last_available=max((r['at'] for r in rows),default=None))
        if batch in ('fr_db_backup','fr_artifacts_backup'):
            item['role']='BACKUP_NOT_DIRECTIONAL_DATA';report['batches'][batch]=item;continue
        for observation in rows:
            meta=observation['payload'];key=meta.get('raw_sha256')
            if not key or batch not in ('fr_amf_short_sync','fr_dila_disclosures_sync'):continue
            raw=root/'raw'/(key+'.json')
            if not raw.exists() or digest(raw)!=key:
                report['raw_hash_errors'].append(str(raw));continue
            sources[str(raw)]=key;payload=read(raw)
            if batch=='fr_amf_short_sync':
                positions,rejected=parse_positions(payload['csv_utf8'].encode('utf-8'))
                positions=[r for r in positions if r['isin'] in reference]
                active,ambiguous=active_public_positions(positions,observation['at'].date(),reference)
                amf.append(dict(available_at=observation['at'],raw_sha256=key,positions=active,
                    historical_rows=len(positions),historical_isins=len({r['isin'] for r in positions}),
                    rejected_rows=len(rejected),ambiguous_holder_groups=ambiguous))
            else:
                for record in payload['records']:
                    isin=record.get('identificationsociete_iso_cd_isi');identifier=record.get('uin_idt_uin')
                    published=public_day(record)
                    if (isin not in reference or not identifier or not published
                            or published>meta['window'][1]):continue
                    logical=isin,identifier
                    if logical not in dila or observation['at']<dila[logical]['available_at']:
                        dila[logical]=dict(isin=isin,identifier=identifier,available_at=observation['at'],
                            category=record.get('sous_type_d_information'),title=record.get('informationdeposee_inf_tit_inf'),
                            raw_sha256=key)
        report['batches'][batch]=item
    amf.sort(key=lambda r:r['available_at'])
    if amf:
        report['amf']=dict(snapshots=len(amf),reconstructed_historical_rows=amf[-1]['historical_rows'],
            historical_isins=amf[-1]['historical_isins'],current_isins_with_public_position=len(amf[-1]['positions']),
            first_available=amf[0]['available_at'],last_available=amf[-1]['available_at'],
            historical_dates_not_old_vintages=True,below_threshold_not_zero=True)
    report['dila']=dict(unique_documents=len(dila),isins=len({r['isin'] for r in dila.values()}),
        categories=dict(Counter(r['category'] for r in dila.values())),pdf_texts_collected=0,
        directional_event_facts_qualified=0)
    # Exclude known vendor actions as a conservative diagnostic gate, not proof
    # of absence/independent corporate-action qualification.
    for file in sorted((OPS/'fr_corporate_actions_sync/latest').glob('*.json')):
        p=read(file);sources[str(file)]=digest(file)
        for day,events in p['events'].items():
            if events:actions[p['symbol']].add(day)
    checkpoint=OPS/'fr_security_master_sync/checkpoint.json'
    if checkpoint.exists():
        p=read(checkpoint);sources[str(checkpoint)]=digest(checkpoint)
        report['master']=dict(checkpoint_end=p.get('end'),canonical_go=p.get('canonical_go'),
            continuity_confirmed=p.get('delta_publication_continuity_confirmed'),anomalies=len(p.get('anomalies',[])))
    frozen=output/'public-observations.json'
    write(frozen,dict(amf=amf,dila=list(dila.values()),known_vendor_actions=dict((s,sorted(ds)) for s,ds in actions.items())))
    return report,sources,amf,dila,actions


def evaluate(frame,cal,amf,scope,actions,last_day):
    output=[];issues=Counter();days=[s.session_date for s in cal if s.is_open]
    latest=(frame.sort_values(['available_at','raw_payload_id']).drop_duplicates(['provider_symbol','session_date'],keep='last'))
    groups={s:f.set_index('session_date') for s,f in latest.groupby('provider_symbol')}
    first=amf[0]['available_at']
    entries=[s for s in cal if s.is_open and pd.Timestamp(s.open_at_utc)>first and s.session_date<=last_day]
    for session in entries:
        opened=stamp(session.open_at_utc);eligible=[a for a in amf if a['available_at']<opened]
        snapshot=eligible[-1];previous=eligible[-2] if len(eligible)>1 else None
        i=days.index(session.session_date)
        for symbol,identity in scope.items():
            prices=groups.get(symbol);isin=identity['isin'];holders=snapshot['positions'].get(isin)
            oldholders=previous['positions'].get(isin) if previous else None
            common=set(holders or {}).intersection(oldholders or {})
            features=dict(amf_public_short_score=-sum(holders.values()) if holders else None,
                amf_common_holder_change_score=-sum(holders[h]-oldholders[h] for h in common) if common else None)
            prior=frame[(frame.provider_symbol==symbol)&frame.available_at.lt(opened)&frame.session_date.lt(pd.Timestamp(session.session_date))]
            prior=prior.sort_values(['available_at','raw_payload_id']).drop_duplicates('session_date',keep='last').sort_values('session_date')
            prior=prior[prior.quality_code.eq('VALID')]
            for lag in [5,20]:
                expected=pd.DatetimeIndex(days[max(0,i-lag-1):i])
                p=prior.set_index('session_date').reindex(expected)
                features['momentum_'+str(lag)]=(float(p.close_price.iloc[-1]/p.close_price.iloc[0]-1)
                    if len(p)==lag+1 and p.close_price.notna().all() else None)
            for horizon in HORIZONS:
                expected=days[i:i+horizon]
                record=dict(symbol=symbol,isin=isin,entry_day=str(session.session_date),horizon=horizon,
                    feature_available_at=snapshot['available_at'],entry_at=opened,**features)
                if len(expected)<horizon or expected[-1]>last_day:
                    record['status']='NOT_MATURE';output.append(record);continue
                if prices is None:
                    record['status']='MISSING_PRICES';output.append(record);continue
                p=prices.reindex(pd.DatetimeIndex(expected))
                if p.open_price.isna().any() or not p.quality_code.eq('VALID').all():
                    record['status']='INCOMPLETE_OR_INVALID_PRICES';output.append(record);continue
                if any(str(d) in actions.get(symbol,set()) for d in expected):
                    record['status']='KNOWN_VENDOR_ACTION_RESERVED';output.append(record);continue
                rows=[dict(date=str(d.date()),open=r.open_price,high=r.high_price,low=r.low_price,close=r.close_price)
                    for d,r in p.iterrows()]
                long,short=protected_excursion(rows,'LONG'),protected_excursion(rows,'SHORT')
                direction,first_peak=compare_paths(long,short)
                record.update(status='DIAGNOSTIC_LABEL' if direction!='AMBIGUOUS_OR_TIE' else 'AMBIGUOUS_PATH',
                    dominant_direction=direction,first_peak=first_peak)
                record.update({'long_'+k:v for k,v in long.items()});record.update({'short_'+k:v for k,v in short.items()})
                output.append(record)
    return pd.DataFrame(output),entries


def statistics(frame):
    from sklearn.metrics import roc_auc_score
    report={}
    for horizon in HORIZONS:
        all_rows=frame[frame.horizon.eq(horizon)];valid=all_rows[all_rows.status.eq('DIAGNOSTIC_LABEL')]
        result=dict(status_counts=all_rows.status.value_counts().to_dict(),symbols=int(valid.symbol.nunique()),
            entry_dates=int(valid.entry_day.nunique()),long_dominant=int(valid.dominant_direction.eq('LONG').sum()),
            short_dominant=int(valid.dominant_direction.eq('SHORT').sum()),features={})
        for feature in ['amf_public_short_score','amf_common_holder_change_score','momentum_5','momentum_20']:
            sample=valid[valid[feature].notna()]
            daily=[]
            for day,g in sample.groupby('entry_day'):
                if g.dominant_direction.nunique()==2 and g[feature].nunique()>1:
                    daily.append(dict(day=day,auc=float(roc_auc_score(g.dominant_direction.eq('LONG'),g[feature])),n=len(g)))
            # A single first date per security removes repeated same-name paths;
            # it does NOT create independent market episodes or a validation set.
            unique=sample.sort_values('entry_day').drop_duplicates('symbol')
            result['features'][feature]=dict(n=len(sample),symbols=int(sample.symbol.nunique()),
                dates=int(sample.entry_day.nunique()),mean_daily_auc=float(np.mean([r['auc'] for r in daily])) if daily else None,
                daily=daily,first_observation_per_symbol_n=len(unique),
                first_observation_per_symbol_auc=float(roc_auc_score(unique.dominant_direction.eq('LONG'),unique[feature]))
                    if unique.dominant_direction.nunique()==2 and unique[feature].nunique()>1 else None)
        report[str(horizon)]=result
    return report


def run(output):
    cutoff=pd.Timestamp.now(tz='UTC');output.mkdir(parents=True,exist_ok=False)
    cfg=yaml.safe_load(Path('batch_fr.yaml').read_text(encoding='utf-8-sig'))
    from common.market_calendar import get_market_calendar
    from service.fr.eodhd_daily_15b import symbol_windows
    cal=[s for s in get_market_calendar('FR_EQ',allow_us_weekday_fallback=False).sessions(date(2026,8,1),date(2026,12,15)) if s.is_open]
    last_day=max(s.session_date for s in cal if pd.Timestamp(s.close_at_utc)<cutoff)
    with gzip.open(IDENTITIES,'rt',encoding='utf-8') as f:identities=[json.loads(line) for line in f if line.strip()]
    active={r['provider_symbol']:r for r in identities if r['identity_state']=='VERIFIED_RESEARCH' and r['provider_status_current']=='active'}
    bars_cfg=cfg['fr_daily_bars_sync']
    windows=symbol_windows(IDENTITIES,date(2026,9,1),last_day,bars_cfg.get('provider_symbol_migrations'),
        excluded_symbols=bars_cfg.get('excluded_symbols'))
    for migration in bars_cfg.get('provider_symbol_migrations',[]):
        if migration['new_symbol'] in windows:active[migration['new_symbol']]=active[migration['old_symbol']]
    scope={s:active[s] for s in windows}
    sources={str(p):digest(p) for p in [Path(__file__),Path('tests/test_fr_p0_p1_directional_audit_20261026.py'),
        Path('doc/fr/audit_directionnel_p0_p1_protocole_20261026.md'),Path('batch_fr.yaml'),IDENTITIES,
        Path('service/fr/event_data_qualification_11b.py'),Path('service/fr/eodhd_daily_15b.py'),
        Path('common/market_calendar.py'),Path('database/router.py')]}
    shutil.copyfile(IDENTITIES,output/'identities.jsonl.gz');shutil.copyfile('batch_fr.yaml',output/'batch_fr.yaml')
    write(output/'protocol.json',dict(created_at_utc=cutoff,scope='FR_EQ alpha_trade_fr P0/P1 only',
        symbols=len(scope),horizons=HORIZONS,stop_loss_pct=SL,
        target='Larger favorable excursion before fixed10% adverse stop, LONG/SHORT separately; not terminal return or executable peak exit',
        observation_rule='Proofs received strictly before next entry open after the observed close; never use source historical event date as observation',
        intraday_order='Daily stop-day favorable extrema bounded; unresolved direction/order reserved',
        primary_horizon=20,secondary_horizons='5/10 descriptive only, never replace H20',
        training=False,SQL='FR SELECT ONLY repeatable-read/rollback',API=0,orders=False,production_changed=False))
    inventory_report,archive_sources,amf,dila,actions=inventory(output,cutoff,cfg,{r['isin'] for r in identities})
    sources.update(archive_sources)
    if inventory_report['raw_hash_errors']:raise ValueError('Corrupted public archive')
    frame,tables=sql_snapshot(output,sorted(scope),cutoff,last_day)
    labels,entries=evaluate(frame,cal,amf,scope,actions,last_day)
    labels.to_parquet(output/'protected-path-diagnostics.parquet',index=False)
    first_entry=entries[0];start_index=next(i for i,s in enumerate(cal) if s.session_date==first_entry.session_date)
    h20_last=cal[start_index+19].session_date
    stats=statistics(labels)
    report=dict(status='AUDIT_COMPLETE_H20_NOT_YET_VALIDATED',cutoff_utc=cutoff,latest_closed_session=last_day,
        universe_symbols=len(scope),current_reference_not_historical_tradability=True,
        primary_H20_mature_labels=int(labels.horizon.eq(20).mul(labels.status.eq('DIAGNOSTIC_LABEL')).sum()),
        earliest_entry=first_entry.session_date,earliest_H20_last_session=h20_last,
        earliest_elapsed_sessions=sum(first_entry.session_date<=s.session_date<=last_day for s in cal),
        inventory=inventory_report,SQL_tables=tables,recent_staging_rows=len(frame),
        diagnostic=stats,verdict='NO_H20_DIRECTIONAL_VALIDATION_POSSIBLE_YET',
        limitations=['Short prospective history; secondary diagnostics overlap and are NOT out-of-sample validation',
            'Daily OHLC cannot resolve within-session peak order or stop/peak sequence',
            'AMF is threshold-censored public disclosure, not complete short interest or borrow',
            'DILA is metadata only, no qualified guidance/surprise/directional content',
            'Vendor prices/actions are research staging, no independent currency/actions release',
            'Current identity universe has survivorship/PIT limitations; no FR live promotion',
            'No economic backtest, executable peak exit, costs, borrow, or short tradability claim'],
        consensus_P3='Outside requested P0/P1 scope',rights_blocked_sources_used=False)
    write(output/'report.json',report);write(output/'sources.json',sources)
    write(output/'seal.json',dict(at_utc=pd.Timestamp.now(tz='UTC'),files={p.name:digest(p) for p in output.iterdir() if p.is_file()}))
    print(json.dumps(dict(output=str(output),status=report['status'],H20_labels=report['primary_H20_mature_labels'],
        first_entry=str(first_entry.session_date),first_H20_end=str(h20_last),stats=stats),default=str))


if __name__=='__main__':
    os.environ['SSLKEYLOGFILE']=''
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No HTTP in FR audit'))
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=OUTPUT)
    run(p.parse_args().output)
