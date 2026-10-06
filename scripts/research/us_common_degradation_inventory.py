"""Read-only bounded inventory for the original directional experiment."""
import json
from pathlib import Path
from sqlalchemy import text
from database.connection import get_sqlalchemy_engine

if __name__=='__main__':
    engine=get_sqlalchemy_engine()
    batch='model-factory-20260903174624-014164'
    root=Path('artifacts/research/us_common_degradation/inventory-20261005-v1')
    root.mkdir(parents=True,exist_ok=False)
    with engine.connect() as c:
        if c.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US only')
        tables=c.execute(text('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')).scalars().all()
        candidates=[t for t in tables if any(k in t for k in ('backtest','model_prediction','model_training'))]
        schema=c.execute(text('SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()')).all()
        print('TABLES',candidates,flush=True)
        counts={}
        for table in ['oracle_extreme_predictions','global_oracle_labels']:
            counts[table]=[dict(r) for r in c.execute(text(f'SELECT MIN(prediction_date) AS first_date,MAX(prediction_date) AS last_date,COUNT(*) AS rows_count FROM {table} WHERE batch_id=:batch'),{'batch':batch}).mappings()]
        counts['model_predictions']=[dict(r) for r in c.execute(text('SELECT run_id,model_role,MIN(prediction_date) AS first_date,MAX(prediction_date) AS last_date,COUNT(*) AS rows_count FROM model_predictions WHERE run_id=:batch GROUP BY run_id,model_role'),{'batch':batch}).mappings()]
    payload={'batch':batch,'tables':candidates,'schema':[list(r) for r in schema if r[0] in candidates],'counts':counts}
    (root/'report.json').write_text(json.dumps(payload,indent=2,default=str),encoding='utf-8')
    print(json.dumps(payload,default=str))
