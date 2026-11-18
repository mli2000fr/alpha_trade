"""Per-batch anti-SL score lineage; only ML Predict creates/writes this table."""
from datetime import datetime,timezone

import numpy as np
import pandas as pd
from sqlalchemy import MetaData,Table,Column,String,Date,DateTime,Float,select,and_

from .anti_sl import FIELDS,load_manifest


def table():
    return Table('oracle_path_anti_sl_predictions',MetaData(),
        Column('prediction_date',Date,primary_key=True),Column('symbol',String(20),primary_key=True),
        Column('batch_id',String(255),primary_key=True),
        Column('anti_sl_probability',Float),Column('anti_sl_threshold',Float),
        Column('anti_sl_model_sha256',String(64)),Column('anti_sl_manifest_sha256',String(64),nullable=False),
        Column('anti_sl_available',Date),Column('anti_sl_status',String(40),nullable=False),
        Column('anti_sl_features_sha256',String(64)),Column('updated_at',DateTime,nullable=False))


def write(conn,frame,batch_id):
    t=table();t.create(conn,checkfirst=True);now=datetime.now(timezone.utc).replace(tzinfo=None)
    records=[]
    for r in frame.to_dict('records'):
        item={k:(None if pd.isna(r[k]) else r[k]) for k in FIELDS}
        if item['anti_sl_available'] is not None:item['anti_sl_available']=pd.Timestamp(item['anti_sl_available']).date()
        item.update(prediction_date=pd.Timestamp(r['date']).date(),symbol=r['symbol'],batch_id=batch_id,updated_at=now)
        records.append(item)
    if not records:return
    # Delete/insert under the caller's existing prediction transaction; never
    # commit partial scores or use a SQL-session-local timestamp as UTC.
    for day,g in frame.groupby('date'):
        conn.execute(t.delete().where(and_(t.c.batch_id==batch_id,t.c.prediction_date==pd.Timestamp(day).date(),t.c.symbol.in_(g.symbol.tolist()))))
    conn.execute(t.insert(),records)


def validate(root,oracle,saved):
    manifest,checksum=load_manifest(root);heads={r['year']:r for r in manifest['models']}
    if not set(FIELDS)<=set(saved):
        raise ValueError('Scores anti-SL incomplets ; relancer ML Predict pour ce batch')
    a=oracle.copy().rename(columns={'prediction_date':'date','trade_date':'date'});a.date=pd.to_datetime(a.date).dt.normalize()
    b=saved.copy().rename(columns={'prediction_date':'date'});b.date=pd.to_datetime(b.date).dt.normalize()
    if (b.duplicated(['date','symbol']).any() or len(a)!=len(b) or set(zip(a.date,a.symbol))!=set(zip(b.date,b.symbol))
        or not b.anti_sl_manifest_sha256.eq(checksum).all()):raise ValueError('Scores anti-SL manquants/dupliqués/autre manifeste ; relancer ML Predict')
    for r in b.itertuples():
        record=heads.get(r.date.year)
        if record is None:
            if r.anti_sl_status!='NO_CAUSAL_MODEL' or any(pd.notna(getattr(r,k)) for k in
                ['anti_sl_probability','anti_sl_threshold','anti_sl_model_sha256','anti_sl_available','anti_sl_features_sha256']):
                raise ValueError('Anti-SL: fausse abstention ou modèle non causal')
            continue
        if (r.anti_sl_model_sha256!=record['sha256'] or pd.isna(r.anti_sl_threshold)
            or not np.isclose(r.anti_sl_threshold,record['threshold'],rtol=0,atol=1e-12)
            or pd.Timestamp(r.anti_sl_available)!=pd.Timestamp(record['available']) or pd.Timestamp(record['available'])>=r.date):
            raise ValueError('Anti-SL: seuil/date/modèle différent du contrat')
        if r.anti_sl_status=='SCORED':
            if pd.isna(r.anti_sl_probability) or not 0<=r.anti_sl_probability<=1 or not isinstance(r.anti_sl_features_sha256,str) or len(r.anti_sl_features_sha256)!=64:
                raise ValueError('Anti-SL: score ou empreinte des variables invalide')
        elif r.anti_sl_status!='INSUFFICIENT_FEATURES' or pd.notna(r.anti_sl_probability) or pd.notna(r.anti_sl_features_sha256):
            raise ValueError('Anti-SL: statut incohérent')
    return b[['date','symbol',*FIELDS]]


def read(engine,root,oracle,batch_id,*,cutoff):
    if cutoff.tzinfo is None:raise ValueError('Cutoff anti-SL UTC requis')
    t=table();a=oracle.rename(columns={'trade_date':'date','prediction_date':'date'});days=pd.to_datetime(a.date)
    stmt=select(t).where(and_(t.c.batch_id==batch_id,t.c.prediction_date.between(days.min().date(),days.max().date()),
        t.c.symbol.in_(sorted(set(a.symbol))),t.c.updated_at<=cutoff.astimezone(timezone.utc).replace(tzinfo=None)))
    # No CREATE/repair/fallback in a read-only replay or operational consumer.
    from sqlalchemy.exc import SQLAlchemyError
    try:
        with engine.connect() as conn:saved=pd.read_sql(stmt,conn)
    except SQLAlchemyError as exc:
        raise ValueError('Scores anti-SL indisponibles ; compléter ML Predict pour ce batch avant le backtest/risque.') from exc
    return validate(root,a,saved)
