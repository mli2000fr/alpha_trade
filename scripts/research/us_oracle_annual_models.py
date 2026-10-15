"""Annual causal Oracle TP20/SL10 replay; no training, SQL or broker calls."""
import argparse
import logging
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from modelFactory.oracle_barrier import SCORES
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes, run_case, annual_metrics

MODELS = {
    2024: 'model-factory-20261013124901-f62825',
    2025: 'model-factory-20261013124908-f1b59f',
    2026: 'model-factory-20261013125014-9be3d2',
}
SOURCE = Path('artifacts/research/us_oracle_tp20_sl10_new/20261012-v6')
REFERENCE = Path('artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1/input-protocol.json')
COUNTS = (10, 20, 50)


def causal_fold(day, folds):
    """Newest trained fold whose fit AND selection labels predate decision J."""
    day = pd.Timestamp(day)
    eligible = []
    for name, done in folds.items():
        metrics = done['metrics']
        start = pd.Timestamp(metrics['fold_start'])
        heads = metrics['heads']
        if set(heads) != {'long', 'short'}:
            continue
        if start <= day and all(h.get('status') == 'TRAINED' and all(
            pd.notna(pd.Timestamp(h[k])) and pd.Timestamp(h[k]) < day
            for k in ('train_available_max', 'val_available_max')) for h in heads.values()):
            eligible.append((start, name))
    if not eligible:
        raise ValueError(f'No causal fold for {day.date()}')
    return max(eligible)[1]


def validate_contract(protocol, profile, report, reference):
    if report['status'] != 'completed' or protocol['mode'] != 'oracle_tp_before_sl':
        raise ValueError('Completed barrier training required')
    if protocol['barriers'] != dict(take_profit_pct=.2, stop_loss_pct=.1, max_sessions=20):
        raise ValueError('Expected trained TP20/SL10/20')
    if sorted(protocol['universe']) != sorted(reference['universe']):
        raise ValueError('Different model universe')
    if profile['feature_columns'] != reference['columns'] or profile['generator_options'] != reference['options']:
        raise ValueError('Different feature contract')


def prepare(output, source=SOURCE):
    import lightgbm as lgb
    output, source = Path(output), Path(source)
    if (output/'manifest.json').exists():
        manifest = read(output/'manifest.json')
        verify_hashes(Path('.'), manifest['source_hashes'])
        verify_hashes(Path('.'), manifest['code_hashes'])
        for year in MODELS:
            root = output/str(year)
            verify_hashes(root, read(root/'ready.json')['files'])
        return manifest
    verify_hashes(source, read(source/'ready.json')['files'])
    if read(source/'completion-audit.json')['status'] != 'ALL_NINE_BASELINE_CASES_VERIFIED':
        raise ValueError('Unqualified common tape')
    reference, common = read(REFERENCE), read(source/'protocol.json')
    features = pd.read_parquet(source/'features.parquet')
    if features.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate candidate keys')
    output.mkdir(parents=True, exist_ok=True)
    codes = code_hashes()
    codes[str(Path(__file__))] = digest(__file__)
    paths = [source/n for n in (*read(source/'ready.json')['files'], 'ready.json', 'completion-audit.json')]
    paths.append(REFERENCE)
    manifest = dict(status='PREPARING', models={}, years=list(MODELS), counts=list(COUNTS),
        side='LONG', tp_pct=.2, sl_pct=.1, trailing=False, initial_capital_usd=4000,
        decision_end_2026='2026-09-03', training=False, sql_writes=False, broker_calls=False,
        source=str(source), code_hashes=codes,
        provenance='Reuse hash-verified archived data, NOT deleted prior model weights',
        limitations=common['limitations']+read(source/'lifecycle.json')['reserves']+[
            'Research only: serving_ready=false',
            'Latest causal fold may be extrapolated beyond its original OOF test window',
            'LONG-head ranking, not argmax LONG/SHORT allocation; annual capital resets'])
    for year, batch in MODELS.items():
        atomic_json(output/'progress.json', dict(status='RUNNING', phase='inference', year=year))
        model = Path('artifacts/models')/batch/'oracle_barrier'
        protocol, profile, report = [read(model/n) for n in ('protocol.json', 'feature_profile.json', 'report.json')]
        validate_contract(protocol, profile, report, reference)
        folds = {p.name: read(p/'done.json') for p in sorted((model/'folds').iterdir()) if (p/'done.json').exists()}
        subset = features.loc[features.date.dt.year.eq(year)].copy()
        if subset.empty:
            raise ValueError(f'No archived features for {year}')
        schedule = {str(day.date()): causal_fold(day, folds) for day in sorted(subset.date.unique())}
        scores = subset[['date', 'symbol']].copy()
        scores['fold_start'] = scores.date.dt.strftime('%Y-%m-%d').map(schedule)
        lineage = {}
        files = [model/n for n in ('protocol.json', 'feature_profile.json', 'report.json')]
        for fold in sorted(set(schedule.values())):
            folder, done = model/'folds'/fold, folds[fold]
            verify_hashes(folder, done['files'])
            files.extend([folder/'done.json', *[folder/n for n in done['files']]])
            mask = scores.fold_start.eq(fold)
            for side in ('long', 'short'):
                booster = lgb.Booster(model_file=str(folder/f'{side}_model.txt'))
                if booster.feature_name() != reference['columns']:
                    raise ValueError('Feature order mismatch')
                values = booster.predict(subset.loc[mask, reference['columns']], num_threads=3)
                if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
                    raise ValueError('Invalid probabilities')
                scores.loc[mask, SCORES[side]] = values
            lineage[fold] = dict(metrics=done['metrics'], first_decision=str(scores.loc[mask, 'date'].min().date()),
                last_decision=str(scores.loc[mask, 'date'].max().date()), rows=int(mask.sum()),
                extrapolated_rows=int((mask & scores.date.gt(pd.Timestamp(done['metrics']['test_end']))).sum()))
        root = output/str(year)
        root.mkdir(exist_ok=True)
        scores.to_parquet(root/'scores.parquet', index=False)
        for n in ('prices.parquet', 'macro.parquet', 'lifecycle.json'):
            shutil.copy2(source/n, root/n)
        context = dict(common, batch_id=batch, model=str(model), model_files={str(p): digest(p) for p in files},
            frozen_fold=None, fold_schedule=schedule, lineage=lineage, years=[year],
            experiment_fit='Per-date causal fold, both fit and validation labels strictly before J')
        atomic_json(root/'protocol.json', context)
        names = ('prices.parquet', 'macro.parquet', 'lifecycle.json', 'scores.parquet', 'protocol.json')
        atomic_json(root/'ready.json', dict(files={n: digest(root/n) for n in names}))
        paths.extend(files)
        manifest['models'][str(year)] = dict(batch_id=batch, lineage=lineage, barriers=protocol['barriers'],
            universe=len(protocol['universe']), feature_count=len(reference['columns']))
        print(f'{year}: scores prepared, folds={list(lineage)} rows={len(scores)}', flush=True)
    manifest.update(status='READY', source_hashes={str(p): digest(p) for p in paths})
    atomic_json(output/'manifest.json', manifest)
    return manifest


