"""Read-only diagnostic of the archived bundle; never a portfolio replay."""
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.build_labels import build_labels
from modelFactory.oracle.extreme_gate import compute_extreme_gate

BATCH = 'model-factory-20260903174624-014164'
ROOT = Path('artifacts/research/us_common_degradation/original-monthly-20261005-v1')


def long_mask(frame):
    return (frame.proba_long.gt(.55) & frame.proba_long.gt(frame.proba_short)
            & frame.proba_long.gt(frame.proba_flat)
            & (frame.proba_long-frame.proba_short).ge(.02))


def summarize(frame, policy):
    rows = []
    for month, group in frame.groupby(pd.to_datetime(frame.date).dt.strftime('%Y-%m')):
        valid = group[group.target_quality_valid.eq(1) & group.oracle_decile.notna()
                      & group.future_return.notna()]
        rows.append(dict(policy=policy, month=month, candidates=len(group), evaluated=len(valid),
            unknown=len(group)-len(valid), symbols=group.symbol.nunique(),
            d1_pct=100*valid.oracle_decile.eq(1).mean() if len(valid) else None,
            d10_pct=100*valid.oracle_decile.eq(10).mean() if len(valid) else None,
            mean_return_h20_pct=100*valid.future_return.mean() if len(valid) else None,
            median_return_h20_pct=100*valid.future_return.median() if len(valid) else None,
            positive_return_pct=100*valid.future_return.gt(0).mean() if len(valid) else None))
    return rows


def run():
    ROOT.mkdir(parents=True, exist_ok=True)
    def progress(stage, **kwargs):
        payload = dict(stage=stage, **kwargs)
        (ROOT/'progress.json').write_text(json.dumps(payload, default=str), encoding='utf-8')
        print(json.dumps(payload, default=str), flush=True)
    (ROOT/'protocol.json').write_text(json.dumps(dict(batch=BATCH, no_sql_writes=True,
        no_training=True, pool_pct=.2, long_min_prob=.55, margin=.02,
        policy='current strict ternary rule, not verified archived backtest configuration',
        no_atr_filter=True, no_portfolio_or_cost_replay=True), indent=2), encoding='utf-8')
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('US database required')
        symbols_raw = conn.execute(text('SELECT symbols FROM model_training_batch WHERE batch_id=:b'),
                                   {'b': BATCH}).scalar_one()
        symbols = [s.strip() for s in str(symbols_raw).split(',') if s.strip()]
        progress('READ_ORIGINAL_PREDICTIONS', symbols=len(symbols))
        oracle = pd.read_sql(text('SELECT prediction_date AS date,symbol,proba_extreme '
            'FROM oracle_extreme_predictions WHERE batch_id=:b '
            'AND prediction_date BETWEEN :s AND :e'), conn,
            params={'b': BATCH, 's': '2024-07-01', 'e': '2026-06-30'})
        predictions = pd.read_sql(text('SELECT p.prediction_date AS date,p.symbol,p.proba_long,'
            'p.proba_short,p.proba_flat,p.predicted_side,p.run_id,p.source '
            'FROM model_predictions p WHERE p.model_role=\'directional_bundle\' '
            'AND p.run_id IN (SELECT run_id FROM model_training_run WHERE batch_id=:b) '
            'AND p.prediction_date BETWEEN :s AND :e'), conn,
            params={'b': BATCH, 's': '2024-07-01', 'e': '2026-06-30'})
    for name, frame in [('oracle', oracle), ('directional', predictions)]:
        frame.date = pd.to_datetime(frame.date)
        if frame.duplicated(['date', 'symbol']).any():
            raise ValueError(f'Ambiguous duplicate {name} predictions')
        frame.to_parquet(ROOT/f'{name}_snapshot.parquet', index=False)
    path = ROOT/'native_labels.parquet'
    if not path.exists():
        progress('NATIVE_LABELS_DRY_RUN')
        status = build_labels(BATCH, horizon=20, start_date='2024-07-01', end_date='2026-06-30',
            engine=engine, dry_run=True, symbols=symbols, output_parquet=str(path),
            progress_callback=lambda n,t,m: progress('NATIVE_LABELS_DRY_RUN', current=n,total=t,message=m))
        (ROOT/'labels_quality.json').write_text(json.dumps(status, default=str, indent=2), encoding='utf-8')
    labels = pd.read_parquet(path).rename(columns={'prediction_date': 'date'})
    labels.date = pd.to_datetime(labels.date)
    pool = compute_extreme_gate(oracle)
    pool = pool[pool.extreme_gate].merge(labels[['date','symbol','oracle_decile','future_return',
        'target_quality_valid']], on=['date','symbol'], how='left', validate='one_to_one')
    joined = pool.merge(predictions, on=['date','symbol'], how='left', validate='one_to_one', indicator=True)
    available = joined[joined._merge.eq('both')]
    selected = available[long_mask(available)]
    monthly = (summarize(pool,'ORACLE_TOP20') + summarize(available,'ORACLE_TOP20_SERVABLE')
               + summarize(selected,'ORACLE_TOP20_FIXED_LONG'))
    pd.DataFrame(monthly).to_csv(ROOT/'monthly.csv', index=False)
    joined.to_parquet(ROOT/'joined_diagnostic.parquet', index=False)
    report = dict(status='DIRECTIONAL_DIAGNOSTIC_COMPLETE_PORTFOLIO_BLOCKED', batch=BATCH,
        oracle_rows=len(oracle), real_directional_rows=len(predictions),
        oracle_pool_rows=len(pool), pool_with_real_directional_rows=len(available),
        fixed_long_rows=len(selected), monthly=monthly,
        limitations=['No original trade ledgers/config: this is not reproduction of net backtest PnL',
            'H20 adjusted close-to-close returns, not next-open entries or lifecycle exits',
            'Original Oracle universe preserved; never substituted by current Oracle x ATR',
            'Correlated overlapping outcomes; counts are not independent observations',
            'No historical data-vintage proof restored by reconstructing labels'])
    (ROOT/'report.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    progress('COMPLETED', report=str(ROOT/'report.json'))
    print(pd.DataFrame(monthly).query("month >= '2026-01'").to_string(index=False), flush=True)


if __name__ == '__main__':
    run()
