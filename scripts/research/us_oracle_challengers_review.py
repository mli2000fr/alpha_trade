"""Read-only second technical audit and diagnostics of completed challengers."""
from __future__ import annotations

import argparse
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import freeze_candidates
from scripts.research.us_oracle_challengers import (
    STAGES, FEATURES, SCORE_FEATURES, audit_stage, split_fit_validation, read, input_matrix, PROFILES,
)


def review(root):
    protocol = read(root/'challenger-protocol.json')
    verify_hashes(Path('.'), protocol['source_hashes'])
    baseline = Path(protocol['baseline'])
    if digest(baseline/'completion-audit.json') != protocol['baseline_audit_sha256']:
        raise ValueError('Baseline audit changed')
    verify_hashes(root, read(root/'ready.json')['files'])
    verify_hashes(baseline, read(baseline/'ready.json')['files'])
    verify_hashes(Path('.'), read(baseline/'protocol.json')['model_files'])
    manifest = read(root/'fit-data'/'training-source-manifest.json')
    verify_hashes(Path('.'), manifest['files'])
    for done_path in manifest['files']:
        marker=Path(done_path)
        verify_hashes(marker.parent,read(marker)['files'])
    verify_hashes(root/'fit-data', manifest['dataset_hashes'])
    entries = pd.read_parquet(root/'fit-data'/'entry-training.parquet')
    states = pd.read_parquet(root/'fit-data'/'exit-training.parquet')
    train, val = split_fit_validation(entries)
    train_states, val_states = split_fit_validation(states)
    if entries.date.max() >= pd.Timestamp('2023-01-01') or states.date.max() >= pd.Timestamp('2024-01-01'):
        raise ValueError('External observations entered training dataset')
    if not pd.to_datetime(entries.label_available).gt(entries.date).all():
        raise ValueError('Non-future trade target availability')
    base = {(r['year'],r['count']):r for r in read(root/'baseline-report.json')['portfolios']}
    heads, stages, files = [], [], {}
    for name in STAGES:
        path = root/name/'report.json'
        if not path.exists() or read(path)['status'] != 'COMPLETED_EXPLORATORY':
            continue
        report = read(path)
        audit_stage(root, name, report['portfolios'])
        models = root/name/'models'
        for weights in sorted(models.glob('*.txt')):
            m = read(weights.with_suffix('.json'))
            if digest(weights) != m['model_sha256']:
                raise ValueError('Challenger weight mismatch')
            if pd.Timestamp(m['fit_available_max']) >= pd.Timestamp('2022-01-01') \
                    or pd.Timestamp(m['validation_available_max']) >= pd.Timestamp('2023-01-01'):
                raise ValueError('Training/early stopping availability crossed cutoff')
            columns = FEATURES+SCORE_FEATURES
            if name == 'DAILY_EXIT': columns += ['age','pnl','mfe','mae','distance_stop','distance_tp']
            if m['columns'] != columns:
                raise ValueError('Unexpected feature or future target in booster')
            booster = lgb.Booster(model_file=str(weights))
            if booster.feature_name() != columns:
                raise ValueError('Booster/input feature ordering differs')
            gain = booster.feature_importance(importance_type='gain')
            importance = sorted([dict(feature=c, gain=float(g)) for c,g in zip(columns,gain)],
                key=lambda r:-r['gain'])
            heads.append(dict(experiment=name, target=weights.stem, **m, feature_importance=importance))
        stage_rows = []
        for r in report['portfolios']:
            ref = base[(r['year'],r['count'])]
            m, b = r['annual_metrics'], ref['annual_metrics']
            case = root/name/f"{r['year']}-TOP{r['count']}"
            stage_rows.append(dict(year=r['year'], count=r['count'],
                return_pct=m['return_pct'], baseline_return_pct=b['return_pct'],
                delta_return_points=m['return_pct']-b['return_pct'],
                drawdown_pct=m['max_drawdown_pct'], baseline_drawdown_pct=b['max_drawdown_pct'],
                winning_pct=m['winning_pct'], baseline_winning_pct=b['winning_pct'],
                positions=m['closed_positions'], baseline_positions=b['closed_positions'],
                exposure=r['mean_gross_exposure_over_equity'],
                baseline_exposure=ref['mean_gross_exposure_over_equity']))
            for p in case.glob('*.json'): files[str(p)] = digest(p)
        diagnostics = {}
        if name == 'ENTRY_FILTER':
            f = pd.read_parquet(models/'filter-decisions.parquet')
            model=lgb.Booster(model_file=str(models/'label_win.txt'))
            probabilities=model.predict(input_matrix(f,FEATURES+SCORE_FEATURES),num_threads=3)
            if not np.isclose(probabilities,f.entry_filter_probability,rtol=1e-12,atol=1e-12).all() \
                    or not f.entry_allowed.eq(probabilities>=.5).all():
                raise ValueError('Stored filter differs from frozen booster/threshold')
            flags = f[['date','symbol','entry_filter_probability','entry_allowed']]
            samples = []
            for n in (10,20,50):
                selected = freeze_candidates(f,n,'NEW_BARRIER_LONG').merge(flags,on=['date','symbol'],validate='one_to_one')
                for y,g in selected.groupby(selected.date.dt.year):
                    samples.append(dict(year=int(y),count=n,candidates=len(g),kept=int(g.entry_allowed.sum()),
                        kept_pct=float(g.entry_allowed.mean()*100),
                        minimum_probability=float(g.entry_filter_probability.min()),
                        median_probability=float(g.entry_filter_probability.median()),
                        maximum_probability=float(g.entry_filter_probability.max())))
            diagnostics['candidate_retention'] = samples
            prior=Path('artifacts/research/us_oracle_challengers/20261013-v1')
            if (prior/name/'report.json').exists():
                original=read(prior/name/'report.json')
                original_metrics={(r['year'],r['count']):r['annual_metrics'] for r in original['portfolios']}
                if original_metrics != {(r['year'],r['count']):r['annual_metrics'] for r in report['portfolios']}:
                    raise ValueError('Tail-only repair changed the entry-filter result')
                original_head=read(prior/name/'models'/'label_win.json')['model_sha256']
                if original_head != read(models/'label_win.json')['model_sha256']:
                    raise ValueError('Tail-only repair changed entry-filter weights')
                diagnostics['v1_exactly_reproduced_after_tail_repair']=True
        elif name == 'DAILY_EXIT':
            diagnostics['daily_action_counts'] = {}
            for r in report['portfolios']:
                diary = pd.read_parquet(root/name/f"{r['year']}-TOP{r['count']}"/'daily-model-decisions.parquet')
                diagnostics['daily_action_counts'][f"{r['year']}-TOP{r['count']}"] = diary.action.value_counts().to_dict() if len(diary) else {}
        else:
            f = pd.read_parquet(models/'profile-decisions.parquet')
            external=pd.read_parquet(root/'features.parquet',columns=['date','symbol',*FEATURES]).merge(
                pd.read_parquet(root/'scores.parquet'),on=['date','symbol'],validate='one_to_one')
            from modelFactory.oracle_barrier import SCORES
            external['score_difference']=external[SCORES['long']]-external[SCORES['short']]
            if not f[['date','symbol']].equals(external[['date','symbol']]):
                raise ValueError('Profile decision order/identity differs')
            predictions=[]
            for k in range(3):
                model=lgb.Booster(model_file=str(models/f'profile_target_{k}.txt'))
                prediction=model.predict(input_matrix(external,FEATURES+SCORE_FEATURES),num_threads=3)
                if not np.isclose(prediction,f[f'predicted_profile_{k}'],rtol=1e-12,atol=1e-12).all():
                    raise ValueError('Stored profile score differs from frozen booster')
                predictions.append(prediction)
            choice=np.stack(predictions,axis=1).argmax(axis=1)
            if not np.allclose(f.tp,[PROFILES[k][0] for k in choice]) \
                    or not np.allclose(f.sl,[PROFILES[k][1] for k in choice]):
                raise ValueError('Profile selected from another objective or realised outcome')
            selected_profiles=f.set_index(['date','symbol'])[['tp','sl']]
            for r in report['portfolios']:
                trades=pd.read_parquet(root/name/f"{r['year']}-TOP{r['count']}"/'trades.parquet')
                ids=trades.entry_symbol.fillna(trades.symbol) if 'entry_symbol' in trades else trades.symbol
                keys=pd.MultiIndex.from_arrays([pd.to_datetime(trades.signal_date),ids])
                profiles=selected_profiles.reindex(keys)
                if profiles.isna().any().any() or not np.isclose(trades.replay_initial_stop_price,
                    trades.entry_price*(1-profiles.sl.to_numpy()),rtol=1e-8,atol=1e-7).all() \
                    or not np.isclose(trades.replay_take_profit_price,
                    trades.entry_price*(1+profiles.tp.to_numpy()),rtol=1e-8,atol=1e-7).all():
                    raise ValueError('Booked protection differs from decision at J')
            choices = []
            for n in (10,20,50):
                selected = freeze_candidates(pd.read_parquet(root/'scores.parquet'),n,'NEW_BARRIER_LONG').merge(
                    f[['date','symbol','tp','sl']],on=['date','symbol'],validate='one_to_one')
                for (y,tp,sl),g in selected.groupby([selected.date.dt.year,'tp','sl']):
                    choices.append(dict(year=int(y),count=n,tp=float(tp),sl=float(sl),candidates=len(g)))
            diagnostics['selected_profile_counts'] = choices
            # The common replay's legacy flag describes its native default;
            # it does not account for an injected research session factory.
            # Preserve raw reports and state the effective contract explicitly.
            diagnostics['effective_sizing_unchanged']=False
            diagnostics['legacy_sizing_unchanged_flag_not_authoritative']=True
            control=read(root/'FIXED_SL10_SIZING_CONTROL'/'report.json')
            audit_stage(root,'FIXED_SL10_SIZING_CONTROL',control['portfolios'])
            control_metrics={(r['year'],r['count']):r['annual_metrics'] for r in control['portfolios']}
            identical_controls=[]
            for r in control['portfolios']:
                case=f"{r['year']}-TOP{r['count']}"
                actual=pd.read_parquet(root/'FIXED_SL10_SIZING_CONTROL'/case/'trades.parquet')
                reference=pd.read_parquet(baseline/'BASELINE'/case/'trades.parquet')
                identical_controls.append(dict(year=r['year'],count=r['count'],
                    trades_identical_to_baseline=actual.equals(reference),
                    metrics_identical_to_baseline=r['annual_metrics']==base[(r['year'],r['count'])]['annual_metrics']))
            for row in stage_rows:
                ref=control_metrics[(row['year'],row['count'])]
                row['same_sizing_control_return_pct']=ref['return_pct']
                row['delta_return_vs_same_sizing']=row['return_pct']-ref['return_pct']
            diagnostics['fixed_profile_sizing_control_audited']=True
            diagnostics['fixed_profile_sizing_control_parity']=identical_controls
            diagnostics['profile_inference_recomputed_and_booked_protections_verified']=True
        stages.append(dict(experiment=name, results=stage_rows, diagnostics=diagnostics))
        for p in models.iterdir():
            if p.is_file(): files[str(p)] = digest(p)
        files[str(path)] = digest(path)
    if not stages: raise ValueError('No completed challenger to review')
    completed = len(stages) == 3
    output = dict(status='THREE_CHALLENGERS_VERIFIED' if completed else 'COMPLETED_STAGES_VERIFIED',
        stages=stages, training=dict(entry_fit=len(train),entry_validation=len(val),
            state_fit=len(train_states),state_validation=len(val_states),
            fit_available_max=str(train.label_available.max()),validation_available_max=str(val.label_available.max())),
        heads=heads, source_hashes=files, baseline_immutable=True, original_oracle_unchanged=True,
        progressive_exposure_guard=False, holdout_is_virgin=False, no_automatic_promotion=True,
        sql_writes=False, broker_orders=False)
    atomic_json(root/'second-technical-review.json',output)
    print(output['status'])
    for stage in stages:
        for row in stage['results']:
            if row['count']==10:
                print(stage['experiment'],row)
    return output


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    review(**vars(parser.parse_args()))
