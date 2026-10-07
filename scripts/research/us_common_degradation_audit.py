"""Monthly descriptive audit; original-run gaps never replaced by another batch."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def month_summary(frame):
    frame=frame.copy()
    frame['month']=pd.to_datetime(frame.trade_date).dt.strftime('%Y-%m')
    rows=[]
    for month,g in frame.groupby('month'):
        complete=g[g.unknown_count.eq(0)&g.evaluated_count.gt(0)]
        denominator=float(complete.evaluated_count.sum())
        tails=float((complete.d1_count+complete.d10_count).sum())
        rows.append({'month':month,'days':len(g),'complete_days':len(complete),
            'd10_pct':100*complete.d10_count.sum()/denominator if denominator else None,
            'd1_pct':100*complete.d1_count.sum()/denominator if denominator else None,
            'tail_share':float(complete.d10_count.sum()/tails) if tails else None,
            'vix_previous_mean':float(g.vix_previous.mean()),
            'vix_term_previous_mean':float(g.term_previous.mean()),
            'regime_previous_counts':g.regime_previous.value_counts().to_dict()})
    return rows


def run():
    root=Path('artifacts/research/us_common_degradation/audit-20261005-v1')
    root.mkdir(parents=True,exist_ok=False)
    batch='model-factory-20260903174624-014164'
    protocol={'original_batch':batch,'original_runs':['20260904_161042_e4696eb8','20260904_191330_695b4e33'],
        'focus':['2026-01','2026-02','2026-03'],'no_training':True,'no_sql_writes':True,
        'no_threshold_selection':True,'different_batches_not_substituted':True,
        'context_lag':'one observed session before signal','hypothesis':'common adverse context, not asserted beforehand',
        'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (root/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    engine=get_sqlalchemy_engine()
    with engine.connect() as c:
        if c.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US only')
        registry=pd.read_sql(text('SELECT batch_id,status,training_start_date,training_end_date,symbol_source,symbols '
            'FROM model_training_batch WHERE batch_id=:batch'),c,params={'batch':batch})
        runs=pd.read_sql(text('SELECT run_id,batch_id,model_role,symbol,status,train_start_date,train_end_date '
            'FROM model_training_run WHERE batch_id=:batch'),c,params={'batch':batch})
        predictions=pd.read_sql(text('SELECT p.run_id,p.model_role,MIN(p.prediction_date) AS first_date,'
            'MAX(p.prediction_date) AS last_date,COUNT(*) AS rows_count FROM model_predictions p '
            'WHERE p.run_id=:batch OR p.run_id IN (SELECT run_id FROM model_training_run WHERE batch_id=:batch) '
            'OR p.direction_long_run_id IN (SELECT run_id FROM model_training_run WHERE batch_id=:batch) '
            'OR p.direction_short_run_id IN (SELECT run_id FROM model_training_run WHERE batch_id=:batch) '
            'GROUP BY p.run_id,p.model_role'),c,params={'batch':batch})
        raw=pd.read_sql(text('SELECT * FROM oracle_atr_market_regime_daily ORDER BY trade_date'),c)
    registry.to_parquet(root/'original_batch_registry.parquet',index=False)
    runs.to_parquet(root/'original_training_runs.parquet',index=False)
    predictions.to_parquet(root/'original_prediction_coverage.parquet',index=False)
    if len(raw[['oracle_batch_id','oracle_horizon','universe_hash']].drop_duplicates())!=1:
        raise ValueError('Do not mix aggregate groups')
    raw.trade_date=pd.to_datetime(raw.trade_date)
    raw['vix_previous']=raw.vix.shift(1)
    raw['term_previous']=(raw.vix/raw.vix3m.replace(0,np.nan)).shift(1)
    raw['regime_previous']=raw.regime_mode.shift(1)
    raw.to_parquet(root/'current_intersection_snapshot.parquet',index=False)
    monthly=month_summary(raw)
    comparable=raw[raw.trade_date.lt('2026-01-01')&raw.unknown_count.eq(0)&raw.evaluated_count.gt(0)].copy()
    # Fixed zero-tuning context, not proposed as a trading rule. Always report removed favorable days.
    contexts={
        'previous_regime_not_normal':comparable.regime_previous.notna()&comparable.regime_previous.ne('normal'),
        'previous_vix_curve_inverted':comparable.term_previous.gt(1),
    }
    summaries=[]
    for name,mask in contexts.items():
        for year,g in comparable.groupby(comparable.trade_date.dt.year):
            for active in (True,False):
                part=g[mask.loc[g.index].eq(active)]
                valid=part[(part.d1_count+part.d10_count).gt(0)]
                favorable=valid.d10_count.gt(valid.d1_count)
                summaries.append({'context':name,'year':int(year),'active':active,'days':len(valid),
                    'daily_mean_tail_share':float((valid.d10_count/(valid.d1_count+valid.d10_count)).mean()) if len(valid) else None,
                    'd10_dominant_days':int(favorable.sum()),
                    'not_a_profit_measure':True})
    report={'status':'PARTIAL_AUDIT_BLOCKED_ORIGINAL_PREDICTIONS_AND_LEDGERS',
        'original_batch_registry_rows':len(registry),'original_training_run_rows':len(runs),
        'original_linked_prediction_groups':len(predictions),
        'comparison_population':'CURRENT Oracle x ATR only, NOT old Oracle/per-symbol population',
        'aggregate_batch':str(raw.oracle_batch_id.iloc[0]),'monthly':monthly,
        'historical_fixed_contexts':summaries,'original_portfolio_attribution_completed':False,
        'economic_loss_avoidance_proven':False,'production_go':False,
        'blockers':['Original backtest ledgers/configs not found in workspace/history index',
            'Original label table only reaches June 2024: cannot evaluate its OOS labels directly',
            'No replacement of missing original predictions by current batch',
            'PIT/vintage limitations described in previous lineage audit remain'],
        'snapshot_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.parquet')}}
    (root/'report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('monthly','historical_fixed_contexts')},default=str))
    print(json.dumps([m for m in monthly if m['month'] in ('2026-01','2026-02','2026-03')],default=str))


if __name__=='__main__':
    run()
