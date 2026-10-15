"""Compare three frozen Oracle TOP50s on identical offline execution tapes.

LONG-only, common TP20/SL10, no trailing. No fit, SQL or broker calls.
"""
import argparse
import logging
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from modelFactory.oracle_barrier import SCORES
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes, run_case

SOURCE = Path('artifacts/research/us_oracle_tp20_sl10_new/20261012-v6')
MODELS = {
    'PATH_H20': Path('artifacts/models/model-factory-20261012201432-834576/oracle_path'),
    'TRAIN_TP20_SL7': Path('artifacts/models/model-factory-20261012201220-a769bb/oracle_barrier'),
    'TRAIN_TP20_SL10': Path('artifacts/models/model-factory-20261012183840-6d6569/oracle_barrier'),
}


def validate_contract(protocol, profile, report, done, reference, arm):
    if report['status'] != 'completed':
        raise ValueError('Model training incomplete')
    if sorted(protocol['universe']) != sorted(reference['universe']):
        raise ValueError('Different model universe')
    if profile['feature_columns'] != reference['columns'] or profile['generator_options'] != reference['options']:
        raise ValueError('Different feature contract; cannot reuse matrix')
    if arm == 'PATH_H20':
        if protocol['mode'] != 'oracle_path_h20' or protocol['horizon'] != 20 \
                or protocol['target'] != 'oracle_path_extreme20':
            raise ValueError('Expected path H20 model, not terminal H20')
        heads = [done['metrics']]
    else:
        expected_sl = .07 if arm == 'TRAIN_TP20_SL7' else .1
        if protocol['mode'] != 'oracle_tp_before_sl' or protocol['barriers'] != {
                'take_profit_pct':.2,'stop_loss_pct':expected_sl,'max_sessions':20}:
            raise ValueError('Unexpected trained barriers')
        heads = list(done['metrics']['heads'].values())
        if len(heads) != 2 or any(h['status'] != 'TRAINED' for h in heads):
            raise ValueError('Incomplete barrier heads')
    for head in heads:
        if any(pd.Timestamp(head[k]) >= pd.Timestamp('2024-01-01')
               for k in ('train_available_max','val_available_max')):
            raise ValueError('Model selection uses external test labels')


def prepare(output, source=SOURCE):
    import lightgbm as lgb
    output, source = Path(output), Path(source)
    if output.exists():
        manifest = read(output/'manifest.json')
        verify_hashes(Path('.'),manifest['source_hashes'])
        verify_hashes(Path('.'),manifest['code_hashes'])
        for arm in MODELS:
            verify_hashes(output/arm,read(output/arm/'ready.json')['files'])
        return manifest
    if read(source/'completion-audit.json')['status'] != 'ALL_NINE_BASELINE_CASES_VERIFIED':
        raise ValueError('Common tape baseline not qualified')
    verify_hashes(source,read(source/'ready.json')['files'])
    common = read(source/'protocol.json')
    verify_hashes(Path('.'),common['model_files'])
    original_profile = read(Path(common['model'])/'feature_profile.json')
    reference = dict(universe=common['universe'],columns=common['columns'],
                     options=original_profile['generator_options'])
    features = pd.read_parquet(source/'features.parquet')
    prior = pd.read_parquet(source/'scores.parquet')
    if not features[['date','symbol']].equals(prior[['date','symbol']]):
        raise ValueError('Common candidate membership/order changed')
    output.mkdir(parents=True)
    source_paths = [source/n for n in (*read(source/'ready.json')['files'],'ready.json','completion-audit.json')]
    codes = code_hashes()
    codes[str(Path(__file__))] = digest(__file__)
    manifest = dict(status='PREPARING',source=str(source),count=50,years=[2024,2025,2026],
        side='LONG',execution_tp_pct=.2,execution_sl_pct=.1,trailing=False,
        decision_end='2026-09-03',initial_capital_usd=4000,sql_writes=False,training=False,broker_orders=False,
        unrelated_challengers_launched=False,code_hashes=codes,source_hashes={},models={},
        limitations=common['limitations']+read(source/'lifecycle.json')['reserves'])
    for arm, model in MODELS.items():
        atomic_json(output/'progress.json',dict(status='RUNNING',phase='frozen_inference',arm=arm))
        protocol, profile, report = [read(model/n) for n in ('protocol.json','feature_profile.json','report.json')]
        fold = sorted((model/'folds').iterdir())[-1]
        done = read(fold/'done.json')
        validate_contract(protocol,profile,report,done,reference,arm)
        verify_hashes(fold,done['files'])
        name = 'path_model.txt' if arm == 'PATH_H20' else 'long_model.txt'
        booster = lgb.Booster(model_file=str(fold/name))
        if booster.feature_name() != reference['columns']:
            raise ValueError('Model feature order mismatch')
        predictions = booster.predict(features[reference['columns']],num_threads=3)
        if not np.isfinite(predictions).all() or ((predictions<0)|(predictions>1)).any():
            raise ValueError('Invalid model probabilities')
        if arm == 'TRAIN_TP20_SL10' and not np.allclose(predictions,prior[SCORES['long']],rtol=1e-10,atol=1e-10):
            raise ValueError('Previously verified TP20/SL10 inference not reproduced')
        # Adapter for the shared rank-only portfolio engine. This is NOT a
        # directional LONG probability for the path-amplitude model.
        scores = features[['date','symbol']].copy()
        scores[SCORES['long']] = predictions
        native_score = 'proba_path_extreme' if arm == 'PATH_H20' else SCORES['long']
        scores[native_score] = predictions
        root = output/arm
        root.mkdir()
        scores.to_parquet(root/'scores.parquet',index=False)
        for n in ('prices.parquet','macro.parquet','lifecycle.json'):
            shutil.copy2(source/n,root/n)
        files = [model/n for n in ('protocol.json','feature_profile.json','report.json')]
        files += [fold/'done.json',*[fold/n for n in done['files']]]
        source_paths.extend(files)
        context = dict(common,batch_id=protocol['batch_id'],model=str(model),frozen_fold=fold.name,
            model_files={str(p):digest(p) for p in files},training_target=protocol.get('target',protocol.get('targets')),
            training_barriers=protocol.get('barriers'),native_score=native_score,
            score_adapter='native probability mapped to rank; LONG is a strategy, not path direction')
        atomic_json(root/'protocol.json',context)
        names = ('prices.parquet','macro.parquet','lifecycle.json','scores.parquet','protocol.json')
        atomic_json(root/'ready.json',dict(files={n:digest(root/n) for n in names}))
        manifest['models'][arm] = dict(batch_id=protocol['batch_id'],frozen_fold=fold.name,
            mode=protocol['mode'],trained_barriers=protocol.get('barriers'),features=len(reference['columns']),
            universe=len(reference['universe']),native_score=native_score,model_sha256=digest(fold/name))
    manifest.update(status='READY',source_hashes={str(p):digest(p) for p in source_paths})
    verify_hashes(Path('.'),manifest['source_hashes'])
    verify_hashes(Path('.'),manifest['code_hashes'])
    atomic_json(output/'manifest.json',manifest)
    return manifest


