"""Read-only refresh of actually received US signals; no provider, fit or orders."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re
import dataclasses

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from scripts.research.us_options_equal_mix_20261026 import digest, read, write
from scripts.research.us_consensus_observed_revision_pilot import connect_readonly

UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
TABLES = {
    'stock_option_snapshots': ('underlying_symbol', 'available_at'),
    'stock_option_bars_delayed': ('underlying_symbol', 'available_at'),
    'stock_analyst_consensus_eodhd_history': ('symbol', 'available_at'),
    'stock_borrow_status_snapshots': ('symbol', 'available_at'),
    'stock_opening_window_bars': ('symbol', 'available_at'),
    'sec_filing_raw': ('symbol', 'available_at'),
    'sec_corporate_events': ('symbol', 'available_at'),
    'sec_ownership_snapshots': ('issuer_symbol', 'available_at'),
    'stock_fundamentals_daily': ('symbol', 'fetched_at'),
    'stock_earnings_calendar': ('symbol', 'last_updated'),
    'ticker_daily_sentiment_features': ('symbol', 'updated_at'),
    'stock_short_volume_daily': ('symbol', 'available_at'),
}


def query(conn, sql, **params):
    if not sql.lstrip().upper().startswith('SELECT'):
        raise ValueError('SELECT only')
    stmt = text(sql)
    for name in ('symbols', 'batches'):
        if name in params:
            stmt = stmt.bindparams(bindparam(name, expanding=True))
    return [dict(r) for r in conn.execute(stmt, params).mappings()]


def inventory(root):
    root.mkdir(parents=True, exist_ok=False)
    cutoff = pd.Timestamp.now(tz='UTC')
    symbols = sorted({s.upper() for s in re.split(r'[,;\s]+', UNIVERSE.read_text(encoding='utf-8-sig')) if s})
    sources = [Path(__file__), UNIVERSE, Path('config.yaml'), Path('batch.yaml')]
    write(root/'protocol.json', dict(cutoff=cutoff, start='2026-09-10', symbols=symbols,
        ranks=[10, 20, 50], horizons=[5, 10, 15, 20], stop_loss_pct=.10,
        decision='5 minutes before next official US opening',
        ranking='Original Oracle H20 TOPN before signal coverage or outcomes; no refill',
        model_policy={'2026-09':'model-factory-20261014113232-bc35a7',
                      '2026-10':'model-factory-20261016180250-3b0515',
                      '2026-11':'model-factory-20261016180250-3b0515'},
        SQL='READ ONLY REPEATABLE READ UTC; rollback', provider_calls=0, llm_calls=0,
        training=False, new_inference=False, orders=False, sql_writes=False,
        selection='Frozen signal definitions from preceding audits, no threshold/weight search',
        sources={str(p):digest(p) for p in sources}))
    engine, conn = connect_readonly()
    out = dict(cutoff=cutoff, universe_count=len(symbols), tables={})
    try:
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
        schema = query(conn, 'SELECT TABLE_NAME,COLUMN_NAME,DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE()')
        write(root/'schema.json', schema)
        cols = {t:{r['COLUMN_NAME'] for r in schema if r['TABLE_NAME']==t} for t in TABLES}
        params = dict(symbols=symbols, start='2026-09-10', cutoff=cutoff.tz_localize(None).to_pydatetime())
        for table, (symbol, stamp) in TABLES.items():
            print('Inventory '+table, flush=True)
            if not {symbol, stamp}.issubset(cols[table]):
                out['tables'][table] = dict(status='MISSING_SCHEMA'); continue
            rows = query(conn, f'''SELECT DATE({stamp}) day,COUNT(*) n,COUNT(DISTINCT {symbol}) symbols,
                MIN({stamp}) first_available,MAX({stamp}) last_available FROM {table}
                WHERE {symbol} IN :symbols AND {stamp}>=:start AND {stamp}<=:cutoff
                GROUP BY DATE({stamp}) ORDER BY day''', **params)
            out['tables'][table] = dict(daily=rows, rows=sum(r['n'] for r in rows),
                observation_days=len(rows), first_available=rows[0]['first_available'] if rows else None,
                last_available=rows[-1]['last_available'] if rows else None)
        out['runs'] = query(conn, '''SELECT batch_name,status,COUNT(*) n,MIN(started_at) first_run,
            MAX(started_at) last_run,SUM(requested_count) requested,SUM(received_count) received,
            SUM(persisted_count) persisted,SUM(failed_count) failed FROM pit_collection_runs
            WHERE started_at>=:start AND started_at<=:cutoff GROUP BY batch_name,status''',
            start=params['start'], cutoff=params['cutoff'])
        out['oracle'] = query(conn, '''SELECT p.batch_id,l.target_horizon,COUNT(*) n,
            COUNT(DISTINCT p.prediction_date) dates,COUNT(DISTINCT p.symbol) symbols,
            MIN(p.prediction_date) first_day,MAX(p.prediction_date) last_day
            FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l
            ON p.batch_id=l.batch_id AND p.symbol=l.symbol AND p.prediction_date=l.prediction_date
            WHERE p.prediction_date>=:start AND p.created_at<=:cutoff
            GROUP BY p.batch_id,l.target_horizon''', start=params['start'], cutoff=params['cutoff'])
        conn.rollback()
    finally:
        conn.close(); engine.dispose()
    write(root/'inventory.json', out)
    print('INVENTORY_COMPLETE', flush=True)


def snapshot(root):
    if (root/'snapshot-seal.json').exists():
        raise FileExistsError('Immutable snapshot')
    p = read(root/'protocol.json'); cutoff = pd.Timestamp(p['cutoff'])
    from common.market_calendar import get_market_calendar
    from modelFactory.oracle_path.predict import load_contract
    from service.options_directional.config import load_options_filter_config
    from service.options_directional.runner import validate_oracle_lineage
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    cal = pd.DataFrame([dict(day=pd.Timestamp(s.session_date), opened=pd.Timestamp(s.open_at_utc),
        closed=pd.Timestamp(s.close_at_utc)) for s in cal.sessions(date(2026,9,1),date(2026,12,31)) if s.is_open])
    cal.to_parquet(root/'calendar.parquet', index=False)
    cfg = load_options_filter_config()
    models = {}; sources = {}
    for batch in set(p['model_policy'].values()):
        folder, protocol, _, folds = load_contract('artifacts/models', batch)
        if protocol['horizon'] != 20:
            raise ValueError('H20 Oracle required')
        models[batch] = dict(folds=folds, profile_hash=digest(folder/'feature_profile.json'))
        for name in ('protocol.json','feature_profile.json','report.json'):
            sources[str(folder/name)] = digest(folder/name)
        for fold in folds.values():
            sources[str(fold['model_file'])] = digest(fold['model_file'])
    for name in [__file__, 'service/options_directional/features.py',
        'scripts/research/us_options_top20_refresh_20261030.py',
        'scripts/research/us_consensus_reliability_20261022.py',
        'scripts/research/fr_p0_p1_directional_audit_20261026.py',
        'common/daily_bar_sources.py', 'config/data_quality/security_discontinuities.json',
        'service/options_directional/runner.py', 'service/eodhd/consensus_snapshot.py',
        'service/eodhd/symbols.py', 'common/options_directional_contract.py', 'config.yaml', UNIVERSE]:
        sources[str(name)] = digest(name)
    write(root/'snapshot-protocol.json', dict(parent_protocol_sha256=digest(root/'protocol.json'),
        sources=sources, options_config=cfg.snapshot(), models=models,
        min_oracle_coverage=cfg.min_oracle_coverage_ratio, max_export_rows=600000,
        consensus='0q fiscal end within J +/-100 days; most recent period then receipt; freshness 72h; >=3 analysts',
        consensus_basis_reserve='EPS basis not identified by EODHD; equal contributor count does not certify identities',
        maturity='All H official sessions must be closed and prices complete; no partial path',
        exploratory=True, independent_holdout=False))
    engine, conn = connect_readonly()
    params = dict(start=p['start'], cutoff=cutoff.tz_localize(None).to_pydatetime(),
                  batches=list(models), end=str(cutoff.date()))
    try:
        conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
        raw = pd.DataFrame(query(conn, '''SELECT p.prediction_date signal_day,p.symbol,p.proba_extreme,
            p.fold_start,p.batch_id,p.created_at prediction_created_at,l.created_at lineage_created_at,
            l.fold_start lineage_fold_start,l.model_available_date,l.target_name,l.target_horizon,
            l.model_sha256,l.feature_profile_sha256 FROM oracle_extreme_predictions p
            LEFT JOIN oracle_path_prediction_lineage l ON l.prediction_date=p.prediction_date
            AND l.symbol=p.symbol AND l.batch_id=p.batch_id WHERE p.batch_id IN :batches
            AND p.prediction_date BETWEEN :start AND :end AND p.created_at<=:cutoff''', **params))
        raw.to_parquet(root/'oracle-raw.parquet', index=False)
        raw['signal_day'] = pd.to_datetime(raw.signal_day)
        raw = raw[raw.symbol.isin(p['symbols']) & raw.signal_day.dt.strftime('%Y-%m').map(p['model_policy']).eq(raw.batch_id)]
        if raw.duplicated(['signal_day','symbol']).any():
            raise ValueError('Duplicate Oracle rows')
        if not (np.isfinite(raw.proba_extreme) & raw.proba_extreme.between(0,1)).all():
            raise ValueError('Invalid Oracle probabilities')
        rows=[]; coverage=[]; sessions=list(cal.day)
        for (day,batch), g in raw.groupby(['signal_day','batch_id'], sort=True):
            ratio=len(g)/len(p['symbols']); model=models[batch]
            item=dict(signal_day=day,batch_id=batch,count=len(g),ratio=ratio,
                      qualifies=ratio>=cfg.min_oracle_coverage_ratio, qualifies95=ratio>=.95)
            coverage.append(item)
            if not item['qualifies']:
                continue
            validate_oracle_lineage(g.to_dict('records'),day.date(),model['profile_hash'],model['folds'])
            g=g.sort_values(['proba_extreme','symbol'],ascending=[False,True]).head(50).copy()
            g['oracle_rank']=np.arange(1,len(g)+1)
            entry=sessions[sessions.index(day)+1]; decision=cal.set_index('day').loc[entry,'opened']-pd.Timedelta(minutes=5)
            if decision>=cutoff:
                continue
            g['entry_day'],g['decision_at'],g['oracle_coverage']=entry,decision,ratio
            g['physical_oracle']=(pd.to_datetime(g.prediction_created_at,utc=True).le(decision)
                & pd.to_datetime(g.lineage_created_at,utc=True).le(decision))
            rows.append(g)
        top=pd.concat(rows,ignore_index=True)
        top.to_parquet(root/'oracle-top50.parquet',index=False)
        pd.DataFrame(coverage).to_csv(root/'oracle-coverage.csv',index=False)
        params=dict(start=p['start'],cutoff=params['cutoff'],end=params['end'], symbols=sorted(top.symbol.unique()))
        queries={
            'snapshots': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,
                option_type,observed_at,available_at,provider_timestamp,open_interest,payload_hash,provider,feed
                FROM stock_option_snapshots WHERE provider='alpaca' AND feed='indicative'
                AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<=:cutoff
                AND observed_at<=:cutoff''',
            'volumes': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                bar_timestamp,observed_at,available_at,volume,payload_hash,provider,feed,provenance_status,timeframe
                FROM stock_option_bars_delayed WHERE provider='alpaca' AND timeframe='30Min'
                AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<=:cutoff
                AND bar_timestamp>=:start AND bar_timestamp<=:cutoff AND observed_at<=:cutoff''',
            'consensus': '''SELECT * FROM stock_analyst_consensus_eodhd_history WHERE provider='eodhd'
                AND horizon_raw='0q' AND fiscal_period_end BETWEEN '2026-06-01' AND '2027-03-31'
                AND symbol IN :symbols AND available_at>=:start AND available_at<=:cutoff AND observed_at<=:cutoff''',
            'sentiment': '''SELECT symbol,trade_date,news_count_1d,sentiment_net_mean_1d,
                sentiment_net_mean_3d,news_count_3d,created_at,updated_at,instrument_id
                FROM ticker_daily_sentiment_features WHERE symbol IN :symbols
                AND trade_date BETWEEN :start AND :end''',
            'prices': '''SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,
                data_adjustment,instrument_id,ingested_at,last_updated FROM stock_bars_daily
                WHERE symbol IN :symbols AND date BETWEEN :start AND :end
                AND data_source IN ('eodhd_eod','alpaca_sip')'''}
        for name,sql in queries.items():
            # Count before export: never silently truncate a dataset.
            required={k:params[k] for k in ('symbols','start','cutoff','end') if ':'+k in sql}
            count=query(conn,'SELECT COUNT(*) n FROM ('+sql+') bounded_export',**required)[0]['n']
            if count>600000:
                raise ValueError('Explicit export cap exceeded, partition required: '+name+' '+str(count))
            frame=pd.DataFrame(query(conn,sql,**required))
            if len(frame)!=count:
                raise ValueError('Snapshot count mismatch')
            frame.to_parquet(root/(name+'.parquet'),index=False)
            print(name+' '+str(len(frame))+' rows',flush=True)
        runs=pd.DataFrame(query(conn, '''SELECT run_id,status,started_at,finished_at FROM pit_collection_runs
            WHERE batch_name='eodhd_consensus_snapshot' AND started_at<=:cutoff''',cutoff=params['cutoff']))
        runs.to_parquet(root/'runs.parquet',index=False)
        conn.rollback()
    finally:
        conn.close();engine.dispose()
    write(root/'snapshot-seal.json',dict(files={f.name:digest(f) for f in root.iterdir()
        if f.is_file()},sources=sources))
    print('SNAPSHOT_COMPLETE '+str(len(top))+' TOP50 pairs',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['inventory','snapshot'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    (inventory if args.phase=='inventory' else snapshot)(args.output)
