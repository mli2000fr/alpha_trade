"""Read-only coverage diagnosis for stored CALL/PUT data, no provider or orders."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sqlalchemy import bindparam,event,inspect,text
import yaml

from database.connection import get_sqlalchemy_engine
from service.options_directional.features import build_features,_rows,_latest
from common.daily_bar_sources import select_daily_bars


def symbols(path):
    return sorted({s.upper() for s in re.split(r'[,;\s]+',Path(path).read_text(encoding='utf-8-sig')) if s})


def main():
    now=datetime.now(timezone.utc)
    output=Path('artifacts/operations/options_universe_coverage')/now.strftime('%Y%m%dT%H%M%SZ')
    output.mkdir(parents=True,exist_ok=False)
    cfg=yaml.safe_load(Path('batch.yaml').read_text(encoding='utf-8'))
    tradable=symbols('config/univers_batch/univers_filtred_tradable.txt')
    universe=symbols(cfg['oracle_options_indicative_snapshot']['symbols_file'])
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    def readonly(conn,cursor,statement,parameters,context,many):
        if statement.lstrip().split()[0].upper() not in ('SELECT','SHOW','DESCRIBE','SET'):
            raise ValueError('SQL read-only audit')
    event.listen(engine,'before_cursor_execute',readonly)
    report=dict(read_only=True,cutoff_utc=now.isoformat(),universe_file=cfg['oracle_options_indicative_snapshot']['symbols_file'],
        universe_count=len(universe),tradable_count=len(tradable),tradable_outside_collection=sorted(set(tradable)-set(universe)),runs=[])
    print(json.dumps({k:v for k,v in report.items() if k!='runs'}),flush=True)
    names=['oracle_options_indicative_snapshot','options_delayed_bars_sync']
    with engine.connect() as conn:
        columns=[c['name'] for c in inspect(engine).get_columns('pit_collection_runs')]
        print(json.dumps(dict(run_columns=columns)),flush=True)
        latest={}
        for name in names:
            rows=[dict(r) for r in conn.execute(text('SELECT * FROM pit_collection_runs WHERE batch_name=:name '
                'ORDER BY started_at DESC LIMIT 3'),dict(name=name)).mappings()]
            for r in rows:
                if isinstance(r.get('details_json'),str):r['details_json']=json.loads(r['details_json'])
            report['runs'].extend(rows)
            latest[name]=next((r for r in rows if r['status'] in ('SUCCESS','COMPLETED','OK','PARTIAL')),None)
            if latest[name] is None:
                latest[name]=next((r for r in rows if r.get('finished_at') and r.get('persisted_count',0)>0),None)
            if latest[name] is None:raise ValueError('No completed stored collection '+name)
            r=latest[name]
            detail=r.get('details_json') or {}
            compact={k:v for k,v in r.items() if k!='details_json'}
            compact['details']={k:v for k,v in detail.items() if k!='warnings'}
            compact['warning_examples']=(detail.get('warnings') or [])[:5]
            print(json.dumps(compact,default=str),flush=True)
        snap_run=latest[names[0]]['run_id'];vol_run=latest[names[1]]['run_id']
        references=set()
        for payload, in conn.execute(text("SELECT payload_json FROM pit_raw_payloads WHERE run_id=:run "
                "AND endpoint='/v2/stocks/bars?feed=sip&timeframe=1Min'"),dict(run=snap_run)):
            for symbol,item in json.loads(payload).items():
                price=(item.get('minuteBar') or {}).get('c')
                if isinstance(price,(int,float)) and np.isfinite(price) and price>0:references.add(symbol)
        snapshot_counts={}
        for entity,count in conn.execute(text("SELECT entity_key,JSON_LENGTH(payload_json,'$.snapshots') "
                "FROM pit_raw_payloads WHERE run_id=:run AND endpoint='/v1beta1/options/snapshots'"),dict(run=snap_run)):
            symbol=entity.split(':page:')[0]
            snapshot_counts[symbol]=snapshot_counts.get(symbol,0)+(count or 0)
        queries={
            'snapshots':'''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                observed_at,available_at,provider_timestamp,open_interest,payload_hash,provider,feed
                FROM stock_option_snapshots WHERE run_id=:run AND underlying_symbol IN :symbols''',
            'volumes':'''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                bar_timestamp,observed_at,available_at,volume,payload_hash,provider,feed,provenance_status,timeframe
                FROM stock_option_bars_delayed WHERE run_id=:run AND underlying_symbol IN :symbols AND timeframe='30Min' '''}
        frames={}
        for key,sql in queries.items():
            rows=[dict(r) for r in conn.execute(text(sql).bindparams(bindparam('symbols',expanding=True)),
                dict(run=snap_run if key=='snapshots' else vol_run,symbols=tradable)).mappings()]
            frames[key]=pd.DataFrame(rows)
        s=frames['snapshots'];v=frames['volumes']
        if s.empty or v.empty:raise ValueError('Latest stored collection empty for tradable')
        day=pd.to_datetime(v.bar_timestamp,utc=True).dt.tz_convert('America/New_York').dt.date.mode().iloc[0]
        prices=[dict(r) for r in conn.execute(text('SELECT symbol,date,close,is_filled,data_source FROM stock_bars_daily '
            "WHERE date=:day AND symbol IN :symbols AND data_source IN ('eodhd_eod','alpaca_sip')").bindparams(
                bindparam('symbols',expanding=True)),dict(day=day,symbols=tradable)).mappings()]
    price_frame=select_daily_bars(pd.DataFrame(prices)) if prices else pd.DataFrame()
    spots={} if price_frame.empty else {r.symbol:float(r.close) for r in price_frame.itertuples()
        if not r.is_filled and pd.notna(r.close) and r.close>0}
    features=build_features(s,v,spots,day,pd.Timestamp(now))
    oi=_rows(s,day,pd.Timestamp(now));flow=_rows(v,day,pd.Timestamp(now),volume=True)
    oi['open_interest']=pd.to_numeric(oi.open_interest,errors='coerce');oi['strike']=pd.to_numeric(oi.strike,errors='coerce')
    oi=_latest(oi,['symbol','contract_symbol'],['open_interest','strike','expiration_date','option_type','payload_hash'])
    oi=oi[np.isfinite(oi.open_interest)&oi.open_interest.ge(0)&(oi.strike/oi.symbol.map(spots)-1).abs().le(.05)]
    oi_pairs=oi.groupby(['symbol','expiration_date','strike']).option_type.agg(lambda x:set(x))
    oi_ok={idx[0] for idx,sides in oi_pairs.items() if {'CALL','PUT'}<=sides}
    flow['volume']=pd.to_numeric(flow.volume,errors='coerce')
    flow=_latest(flow,['symbol','contract_symbol','bar_timestamp'],['volume','payload_hash','option_type','expiration_date'])
    good=flow.groupby(['symbol','expiration_date','option_type']).volume.agg(lambda x:np.isfinite(x).all() and x.ge(0).all())
    valid=good[good].reset_index();flow_pairs=valid.groupby(['symbol','expiration_date']).option_type.agg(lambda x:set(x))
    flow_ok={idx[0] for idx,sides in flow_pairs.items() if {'CALL','PUT'}<=sides}
    s_all=set(s.symbol);v_all=set(v.symbol)
    rows=[]
    for symbol in tradable:
        reason=('QUALIFIED_COMBINED' if symbol in features else 'NO_STORED_SNAPSHOT_IN_LATEST_RUN' if symbol not in s_all
            else 'NO_STORED_VOLUME_IN_LATEST_RUN' if symbol not in v_all else 'NO_VALID_CLOSE_J' if symbol not in spots
            else 'NO_MATCHED_OI_PAIR_15_25D_ATM5PCT' if symbol not in oi_ok else 'NO_MATCHED_VOLUME_PAIR_15_25D'
            if symbol not in flow_ok else 'OTHER_CANONICAL_REJECTION')
        rows.append(dict(symbol=symbol,snapshot=symbol in s_all,volume=symbol in v_all,oi_pair=symbol in oi_ok,
            volume_pair=symbol in flow_ok,combined=symbol in features,reason=reason))
    report.update(session_date=str(day),latest_snapshot_run=snap_run,latest_volume_run=vol_run,
        stored_snapshot_symbols=len(s_all),stored_volume_symbols=len(v_all),qualified_oi_pairs=len(oi_ok),
        qualified_volume_pairs=len(flow_ok),qualified_combined=len(features),reasons=dict(Counter(r['reason'] for r in rows)),
        rows=rows,features=features)
    missing_detail=[]
    for symbol in sorted(set(tradable)-s_all):
        why=('NO_RECENT_SIP_REFERENCE' if symbol not in references else 'NO_ARCHIVED_SNAPSHOT_RESPONSE'
            if symbol not in snapshot_counts else 'EMPTY_PROVIDER_WINDOW' if snapshot_counts[symbol]==0
            else 'ALL_CONTRACTS_EXCLUDED_BY_COLLECTOR')
        missing_detail.append(dict(symbol=symbol,reason=why,raw_snapshot_contracts=snapshot_counts.get(symbol)))
    report['missing_snapshots_detail']=missing_detail
    report['missing_snapshots_reasons']=dict(Counter(r['reason'] for r in missing_detail))
    (output/'report.json').write_text(json.dumps(report,default=str,indent=2),encoding='utf-8')
    pd.DataFrame(rows).to_csv(output/'tradable_coverage.csv',index=False,encoding='utf-8-sig')
    print(json.dumps({k:report[k] for k in ('session_date','stored_snapshot_symbols','stored_volume_symbols',
        'qualified_oi_pairs','qualified_volume_pairs','qualified_combined','reasons')}),flush=True)
    print(json.dumps(dict(reason_examples={r:[x['symbol'] for x in rows if x['reason']==r][:10] for r in report['reasons']},
        report=str((output/'report.json').resolve()))),flush=True)
    print(json.dumps(dict(missing_snapshot_reasons=report['missing_snapshots_reasons'],
        examples=missing_detail[:15])),flush=True)
    engine.dispose()


if __name__=='__main__':main()
