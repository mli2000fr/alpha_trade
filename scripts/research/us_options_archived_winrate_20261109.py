"""Extend outcomes of immutable archived H20 ranks, including observed ranks.

Original model files were deleted later. Validate archived fold metadata and
lineage but never claim present-day model reproducibility/serving readiness.
"""
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from scripts.research import us_options_winrate_audit_20261109 as audit
from scripts.research.us_collected_directional_refresh_20261105 import query
from scripts.research.us_consensus_observed_revision_pilot import connect_readonly
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

SOURCE=Path('artifacts/research/us_collected_directional_refresh/20261105-v2')
ROOT=Path('artifacts/research/us_options_winrate/20261109-archived-v1')


def archived_ranks(source=SOURCE):
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    seal=read(source/'snapshot-seal.json')
    for name,sha in seal['files'].items():
        if digest(source/name)!=sha:raise ValueError('Archived snapshot changed '+name)
    protocol=read(source/'protocol.json');spec=read(source/'snapshot-protocol.json')
    top=pd.read_parquet(source/'oracle-top50.parquet');raw=pd.read_parquet(source/'oracle-raw.parquet')
    top['signal_day']=pd.to_datetime(top.signal_day);raw['signal_day']=pd.to_datetime(raw.signal_day)
    from service.options_directional.runner import validate_oracle_lineage
    pieces=[]
    for (batch,day),group in top.groupby(['batch_id','signal_day']):
        full=raw[raw.batch_id.eq(batch)&raw.signal_day.eq(day)&raw.symbol.isin(protocol['symbols'])].copy()
        if full.symbol.duplicated().any():raise ValueError('Duplicate archive ranking')
        m=spec['models'][batch]
        validate_oracle_lineage(full.to_dict('records'),day.date(),m['profile_hash'],m['folds'],horizon=20)
        expected=full.sort_values(['proba_extreme','symbol'],ascending=[False,True]).head(50)
        actual=group.sort_values('oracle_rank')
        if actual.symbol.tolist()!=expected.symbol.tolist() or not np.allclose(actual.proba_extreme,expected.proba_extreme):
            raise ValueError('Archived TOP50 disagrees with full ranking')
        decision=group.decision_at.iloc[0]
        physical=bool((pd.to_datetime(full.prediction_created_at,utc=True).lt(decision)
            &pd.to_datetime(full.lineage_created_at,utc=True).lt(decision)).all())
        group=group.copy();group['physical_oracle']=physical
        group['model_label']='H20_ARCHIVE_OBSERVABLE' if physical else 'H20_ARCHIVE_RECONSTRUIT'
        pieces.append(group)
    return pd.concat(pieces,ignore_index=True),protocol,spec


def run(root=ROOT):
    from common.config_loader import load_config
    from service.options_directional.config import load_options_filter_config
    root.mkdir(parents=True,exist_ok=False);cutoff=pd.Timestamp.now(tz='UTC')
    top,old,spec=archived_ranks();top.to_parquet(root/'oracle-top50.parquet',index=False)
    pd.read_parquet(SOURCE/'calendar.parquet').to_parquet(root/'calendar.parquet',index=False)
    cfg=load_config();sources={str(Path(__file__)):digest(Path(__file__)),str(Path(audit.__file__)):digest(Path(audit.__file__))}
    for name in ['service/options_directional/features.py','service/options_directional/runner.py','common/daily_bar_sources.py',
        'common/options_directional_contract.py','config/data_quality/security_discontinuities.json',
        'scripts/research/us_options_top20_refresh_20261030.py','scripts/research/fr_p0_p1_directional_audit_20261026.py']:
        sources[name]=digest(Path(name))
    protocol=dict(cutoff_utc=str(cutoff),start=old['start'],horizons=audit.HORIZONS,ranks=audit.RANKS,
        options=load_options_filter_config().snapshot(),sources=sources,
        price_config={'market_data':{'daily_bars_preferred_source':cfg.get('market_data',{}).get('daily_bars_preferred_source','eodhd')}},
        trade={'stop_loss':.05,'fees_per_leg':.0008,'exit':'open H+1'},source_archive=str(SOURCE),
        source_seal_sha256=digest(SOURCE/'snapshot-seal.json'),models=spec['models'],
        model_binary_status='DELETED_AFTER_ARCHIVE_METADATA_AND_LINEAGE_REVALIDATED_NOT_CURRENTLY_REPRODUCIBLE',
        provider_calls=0,orders=0,SQL_writes=0,training=False,new_inference=False)
    atomic_json(root/'protocol.json',protocol)
    engine,conn=connect_readonly()
    try:
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
        params=dict(symbols=sorted(top.symbol.unique()),start=old['start'],end=str(cutoff.date()),cutoff=cutoff.tz_localize(None).to_pydatetime())
        queries={
            'snapshots':'''SELECT id,provider,feed,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                observed_at,available_at,provider_timestamp,open_interest,payload_hash FROM stock_option_snapshots
                WHERE provider='alpaca' AND feed='indicative' AND underlying_symbol IN :symbols
                AND available_at>=:start AND available_at<=:cutoff AND observed_at<=:cutoff''',
            'volumes':'''SELECT id,provider,feed,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                bar_timestamp,observed_at,available_at,volume,payload_hash,provenance_status,timeframe FROM stock_option_bars_delayed
                WHERE provider='alpaca' AND timeframe='30Min' AND underlying_symbol IN :symbols
                AND available_at>=:start AND available_at<=:cutoff AND observed_at<=:cutoff AND bar_timestamp>=:start AND bar_timestamp<=:cutoff''',
            'prices':'''SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,data_adjustment,instrument_id,
                ingested_at,last_updated FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN :start AND :end
                AND data_source IN ('eodhd_eod','alpaca_sip')'''}
        for name,sql in queries.items():
            pp={k:v for k,v in params.items() if ':'+k in sql}
            n=query(conn,'SELECT COUNT(*) n FROM ('+sql+') bounded_export',**pp)[0]['n']
            if n>600000:raise ValueError('Partition required; no truncation')
            frame=pd.DataFrame(query(conn,sql,**pp))
            if len(frame)!=n:raise ValueError('Export count mismatch')
            frame.to_parquet(root/(name+'.parquet'),index=False);print(name,n,flush=True)
        conn.rollback()
    finally:conn.close();engine.dispose()
    atomic_json(root/'snapshot-seal.json',dict(files={p.name:digest(p) for p in root.iterdir() if p.is_file()},sources=sources))
    audit.analyze(root)


if __name__=='__main__':run()