def run(output, source=SOURCE):
    output = Path(output)
    manifest = prepare(output,source)
    results = []
    for year in manifest['years']:
        for arm in MODELS:
            atomic_json(output/'progress.json',dict(status='RUNNING',phase='portfolio',year=year,arm=arm,
                completed_runs=len(results),total_runs=9))
            verify_hashes(Path('.'),manifest['code_hashes'])
            result = run_case(output/arm,year,50)
            result = dict(result,arm=arm,model_contract=manifest['models'][arm],
                          output=str(output/arm/'BASELINE'/f'{year}-TOP50'))
            if result['status'] == 'COMPLETED_EXPLORATORY':
                case = output/arm/'BASELINE'/f'{year}-TOP50'
                daily = pd.read_parquet(case/'daily.parquet')
                if daily.positions.iloc[-1] or abs(result['cash_reconciliation_error'])>1e-6:
                    raise ValueError('Unclosed or unreconciled portfolio')
                if arm == 'TRAIN_TP20_SL10':
                    old = Path(source)/'BASELINE'/f'{year}-TOP50'
                    reference = read(old/'case-report.json')
                    if result['annual_metrics'] != reference['annual_metrics']:
                        raise ValueError('Reference TP20/SL10 metrics changed')
                    pd.testing.assert_frame_equal(pd.read_parquet(case/'trades.parquet'),pd.read_parquet(old/'trades.parquet'))
                    result['reference_reproduced_exactly'] = True
            results.append(result)
            atomic_json(output/f'results-{year}.json',dict(year=year,portfolios=[r for r in results if r['year']==year]))
            print(year,arm,result['status'],result.get('error',''),flush=True)
    failed = [r for r in results if r['status']=='FAILED']
    verify_hashes(Path('.'),manifest['source_hashes'])
    verify_hashes(Path('.'),manifest['code_hashes'])
    report = dict(status='PARTIAL_FAILED' if failed else 'COMPLETED_EXPLORATORY',failed=len(failed),
        completed=9-len(failed),portfolios=results,manifest_sha256=digest(output/'manifest.json'),
        all_inputs_and_code_verified=True,models_unchanged=True,no_sql_writes=True,no_broker_orders=True)
    atomic_json(output/'report.json',report)
    lines = ['# Trois modèles Oracle — TOP50, exécution commune TP20/SL10','',
        'LONG uniquement, sans trailing, 4 000 USD réinitialisés par année.',
        '834576 = parcours H20, pas Oracle terminal H20. Les barrières du nom décrivent le training.',
        '2026 : décisions jusqu’au 3 septembre, puis dénouement des positions. Recherche exploratoire.','',
        '| Année | Modèle entraîné | Capital final $ | Gains $ | Pertes $ | Gagnants % | Perdants % | Rendement % | DD max % |',
        '| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in results:
        if r['status']=='FAILED':
            lines.append(f"| {r['year']} | {r['arm']} | FAILED : {r['error']} | | | | | | |")
        else:
            m = r['annual_metrics']
            values = [m[k] for k in ('final_capital_usd','winning_amount_usd','losing_amount_usd',
                'winning_pct','losing_pct','return_pct','max_drawdown_pct')]
            lines.append(f"| {r['year']} | {r['arm']} | "+' | '.join(f'{v:.2f}' if v is not None else '—' for v in values)+' |')
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    atomic_json(output/'progress.json',dict(status=report['status'],completed_runs=9-len(failed),failed_runs=len(failed),total_runs=9))
    return report


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path,default=SOURCE)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    try:
        result = run(**vars(args))
        if result['failed']:raise SystemExit(1)
    except Exception as exc:
        args.output.mkdir(parents=True,exist_ok=True)
        atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
