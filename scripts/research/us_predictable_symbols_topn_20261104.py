"""Offline TOP-N sensitivity of the frozen three-source reliability audit.

Reuse the 2023-25 ranking and fixed 2026 nonoverlap validation. Never refit,
rerank using 2026, fabricate source history, or modify the TOP1500 campaign.
"""
from datetime import datetime,timezone
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_predictable_symbols_review_20261104 import summarize
from common.symbol_artifact_paths import symbol_directory

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'artifacts/research/us_predictable_symbols/20261103-v1'
SOURCE=ROOT/'config/univers_batch/action_ordinaire.txt'
TARGETS=('winner_h10','parcours_h20')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n',encoding='utf-8')


def independent_outcomes(symbols,target):
    horizon=10 if target=='winner_h10' else 20
    frames=[]
    for symbol in symbols:
        file=symbol_directory(BASE/'symbols',symbol)/(target+'-predictions.parquet')
        if not file.exists():continue
        a=pd.read_parquet(file)
        a=a[a.year.eq(2026)&a.session_index.mod(horizon).eq(0)].copy()
        assert a.date.is_unique and a.probability.between(0,1).all()
        a['symbol']=symbol;frames.append(a)
    if not frames:return {},pd.DataFrame()
    allrows=pd.concat(frames,ignore_index=True)
    selected=allrows[allrows.probability.ge(allrows.long_threshold)].copy()
    positive=int(selected.label.sum());n=len(selected)
    baseline=float(allrows.label.mean()) if len(allrows) else None
    precision=float(selected.label.mean()) if n else None
    result=dict(symbols_with_2026_predictions=int(allrows.symbol.nunique()),all_independent_stock_windows=len(allrows),
        long_selected_windows=n,positive_long_outcomes=positive,negative_long_outcomes=n-positive,
        long_outcome_positive_ratio=precision,all_windows_base_rate=baseline,
        precision_lift=None if precision is None else precision-baseline,
        outcome='Positive net daily proxy with SL5/H10' if horizon==10 else 'Upward peak dominates absolute downward peak overH20; not trade PnL',
        actual_winner_trades=False,cross_stock_observations_not_statistically_independent=True)
    return result,allrows