def run(output, source=SOURCE):
    output = Path(output)
    manifest = prepare(output, source)
    results = []
    for year in MODELS:
        for count in COUNTS:
            atomic_json(output/'progress.json', dict(status='RUNNING', phase='portfolio', year=year, count=count,
                completed_runs=len(results), total_runs=9))
            verify_hashes(Path('.'), manifest['code_hashes'])
            result = run_case(output/str(year), year, count)
            results.append(result)
            atomic_json(output/f'results-{year}.json', dict(portfolios=[r for r in results if r['year'] == year]))
            print(year, count, result['status'], result.get('error', ''), flush=True)
            if result['status'] != 'COMPLETED_EXPLORATORY':
                raise RuntimeError(f'{year} TOP{count}: {result.get("error")}')
            case = output/str(year)/'BASELINE'/f'{year}-TOP{count}'
            daily = pd.read_parquet(case/'daily.parquet')
            trades = pd.read_parquet(case/'trades.parquet')
            if daily.positions.iloc[-1] or abs(result['cash_reconciliation_error']) > 1e-6:
                raise ValueError('Unclosed or unreconciled portfolio')
            if annual_metrics(result, trades, daily, year) != result['annual_metrics']:
                raise ValueError('Annual metric recomputation differs')
    verify_hashes(Path('.'), manifest['source_hashes'])
    verify_hashes(Path('.'), manifest['code_hashes'])
    report = dict(status='COMPLETED_EXPLORATORY', completed=9, failed=0, portfolios=results,
        manifest_sha256=digest(output/'manifest.json'), all_inputs_and_code_verified=True,
        models_unchanged=True, no_sql_writes=True, no_broker_orders=True)
    atomic_json(output/'report.json', report)
    lines = ['# Modèles annuels causaux — TP20/SL10', '',
        'LONG uniquement, sans trailing, capital annuel initial 4 000 USD. TOP10 primaire ; TOP20/50 secondaires.',
        '2026 : décisions jusqu’au 3 septembre, puis liquidation après vingt séances depuis l’entrée.',
        'Chaque fold doit avoir terminé apprentissage ET validation avant la décision. Aucun entraînement ici.',
        'Les réserves de données historiques et les extrapolations OOF sont dans manifest.json.', '',
        '| Année | TOP | Capital final $ | Gains $ | Pertes $ | Gagnants % | Perdants % | Rendement % | DD max % |',
        '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in results:
        m = r['annual_metrics']
        vals = [m[k] for k in ('final_capital_usd', 'winning_amount_usd', 'losing_amount_usd',
            'winning_pct', 'losing_pct', 'return_pct', 'max_drawdown_pct')]
        lines.append(f'| {r["year"]} | {r["count"]} | '+' | '.join(f'{v:.2f}' if v is not None else '—' for v in vals)+' |')
    (output/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    atomic_json(output/'progress.json', dict(status='COMPLETED_EXPLORATORY', completed_runs=9, failed_runs=0, total_runs=9))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=SOURCE)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    try:
        run(**vars(args))
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        atomic_json(args.output/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise
