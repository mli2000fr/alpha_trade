"""Audit archived Oracle lineage only; no database, scoring or training."""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_top10_2024_context_audit import group_metrics

BATCH = 'model-factory-20261003082853-e98332'


def extract_window(lines):
    pattern = re.compile(r"build_folds_adaptive windows=(\d+).*first=\('([\d-]+)', '([\d-]+)'\) last=\('([\d-]+)', '([\d-]+)'\)")
    matches = [m for line in lines if (m := pattern.search(line))]
    if len(matches) != 1:
        raise ValueError('Need exactly one attributable adaptive-window record')
    n, first, first_end, last, last_end = matches[0].groups()
    return dict(folds=int(n), first_start=first,first_end=first_end,
                last_start=last,last_end=last_end)


def classify_scope(frame, starts, first, last):
    result=frame.copy()
    day=pd.to_datetime(result.date)
    fold=pd.to_datetime(result.fold_start,errors='coerce')
    known=result.fold_start.astype(str).isin(starts) & fold.le(day)
    result['scope']='UNQUALIFIED_CHAMPION_OR_DATE'
    within=known & day.between(pd.Timestamp(first),pd.Timestamp(last))
    result.loc[within,'scope']='LOGGED_TEST_ENVELOPE_NOT_FULL_PIT'
    result.loc[known & day.gt(pd.Timestamp(last)),'scope']='POST_TEST_HISTORICAL_SERVING'
    return result


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    base=Path('artifacts/models/oracle/champions')/BATCH
    manifest_path=base/'oracle_champions.json'
    archive=Path('artifacts/rapport_ml')/(BATCH+'.log')
    report_path=Path('artifacts/rapport_ml')/(BATCH+'.md')
    log_path=Path('log/model_factory.log')
    manifest=json.loads(manifest_path.read_text())
    log=log_path.read_text(encoding='utf-8',errors='replace').splitlines()
    # Bound by this batch's actual start/DONE markers, not the whole global log.
    begin=[i for i,line in enumerate(log) if 'oracle_extreme start batch_id='+BATCH in line]
    finish=[i for i,line in enumerate(log) if 'oracle_extreme DONE' in line and 'stored_batch='+BATCH in line]
    if len(begin)!=1 or len(finish)!=1 or finish[0]<=begin[0]:
        raise ValueError('Cannot attribute the global-log interval uniquely')
    block=log[begin[0]:finish[0]+1]
    window=extract_window(block)
    selected=[line for line in block if any(key in line for key in [
        'oracle_extreme start','build_labels done','build_folds_adaptive',
        'persisted OOS','persisted oracle champions','oracle_extreme DONE',
        'oracle_extreme_train_features: daily_return ',
        'oracle_extreme_train_features: overnight_gap ',
        'oracle_extreme_train_features: rolling_volatility_20 '])]
    atomic_json(output/'evidence-excerpts.json',dict(source=str(log_path),
        start_line=begin[0]+1,end_line=finish[0]+1,lines=selected))
    models=[]
    for item in manifest:
        path=base/item['model_file']
        names=next(line.split('=',1)[1].split() for line in path.read_text().splitlines()
                   if line.startswith('feature_names='))
        feature_match=names==item['feature_columns']
        models.append(dict(start=item['t_start'],file=str(path),sha256=digest(path),
            feature_count=len(names),manifest_feature_order_matches=feature_match,
            training_weights_log_present=any('oracle_extreme fold='+item['t_start']+':' in line for line in block)))
    if window['folds']!=len(models) or not all(m['manifest_feature_order_matches'] for m in models):
        raise ValueError('Model manifest/log mismatch')
    starts=[m['t_start'] for m in manifest]
    root=Path('artifacts/research/us_extreme50_capture/audit-20261006-v1')
    paths=[root/str(year)/'panel.parquet' for year in [2023,2024]]
    frame=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
    frame=frame.loc[frame.ORACLE_TOP10].copy()
    frame=classify_scope(frame,starts,window['first_start'],window['last_end'])
    sorted_starts=sorted(starts)
    expected=frame.date.map(lambda d: next((s for s in reversed(sorted_starts)
                                            if s<=str(d)[:10]),None))
    actual=pd.to_datetime(frame.fold_start,errors='coerce').dt.strftime('%Y-%m-%d')
    mismatch=int(actual.ne(expected).sum())
    frame['year']=pd.to_datetime(frame.date).dt.year
    frame.to_parquet(output/'classified-top10.parquet',index=False)
    groups=group_metrics(frame,['year','scope'])
    atomic_json(output/'protocol.json',dict(batch_id=BATCH,
        sources={str(p):digest(p) for p in paths+[manifest_path,archive,report_path]},
        global_log_hash_at_audit=digest(log_path),sql_reads=False,sql_writes=False,
        training=False,pnl=False,parameters_changed=False,
        qualification='Logged envelope, NOT exact row-level OOF or full PIT certification',
        no_certified_subset='Strict full-PIT subset not established; metrics are provisional'))
    result=dict(status='COMPLETED_PARTIAL_LINEAGE',window=window,models=models,
        candidate_metrics=groups,latest_eligible_champion_mismatches=mismatch,
        strict_full_pit_subset_established=False,
        missing=['Effective train/validation label-availability maxima per fold',
                 'Exact original dataset and row membership per split',
                 'Frozen training source revision and execution environment',
                 'Historical universe and feature publication/vintage lineage',
                 'Immutable original OOF probabilities versus later upserts'],
        findings=['Original logged test ends 2024-07-09',
                  'Historical predict and training OOF upsert the same prediction key',
                  'created_at is not updated by prediction upsert; not proof of latest scoring',
                  'Batch-only archived logs omit fold records without batch-id',
                  'Training logs show extreme feature values; separate quality investigation needed'])
    atomic_json(output/'report.json',result)
    print(json.dumps(dict(window=window,candidate_metrics=groups),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
