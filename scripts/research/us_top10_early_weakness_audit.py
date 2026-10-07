"""2023-2024 predicted TOP10: frozen SL7 replay and descriptive early paths.

SELECT only. No new fitting, threshold search, or future-based selection.
Current universe/sectors and archived OOF lineage remain explicit limitations.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, event, text

from common.config_loader import load_config
from database.connection import get_sqlalchemy_engine
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, decision_rows
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_extreme50_capture import forbid_writes
from service.market import parse_market_regimes


def early_paths(scores, bars):
    """Measure all original top10 paths, even after a simulated stop; no refill.

    J+1 open entry, observations at close of 1st/3rd/5th session since entry.
    H20 means entry session +20, not signal session +20.
    No forward fills; incomplete observations stay null and flagged.
    """
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0), 'date']).sort_values()
    prices = {s: g.set_index('date').sort_index() for s, g in bars.groupby('symbol')}
    rows = []
    for signal in scores.loc[scores.ORACLE_TOP10].to_dict('records'):
        day = pd.Timestamp(signal['date'])
        i = calendar.get_indexer([day])[0]
        base = dict(signal_date=day, symbol=signal['symbol'], score=signal['proba_extreme'])
        if i < 0 or i+21 >= len(calendar):
            rows.append(dict(base, path_status='INCOMPLETE_CALENDAR'))
            continue
        dates = calendar[i+1:i+22]
        path = prices[signal['symbol']].reindex(dates)
        good = (path[['open','high','low','close']].gt(0).all(axis=1)
                & np.isfinite(path[['open','high','low','close']]).all(axis=1)
                & path.volume.gt(0) & path.is_filled.eq(0))
        identity_ok = path.instrument_id.notna().all() and path.instrument_id.nunique() == 1
        if not good.all() or not identity_ok:
            rows.append(dict(base, path_status='UNQUALIFIED_PRICE_PATH'))
            continue
        entry = float(path.open.iloc[0])
        record = dict(base, path_status='LOCAL_VALID_NOT_INDEPENDENTLY_CERTIFIED',
                      entry_date=dates[0], entry_open=entry,
                      entry_plus20_date=dates[-1], hold_return=float(path.close.iloc[-1]/entry-1),
                      mae=float(path.low.min()/entry-1), mfe=float(path.high.max()/entry-1),
                      touched_initial_sl7=bool(path.low.le(entry*.93).any()))
        spy = prices['SPY'].reindex(dates)
        for n in (1,3,5):
            ret = float(path.close.iloc[n-1]/entry-1)
            spyret = float(spy.close.iloc[n-1]/spy.open.iloc[0]-1)
            record[f'return_j{n}'] = ret
            record[f'relative_spy_j{n}'] = ret-spyret
        rows.append(record)
    return pd.DataFrame(rows)


def summarize_paths(paths):
    valid = paths.loc[paths.path_status.eq('LOCAL_VALID_NOT_INDEPENDENTLY_CERTIFIED')].copy()
    rows = []
    if valid.empty:
        return rows
    valid['year'] = pd.to_datetime(valid.signal_date).dt.year
    valid['month'] = pd.to_datetime(valid.signal_date).dt.to_period('M').astype(str)
    for key in ('year','month'):
        for period, group in valid.groupby(key):
            for label, sample in [('ALL',group), ('HOLD_POSITIVE',group[group.hold_return.gt(0)]),
                                  ('HOLD_NONPOSITIVE',group[group.hold_return.le(0)]),
                                  ('HOLD_GE50PCT',group[group.hold_return.ge(.5)])]:
                if sample.empty:
                    continue
                row = dict(grouping=key, period=str(period), category=label, count=len(sample),
                           mean_hold_return=float(sample.hold_return.mean()),
                           stop_touch_rate=float(sample.touched_initial_sl7.mean()))
                for n in (1,3,5):
                    row[f'negative_at_j{n}_rate'] = float(sample[f'return_j{n}'].lt(0).mean())
                    row[f'weak_vs_spy_j{n}_rate'] = float(sample[f'relative_spy_j{n}'].lt(0).mean())
                rows.append(row)
    return rows


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output/'progress.json', {'status':'PREPARING'})
    source = Path('artifacts/research/us_extreme50_capture/audit-20261006-v1')
    reference = Path('artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-20261007-v1')
    contract = json.loads((reference/'contract.json').read_text())
    panels = [source/str(y)/'panel.parquet' for y in (2023,2024)]
    scores = decision_rows(pd.concat([pd.read_parquet(p) for p in panels], ignore_index=True))
    scores = scores.loc[scores.ORACLE_TOP10].copy()
    if scores.fold_start.isna().any() or (pd.to_datetime(scores.fold_start) > scores.date).any():
        raise ValueError('Missing or future fold_start: no final-model substitution allowed')
    scores.to_parquet(output/'scores.parquet',index=False)
    sector_path = Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet')
    if digest(sector_path) != contract['sector_sha256']:
        raise ValueError('Sector evidence changed')
    sectors = pd.read_parquet(sector_path).set_index('symbol').sector.to_dict()
    symbols = sorted(set(scores.symbol) | {'SPY'})
    missing_sectors = sorted(set(scores.symbol)-set(sectors))
    if missing_sectors:
        raise ValueError(f'Missing sector evidence: {missing_sectors}')
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    if json.loads(json.dumps(asdict(market),default=str)) != contract['market']:
        raise ValueError('Market configuration changed')
    atomic_json(output/'protocol.json', dict(start='2023-01-01',end='2024-12-31',
        policy='ORACLE_TOP10', initial_stop_pct=.07, tp=False, trailing=False,
        expiry='20 sessions after next-session entry', initial_equity=4000,
        sql_writes=False, training=False, threshold_search=False,
        sources={str(p):digest(p) for p in panels},
        source_protocol_sha256=digest(source/'protocol.json'),
        lineage='Archived fold_start present and <= signal date; full fold train/calibration provenance not certified here',
        limitations=['Static current universe: survivorship risk','Current sectors NON-PIT',
            'Price paths locally checked, not independently certified',
            'Macro daily archive not certified publication vintage',
            'Historical exploratory audit, not untouched independent confirmation',
            'Early path statistics are gross hypothetical buy-and-hold, not portfolio net PnL',
            'Sector-relative paths deferred; SPY-relative paths provided'],
        decision='No early-exit rule promoted or tuned in this diagnostic'))
    engine = get_sqlalchemy_engine()
    event.listen(engine,'before_cursor_execute',forbid_writes)
    try:
        with engine.connect() as conn:
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
                raise ValueError('US database required')
            query = text('SELECT date,symbol,open,high,low,close,adj_close,volume,is_filled,instrument_id FROM stock_bars_daily WHERE date BETWEEN :a AND :b AND symbol IN :symbols').bindparams(bindparam('symbols',expanding=True))
            bars = pd.read_sql(query,conn,params=dict(a='2022-01-01',b='2025-02-15',symbols=symbols))
            macro = pd.read_sql(text("SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN '2022-01-01' AND '2024-12-31'"),conn)
    finally:
        engine.dispose()
    bars['date'] = pd.to_datetime(bars.date)
    if bars.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate price key')
    bars.to_parquet(output/'bars.parquet',index=False)
    macro.to_parquet(output/'macro.parquet',index=False)
    atomic_json(output/'progress.json',{'status':'PATH_AUDIT','candidates':len(scores)})
    paths = early_paths(scores,bars)
    paths.to_parquet(output/'early-paths.parquet',index=False)
    atomic_json(output/'path-summary.json',summarize_paths(paths))
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0),'date']).sort_values()
    frames = {key:bars.pivot(index='date',columns='symbol',values=col).reindex(calendar)
              for key,col in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    atomic_json(output/'progress.json',{'status':'BASELINE_REPLAY'})
    result = run_portfolio(frames=frames,scores=scores,sectors=sectors,macro=ArchivedMacro(macro),
        market_config=market,policy='ORACLE_TOP10',variant='NO_TP_FIXED_SL_20_AFTER_ENTRY',
        output=output/'baseline',quality=bars[['date','symbol','is_filled','instrument_id']],
        initial_stop_pct=.07,reject_constrained_entries=True,start_date='2023-01-01',end_date='2024-12-31')
    atomic_json(output/'report.json',dict(status='COMPLETED_DESCRIPTIVE_AUDIT',baseline=result,
        path_status_counts=paths.path_status.value_counts().to_dict(),
        conclusion='Audit only: no early-exit advantage established; no deployment'))
    atomic_json(output/'progress.json',{'status':'COMPLETED'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args.output)
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output/'progress.json',{'status':'FAILED','error':str(exc)})
        raise