def run(top_n,output):
    if top_n<1 or top_n>1500:raise ValueError('Choose TOP1..1500 from the existing audit')
    if output.exists():raise FileExistsError('Fresh result directory required')
    base_report=json.loads((BASE/'report.json').read_text())
    completion=json.loads((BASE/'completion-audit.json').read_text())
    amendment=json.loads((BASE/'scope-amendment-pfbc.json').read_text())
    assert completion['status']=='PASS' and base_report['errors']==0
    assert sha(SOURCE)==amendment['source_sha256']
    universe=set(SOURCE.read_text(encoding='utf-8-sig').strip().split(','))
    gates=pd.read_parquet(BASE/'source-reliability-gates.parquet')
    # A newly populated reliability list must be reviewed rather than silently ignored.
    for target in TARGETS:
        for family in ('options','consensus'):
            if (BASE/f'{target}-{family}-top1500.txt').read_text().strip():
                raise ValueError('Source lists changed: qualify their ranking/validation before reuse')
    inputs=[SOURCE,BASE/'protocol.json',BASE/'report.json',BASE/'completion-audit.json',
        BASE/'scope-amendment-pfbc.json',BASE/'check-2026-per-symbol.csv',BASE/'check-2026-summary.json',
        BASE/'source-reliability-gates.parquet',Path(__file__)]
    inputs += [BASE/f'{target}-per-symbol-ranking.csv' for target in TARGETS]
    inputs += [BASE/f'{target}-{family}-top1500.txt' for target in TARGETS for family in ('model','options','consensus')]
    output.mkdir(parents=True)
    frozen={str(p):sha(p) for p in inputs}
    save(output/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),top_n=top_n,
        base_campaign=str(BASE),ranking_years=[2023,2024,2025],check_year=2026,price_asof='2026-11-02',
        selection='First N rows of the previously frozen 2023-25 per-symbol reliability ranking',
        source_minimum_independent_windows=20,no_refitting=True,no_2026_reranking=True,
        statistical_status='Sensitivity requested after the TOP1500 result; not a virgin holdout',
        input_hashes=frozen,sql_writes=False,provider_calls=0,llm_calls=0,orders=0))
    validation=pd.read_csv(BASE/'check-2026-per-symbol.csv',keep_default_na=False)
    for col in ('observations','auc','long_observations','base_rate','long_precision','long_lift'):
        validation[col]=pd.to_numeric(validation[col],errors='coerce')
    report=dict(status='COMPLETED_WITH_UNQUALIFIED_SOURCES',top_n=top_n,source_count=len(universe),
        reused_models=base_report['models_fitted'],new_models=0,cases={},sql_writes=False,provider_calls=0,orders=0)
    for target in TARGETS:
        ranking=pd.read_csv(BASE/f'{target}-per-symbol-ranking.csv',keep_default_na=False)
        assert ranking['rank'].tolist()==list(range(1,len(ranking)+1)) and ranking.symbol.is_unique
        first=ranking.head(top_n).copy();chosen=first.symbol.tolist();assert len(chosen)==top_n and set(chosen)<=universe
        assert not set(chosen)&{'CHRD','WFRD'}
        existing=[x for x in (BASE/f'{target}-model-top1500.txt').read_text().strip().split(',') if x]
        assert chosen==existing[:top_n]
        (output/f'{target}-model-top{top_n}.txt').write_text(','.join(chosen)+'\n',encoding='utf-8')
        for family in ('options','consensus'):(output/f'{target}-{family}-top{top_n}.txt').write_text('',encoding='utf-8')
        v=validation[validation.target.eq(target)&validation.symbol.isin(set(ranking.symbol))]
        summaries={f'top{top_n}':summarize(v[v.symbol.isin(chosen)]),
            'other_history_qualified':summarize(v[~v.symbol.isin(chosen)]),
            'top1500_reference':summarize(v[v.symbol.isin(existing)]),
            f'ranks_{top_n+1}_to_1500':summarize(v[v.symbol.isin(set(existing)-set(chosen))])}
        original=json.loads((BASE/'check-2026-summary.json').read_text())[target]['top1500']
        assert all(summaries['top1500_reference'][k]==value for k,value in original.items())
        first=first.rename(columns={'check_2026_auc':'check_2026_auc_all_overlapping'})
        first=first.merge(v[['symbol','observations','auc','long_observations','base_rate','long_precision','long_lift']],
            on='symbol',how='left',validate='one_to_one',sort=False)
        assert first.symbol.tolist()==chosen
        first.to_csv(output/f'{target}-top{top_n}-audit.csv',index=False)
        subset=gates[gates.target.eq(target)&gates.symbol.isin(chosen)]
        assert len(subset)==2*top_n and not subset.status.eq('NEEDS_FULL_SOURCE_QUALIFICATION').any()
        subset.to_csv(output/f'{target}-top{top_n}-source-gates.csv',index=False)
        coverage={family:dict(status_counts={str(k):int(n) for k,n in a.groupby('status').size().items()},
            maximum_optimistic_independent_windows=int(a.optimistic_independent_upper_bound.max()))
            for family,a in subset.groupby('source')}
        outcome,observations=independent_outcomes(chosen,target)
        observations.to_parquet(output/f'{target}-2026-nonoverlap-observations.parquet',index=False)
        # The known source gate failure prevents both non-price rankings, for
        # TOP100 as for TOP1500. It does not assert an empty economic overlap.
        intersection=set(chosen)&set()&set()
        final=ROOT/'config/univers_batch'/f'symbol_trade_{target}.txt'
        previous=output/'previous-requested-outputs';previous.mkdir(exist_ok=True)
        for file in (final,final.with_suffix('.audit.json')):
            if file.exists():(previous/file.name).write_bytes(file.read_bytes())
        assert not final.read_text().strip(),'Do not replace a separately populated trading universe'
        final.write_text(','.join(sorted(intersection)),encoding='utf-8')
        save(final.with_suffix('.audit.json'),dict(status='UNQUALIFIED_EMPTY_DO_NOT_USE_FOR_TRADING',
            target=target,top_n=top_n,symbols=0,reason='Options/consensus histories below the same20 independent-window minimum',report=str(output/'report.json')))
        report['cases'][target]=dict(history_qualified=len(ranking),model_top_n=len(chosen),
            exploratory_consistent_count=int(first.reliability_confirmed.sum()),options_top_n=0,consensus_top_n=0,
            intersection_count=0,output=str(final),validation_2026=summaries,
            aggregate_nonoverlap_long_outcomes=outcome,source_coverage_within_price_top=coverage)
    assert all(sha(p)==expected for p,expected in frozen.items())
    save(output/'report.json',report)
    save(output/'verification.json',dict(status='PASS',top_n=top_n,base_inputs_unchanged=True,
        current_source_unchanged=True,exact_prefix_of_top1500=True,holdout_not_used_to_rerank=True,
        top1500_reference_metrics_reproduced=True,top100_symbols_distinct=True,final_intersections_empty=True,
        no_new_models=True,sql_writes=False,provider_calls=0,orders=0))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--top-n',type=int,default=100)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/research/us_predictable_symbols/20261104-top100-v1')
    args=parser.parse_args();run(args.top_n,args.output)
