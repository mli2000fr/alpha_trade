"""Read-only evidence audit; never reconstruct missing historical vintages."""
import json
import hashlib
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


def run():
    root=Path('artifacts/research/us_ratio_regime_validation/lineage-20261004-v1')
    root.mkdir(parents=True,exist_ok=False)
    batch='model-factory-20261003082853-e98332'
    champions=Path('artifacts/models/oracle/champions')/batch
    meta=json.loads((champions/'oracle_champions.json').read_text())
    starts={m['t_start'] for m in meta}
    engine=get_sqlalchemy_engine()
    snapshots={}
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US only')
        snapshots['prediction_dates']=pd.read_sql(text('SELECT prediction_date,fold_start,COUNT(*) AS rows_count '
            'FROM oracle_extreme_predictions WHERE batch_id=:batch GROUP BY prediction_date,fold_start'),conn,params={'batch':batch})
        snapshots['macro_dates']=pd.read_sql(text('SELECT trade_date,mode,sentiment_source,created_at,updated_at '
            'FROM stock_macro_indicators_daily WHERE trade_date BETWEEN :start AND :end'),conn,
            params={'start':'2020-01-01','end':'2026-09-30'})
        snapshots['sentiment_dates']=pd.read_sql(text('SELECT trade_date,COUNT(*) AS rows_count,MIN(created_at) AS earliest_created_at,'
            'MAX(updated_at) AS latest_updated_at,MAX(latest_event_timestamp_ny) AS latest_event '
            'FROM ticker_daily_sentiment_features WHERE trade_date BETWEEN :start AND :end GROUP BY trade_date'),conn,
            params={'start':'2020-01-01','end':'2026-09-30'})
        snapshots['schemas']=pd.read_sql(text('SELECT TABLE_NAME,COLUMN_NAME,DATA_TYPE FROM information_schema.COLUMNS '
            "WHERE TABLE_SCHEMA='alpha_trade' AND TABLE_NAME IN ('oracle_extreme_predictions',"
            "'stock_macro_indicators_daily','ticker_daily_sentiment_features','news_raw','news_ticker_sentiment')"),conn)
    for name,frame in snapshots.items():
        frame.to_parquet(root/f'{name}.parquet',index=False)
    predictions=snapshots['prediction_dates'].copy()
    predictions['day']=pd.to_datetime(predictions.prediction_date)
    predictions['fold']=pd.to_datetime(predictions.fold_start)
    predictions['known_model']=predictions.fold_start.astype(str).isin(starts)
    predictions['fold_not_future']=predictions.fold.le(predictions.day)
    predictions['expected_fold']=predictions.day.map(lambda d:max((s for s in starts if s<=str(d.date())),default=None))
    predictions['latest_model_matches']=predictions.fold_start.astype(str).eq(predictions.expected_fold)
    predictions.to_parquet(root/'prediction_lineage_checks.parquet',index=False)
    macro=snapshots['macro_dates']
    sentiment=snapshots['sentiment_dates']
    evidence=[]
    for label,frame,column in [('macro',macro,'created_at'),('sentiment',sentiment,'earliest_created_at')]:
        late=pd.to_datetime(frame[column]).dt.normalize().gt(pd.to_datetime(frame.trade_date)+pd.Timedelta(days=1))
        evidence.append({'source':label,'days':len(frame),'first_materialization_later_than_Jplus1_days':int(late.sum()),
            'creation_min':str(frame[column].min()),'creation_max':str(frame[column].max()),
            'interpretation':'Materialization time is not publication proof; late generation does not itself prove future news use'})
    counts=lambda mask:int(predictions.loc[mask,'rows_count'].sum())
    sources=[Path('modelFactory/oracle/walk_forward.py'),Path('modelFactory/oracle/predict_history.py'),
        Path('modelFactory/oracle/predictions_store.py'),Path('service/market/sentiment_provider.py'),
        Path('service/market/macro_providers.py'),champions/'oracle_champions.json',champions/'feature_profile.json']
    report={'status':'AUDIT_COMPLETE_STRICT_PIT_NOT_CERTIFIED','batch':batch,
        'champion_count':len(meta),'latest_champion_start':max(starts),
        'prediction_rows':int(predictions.rows_count.sum()),'prediction_days':int(predictions.day.nunique()),
        'unknown_champion_rows':counts(~predictions.known_model),
        'future_champion_rows':counts(~predictions.fold_not_future),
        'not_latest_champion_rows':counts(~predictions.latest_model_matches),
        'prediction_date_groups':len(predictions),
        'materialization':evidence,
        'macro_sentiment_sources':macro.sentiment_source.value_counts(dropna=False).to_dict(),
        'facts':['Training code purges train labels before validation and validation labels before test',
            'Champion manifest stores t_start/model/features but not train/validation max label maturity or training dataset hash',
            'Prediction upsert can replace OOF rows, with no prediction run/model hash or historical versions',
            'Historical predictor selects latest t_start <= date, but fallback to first model exists if none qualifies',
            'Macro daily schema lacks available_at and vintage; aggregate study copies values without vintage lineage',
            'Macro reader synthesizes available_at at 21:00 UTC from trade_date and ingested_at as read time; neither proves historical publication',
            'Market sentiment SQL filters trade_date only, not publication/observed/calculation time',
            'Sentiment range is [-1,1], weighted by news count, ticker source then sector fallback'],
        'correction_decision':'NO_EVIDENCED_DATA_CORRECTION_AVAILABLE_NO_IDENTICAL_RERUN',
        'reason':'Date routing can be checked; absent publication/vintage/model provenance cannot be invented. No proven future champion use unless counted above.',
        'canonical_writes':False,'serving_changes':False,'production_go':False,
        'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    report['model_hashes']={m['model_file']:hashlib.sha256((champions/m['model_file']).read_bytes()).hexdigest() for m in meta}
    (root/'report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps(report,default=str))


if __name__=='__main__':
    run()
