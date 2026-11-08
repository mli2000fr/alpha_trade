"""Offline completion audit; outcome-blind nonoverlap admission, no API/SQL server."""
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_news_embeddings_pilot as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_news_embedding_cache import DIMENSIONS,EmbeddingCache


def admission_mask(population,days,horizon):
    """Choose eligible dates BEFORE attaching future outcomes; no backfill."""
    keep=[]
    for symbol,part in population.sort_values('date').groupby('symbol'):
        after=-1
        for index,row in part.iterrows():
            j=days.get_loc(row.date)
            if j>after:
                keep.append((row.date,symbol));after=j+horizon
    return set(keep)


def run(root=pilot.ROOT):
    from modelFactory.oracle.build_labels import nyse_sessions
    protocol=pilot.verify(root)
    report=pilot.read(root/'report.json')
    for name,checksum in report['files'].items():
        if digest(root/name)!=checksum:
            raise ValueError('Changed published evaluation file: '+name)
    articles=pd.read_parquet(root/'articles.parquet')
    cache=EmbeddingCache(pilot.HOME/'cache.sqlite')
    try:
        vectors=[cache.get(k) for k in articles.key]
        if any(v is None or len(v)!=DIMENSIONS or not np.isfinite(v).all() for v in vectors):
            raise ValueError('Embedding cache incomplete or corrupt')
        tokens=cache.db.execute('SELECT COALESCE(SUM(usage_tokens),0) FROM paid_call WHERE campaign=? AND status=?',
                               (root.name,'COMPLETE')).fetchone()[0]
        if tokens!=protocol['planned_tokens']:
            raise ValueError('Paid tokens differ from exact frozen input token count')
        calls=cache.db.execute('SELECT status,charged_usd FROM paid_call WHERE campaign=?',(root.name,)).fetchall()
        if any(r[0]=='RESERVED' for r in calls):
            raise ValueError('Unknown paid request remains')
    finally:
        cache.close()
    features=pd.read_parquet(root/'features.parquet')
    features['date']=pd.to_datetime(features.date)
    features['split']=pilot.split_rows(features)
    source_test=features[features.split.eq('TEST') & np.isfinite(features[pilot.NUMERIC]).all(axis=1)].copy()
    predictions=pd.read_parquet(root/'predictions.parquet')
    days=nyse_sessions('2023-01-01','2026-12-31')
    controls=[];selected=[];admitted_counts={}
    for horizon,part in predictions.groupby('horizon'):
        mask=admission_mask(source_test,days,int(horizon))
        admitted_counts[str(horizon)]=len(mask)
        allowed=np.array([(row.date,row.symbol) in mask for row in part.itertuples()])
        sample=part.loc[allowed].copy()
        for arm,frame in sample.groupby('arm'):
            controls.append(dict(horizon=int(horizon),arm=arm,
                scope='NONOVERLAP_SELECTED_BEFORE_OUTCOMES',**pilot.metrics(frame,'probability')))
        selected.append(sample)
    strict=pd.concat(selected,ignore_index=True)
    strict.to_parquet(root/'nonoverlap-audited-predictions.parquet',index=False)
    pd.DataFrame(controls).to_csv(root/'nonoverlap-audited-summary.csv',index=False)
    # GPT opinions are a descriptive ordinal comparator, never calibrated probabilities.
    old=[]
    for folder in sorted((pilot.SOURCE/'months').iterdir()):
        if not folder.name.startswith('2026'):
            continue
        for path in sorted((folder/'assessments').glob('*.json')):
            record=pilot.read(path)
            if record.get('technical_status')=='VALID' and record.get('decision') in ['BULLISH','BEARISH','ABSTAIN']:
                old.append(dict(date=pd.Timestamp(record['decision_date']),symbol=record['symbol'],
                    old_decision=record['decision'],old_score={'BULLISH':1.,'BEARISH':0.,'ABSTAIN':.5}[record['decision']]))
    old=pd.DataFrame(old)
    from sklearn.metrics import roc_auc_score
    old_benchmark=[]
    if len(old):
        if old.duplicated(['date','symbol']).any():
            raise ValueError('Duplicate old GPT opinion')
        for horizon,part in predictions.groupby('horizon'):
            base=part[part.arm.eq('NUMERIC')].merge(old,on=['date','symbol'],validate='one_to_one')
            plus=part[part.arm.eq('NUMERIC_EMBEDDING')].merge(old,on=['date','symbol'],validate='one_to_one')
            if len(base)>1 and base.direction.nunique()==2:
                old_benchmark.append(dict(horizon=int(horizon),same_eligible_rows=len(base),
                    old_decisions=base.old_decision.value_counts().to_dict(),
                    old_ordinal_auc=float(roc_auc_score(base.direction,base.old_score)),
                    numeric_auc=float(roc_auc_score(base.direction,base.probability)),
                    numeric_embedding_auc=float(roc_auc_score(plus.direction,plus.probability)),
                    ordinal_score_not_probability=True))
    result=dict(status='AUDITED_EXPLORATORY_NOT_PIT',checked_embeddings=len(vectors),
        exact_planned_and_billed_tokens=tokens,paid_request_states={s:sum(r[0]==s for r in calls) for s in set(r[0] for r in calls)},
        original_protocol_sha256=pilot.sha(protocol),source_test_candidates_before_outcomes=len(source_test),
        admitted_nonoverlap_before_outcomes=admitted_counts,nonoverlap_results=controls,
        old_gpt_comparator=old_benchmark,
        note='Original NONOVERLAP summary chose from qualified labels; this outcome-blind admission supersedes it.',
        historical_pit_certified=False,independent_holdout=False,
        files={n:digest(root/n) for n in ['nonoverlap-audited-predictions.parquet','nonoverlap-audited-summary.csv']},
        audit_source_sha256=digest(__file__))
    atomic_json(root/'completion-audit.json',result)
    return result


if __name__=='__main__':
    import json
    print(json.dumps(run(),default=str))
