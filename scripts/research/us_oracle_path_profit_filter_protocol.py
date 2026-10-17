"""Point 2 preparation only: evidence inventory and frozen observable TOP20.

No learner, label calculation, SQL, API, broker or portfolio is invoked here.
Future labels are deliberately absent from the prepared candidate population.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json


SPEC = Path('config/research/oracle_path_profit_filter_tp10_sl10.json')
HISTORY = Path('artifacts/research/oracle_path_comparison/20261013-v1/models/oracle-path-comparison/oracle_path')
DATASET = Path('artifacts/research/us_oracle_path_protection_dataset/20261014-v1')
COMPARISON = Path('artifacts/research/us_news_gpt_long_comparison/20261015-v1')
SAFE_SCORE_COLUMNS = ['date', 'symbol', 'score', 'fold_start']
PRICE_COLUMNS = {'date', 'symbol', 'open', 'high', 'low', 'close', 'adj_close',
                 'volume', 'instrument_id', 'is_filled', 'data_source', 'data_adjustment'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def require_hash(path, expected):
    actual = digest(path)
    if actual != expected:
        raise ValueError(f'Immutable input changed: {path}')
    return actual


def freeze_top20(scores):
    """Whitelist first, rank before inspecting any quality or future outcome."""
    part = scores[SAFE_SCORE_COLUMNS].copy()
    part['date'] = pd.to_datetime(part.date).dt.normalize()
    part['fold_start'] = pd.to_datetime(part.fold_start).dt.normalize()
    part['score'] = pd.to_numeric(part.score, errors='raise')
    if part[SAFE_SCORE_COLUMNS].isna().any().any() or part.duplicated(['date', 'symbol']).any():
        raise ValueError('Missing or duplicate observable score key')
    if not np.isfinite(part.score).all() or not part.score.between(0, 1).all():
        raise ValueError('Invalid amplitude score')
    if part.symbol.astype(str).str.strip().eq('').any():
        raise ValueError('Empty symbol')
    if part.groupby('date').size().lt(20).any():
        raise ValueError('Fewer than twenty observable candidates')
    part = part.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True])
    part['oracle_rank'] = part.groupby('date').cumcount() + 1
    return part[part.oracle_rank.le(20)].reset_index(drop=True)


def causal_fold(metrics):
    start, end = pd.Timestamp(metrics['test_start']), pd.Timestamp(metrics['test_end'])
    if pd.isna(start) or pd.isna(end) or start > end:
        raise ValueError('Invalid fold window')
    for key in ('train_available_max', 'val_available_max'):
        available = pd.Timestamp(metrics[key])
        if pd.isna(available) or available >= start:
            raise ValueError('Oracle training/validation label leaks into scored period')
    return start, end


def split_for_label(day, available, spec):
    """Future label availability is mandatory, even if TP was touched early."""
    day, available = pd.Timestamp(day), pd.Timestamp(available)
    if pd.isna(available):
        return 'UNKNOWN_LABEL'
    if pd.isna(day) or available <= day:
        raise ValueError('Invalid label chronology')
    for name in ('fit', 'validation', 'control'):
        block = spec['splits'][name]
        if pd.Timestamp(block['decision_start']) <= day <= pd.Timestamp(block['decision_end']):
            return name.upper() if available < pd.Timestamp(block['label_before']) else 'PURGED_' + name.upper()
    return 'OUTSIDE_FIT_VALIDATION_CONTROL'


def duplicate_audit():
    return dict(verdict='PARTIAL_DUPLICATE_BOUNDED_REPLICATION_ONLY',
        genuinely_new_signal_family=False,
        previous=[
            dict(name='E3-A', source='modelFactory/path_aware_directional.py',
                 shared='Conditional Oracle pool; binary net profitable trade; positive expiry already included',
                 different='Terminal Oracle TOP20 percent; two heads; ATR barriers; TP cap7; expiry close; legacy costs',
                 result='LONG AUC .541 but economic lift -.064 percentage point; NO_GO'),
            dict(name='E3-A2', source='modelFactory/path_aware_utility.py',
                 shared='Net economic outcome after Oracle conditioning',
                 different='Expected utility/tail risk regression, not single binary TP10SL10 head',
                 result='No stable economic improvement'),
            dict(name='ENTRY_FILTER_20261013', source='scripts/research/us_oracle_challengers.py',
                 shared='Small LightGBM net-win filter; next open; expiry; threshold .5; positive expiry included',
                 different='Barrier Oracle TP20SL10 pool/long-short inputs; TOP10 primary; flat cost proxy',
                 result='Validation AUC .50021; all test probabilities below .5; no entries'),
            dict(name='ORACLE_BARRIER', source='modelFactory/oracle_barrier/labels.py',
                 shared='Next open and first TP/SL path',
                 different='Target is TP-before-SL; expired target zero even if profitable; independent LONG/SHORT',
                 result='Not a universal net-profit target; no new evidence from changing target name'),
            dict(name='ENTRY_SEPARABILITY_20261014', source='scripts/research/us_oracle_path_entry_separability.py',
                 shared='Path Oracle shortlist and J features',
                 different='Univariate TP20-before-SL10 label; LightGBM upstream; not multivariate net-profit classifier',
                 result='No stable univariate separation'),
            dict(name='PROTECTION_SELECTOR_20261014', source='scripts/research/us_oracle_path_protection_selector.py',
                 shared='Current annual CatBoost models, 24 J-only features, purged OOF',
                 different='TOP5; 3 protection utility heads; SL5/trailing; 60-session paths, not entry filter',
                 result='Constant LARGE choice; NO_GO')],
        decision='One exact-contract replication may be prepared; do not claim novel direction or rerun an unchanged old experiment')


def prepare(output, spec_path=SPEC):
    output = Path(output)
    marker = output / 'report.json'
    if marker.exists():
        report = read(marker)
        manifest = read(output / 'manifest.json')
        if manifest['spec_path'] != str(spec_path):
            raise ValueError('Different specification; fresh output required')
        for name, expected in manifest['sources'].items():
            require_hash(name, expected)
        for name, expected in report['files'].items():
            require_hash(output / name, expected)
        return report
    if (output / 'manifest.json').exists():
        raise ValueError('Incomplete preparation; use a fresh output directory')
    output.mkdir(parents=True, exist_ok=True)
    spec = read(spec_path)
    if spec['population']['top_titles'] != 20 or spec['safety']['training_in_this_preparation']:
        raise ValueError('This preparer cannot run another contract or fit a model')
    sources = {}

    def bind(path, expected=None):
        path = Path(path)
        value = require_hash(path, expected) if expected else digest(path)
        sources[str(path)] = value
        return value

    for path in [spec_path, Path(__file__), Path('tests/test_us_oracle_path_profit_filter_protocol.py'),
                 DATASET/'protocol.json', DATASET/'report.json', DATASET/'completion-audit.json',
                 HISTORY/'protocol.json', HISTORY/'feature_profile.json',
                 COMPARISON/'ready.json', COMPARISON/'report.json', COMPARISON/'audit.json']:
        bind(path)
    reference = read(DATASET/'report.json')
    audit = read(DATASET/'completion-audit.json')
    if audit['status'] != 'DATASET_KEYS_TARGETS_AND_PURGES_VERIFIED':
        raise ValueError('Historical OOF qualification absent')
    require_hash(DATASET/'report.json', audit['source_report_sha256'])
    for name, expected in reference['files'].items():
        # This preparation needs score caches only, not the old 60-session labels.
        if Path(name).name in ('done.json', 'observable-scores.parquet'):
            bind(DATASET/name, expected)
    compared = read(COMPARISON/'ready.json')
    if read(COMPARISON/'report.json')['status'] != 'COMPLETED' or not read(COMPARISON/'audit.json')['status'].startswith('AUDITED'):
        raise ValueError('Completed matched TP10SL10 comparison required')
    bind(COMPARISON/'candidates.parquet', compared['files']['candidates.parquet'])
    historical_protocol = read(HISTORY/'protocol.json')
    if len(historical_protocol['universe']) != 1790:
        raise ValueError('Unexpected frozen universe')
    profile = read(HISTORY/'feature_profile.json')
    parts, folds = [], []
    for folder in sorted((DATASET/'folds').iterdir()):
        done = read(folder/'done.json')
        original = HISTORY/'folds'/folder.name
        bind(original/'done.json')
        old = read(original/'done.json')
        start, end = causal_fold(old['metrics'])
        bind(original/'catboost_model.cbm', old['files']['catboost_model.cbm'])
        bind(original/'oof.parquet', old['files']['oof.parquet'])
        bind(folder/'observable-scores.parquet', done['files']['observable-scores.parquet'])
        scores = pd.read_parquet(folder/'observable-scores.parquet', columns=SAFE_SCORE_COLUMNS)
        if len(scores) != done['observable_rows'] or not scores.date.between(start, end).all():
            raise ValueError('Observable OOF window or size changed')
        if not pd.to_datetime(scores.fold_start).eq(pd.Timestamp(folder.name)).all():
            raise ValueError('Wrong fold attribution')
        old_scores = pd.read_parquet(original/'oof.parquet', columns=['date', 'symbol', 'score_catboost'])
        check = old_scores.merge(scores, on=['date', 'symbol'], validate='one_to_one')
        error = float((check.score_catboost-check.score).abs().max())
        if len(check) != len(old_scores) or not np.isfinite(error) or error > 1e-7:
            raise ValueError('Original CatBoost score parity failed')
        top = freeze_top20(scores)
        parts.append(top)
        folds.append(dict(name=folder.name, start=str(start.date()), end=str(end.date()),
                          observable_rows=len(scores), original_oof_rows=len(old_scores),
                          original_score_max_error=error, top20_rows=len(top)))
    if len(folds) != 10:
        raise ValueError('Expected ten historical OOF folds')
    pool = pd.concat(parts, ignore_index=True)
    if pool.duplicated(['date', 'symbol']).any() or not pool.groupby('date').size().eq(20).all():
        raise ValueError('Overlapping/incomplete historical population')

    chunks = []
    for folder in sorted((HISTORY/'chunks').iterdir()):
        bind(folder/'done.json')
        declared = read(folder/'done.json')['files']
        price = folder/'bars.parquet'
        metadata = pq.ParquetFile(price)
        if not PRICE_COLUMNS <= set(metadata.schema_arrow.names):
            raise ValueError('Historical price lineage/quality schema missing')
        # Verify the actual price bytes now, not just existence of a manifest.
        bind(price, declared['bars.parquet'])
        chunks.append(dict(path=str(price), rows=metadata.metadata.num_rows,
                           bytes=price.stat().st_size, verified_sha256=declared['bars.parquet']))
    if len(chunks) != 72:
        raise ValueError('Expected all 72 archived price chunks')

    recent = pd.read_parquet(COMPARISON/'candidates.parquet', columns=[
        'date', 'symbol', 'score', 'fold_start', 'oracle_rank', 'selected', 'batch_id', 'model_available_date'])
    if recent.duplicated(['date', 'symbol']).any() or not recent.groupby('date').size().eq(20).all():
        raise ValueError('Recent TOP20 not frozen before exclusions')
    ranked = freeze_top20(recent)
    keys = recent.merge(ranked, on=['date', 'symbol'], suffixes=('_old', '_new'), validate='one_to_one')
    if not keys.oracle_rank_old.eq(keys.oracle_rank_new).all():
        raise ValueError('Recent Oracle priority differs')
    contracts = read(DATASET/'protocol.json')['annual_test_models']
    for year, batch in spec['annual_models'].items():
        rows = recent[recent.date.dt.year.eq(int(year))]
        contract = contracts[year]
        if rows.empty or not rows.batch_id.eq(batch).all() or contract['batch_id'] != batch:
            raise ValueError('Wrong annual model')
        if not pd.to_datetime(rows.model_available_date).lt(rows.date).all():
            raise ValueError('Recent Oracle label availability leak')
        root = Path('artifacts/models')/batch/'oracle_path'
        bind(root/'protocol.json')
        current_protocol = read(root/'protocol.json')
        if current_protocol.get('training_backend') != 'catboost' or current_protocol.get('backend') != 'catboost_cpu':
            raise ValueError('Wrong annual backend')
        bind(root/'feature_profile.json')
        current = read(root/'feature_profile.json')
        if any(current[k] != profile[k] for k in ('feature_columns', 'generator_options')):
            raise ValueError('Annual feature semantics changed')
        fold = root/'folds'/contract['fold']
        bind(fold/'done.json')
        done = read(fold/'done.json')
        if done['metrics']['selected_backend'] != 'catboost' or done['files']['catboost_model.cbm'] != contract['model_sha256']:
            raise ValueError('Annual selected fold is not the frozen CatBoost weight')
        if max(pd.Timestamp(done['metrics'][k]) for k in ('train_available_max', 'val_available_max')) >= rows.date.min():
            raise ValueError('Annual model is not causal for first decision')
        bind(fold/'catboost_model.cbm', contract['model_sha256'])
    for path in (Path(compared[k]) for k in ('prices', 'macro', 'sectors')):
        expected = next(v for k, v in compared['sources'].items() if Path(k) == path)
        bind(path, expected)
    for path in [Path(item['source']) for item in duplicate_audit()['previous']] + [
        Path('scripts/research/us_oracle_path_protection_dataset.py'),
        Path('modelFactory/features.py'), Path('common/trading_costs.py'),
        Path('backtesting/simulator.py'), Path('backtesting/oracle_portfolio_ledger.py'),
        Path('scripts/research/us_news_gpt_bullish_portfolio.py'),
        Path('scripts/research/us_oracle_path_top5_leverage_grid.py'), Path('config.yaml')]:
        bind(path)
    pool.to_parquet(output/'historical-top20.parquet', index=False)
    atomic_json(output/'protocol.json', spec)
    atomic_json(output/'non-duplication.json', duplicate_audit())
    atomic_json(output/'manifest.json', dict(spec_path=str(spec_path), sources=sources,
        folds=folds, price_chunks=chunks, annual_contracts=contracts,
        old_manifests_modified=False, source_normalization_tolerance=False))
    inventory = dict(historical_rows=len(pool), historical_dates=int(pool.date.nunique()),
        historical_symbols=int(pool.symbol.nunique()),
        historical_by_year={str(y):dict(rows=len(g), dates=int(g.date.nunique()), symbols=int(g.symbol.nunique()))
                            for y, g in pool.groupby(pool.date.dt.year)},
        observable_scored_rows=sum(f['observable_rows'] for f in folds),
        original_oof_rows=sum(f['original_oof_rows'] for f in folds),
        max_original_score_error=max(f['original_score_max_error'] for f in folds),
        price_chunks=len(chunks), price_rows=sum(c['rows'] for c in chunks),
        recent_rows=len(recent), recent_dates=int(recent.date.nunique()),
        recent_admissible_at_J=int(recent.selected.sum()),
        recent_by_year={str(y):dict(rows=len(g), dates=int(g.date.nunique()), admissible_at_J=int(g.selected.sum()))
                        for y, g in recent.groupby(recent.date.dt.year)},
        historical_top20_target_labels_built=False, feature_matrix_top20_built=False,
        old_TOP5_60_session_outcomes_reused_as_TP10SL10=False,
        upstream_vintages_PIT_certified=False)
    atomic_json(output/'readiness.json', inventory)
    report = dict(status='PREPARED_NOT_TRAINED', verdict='BOUNDED_REPLICATION_PROTOCOL_FROZEN',
        duplicate_audit_verdict=duplicate_audit()['verdict'], inventory=inventory,
        remaining_before_fit=['J-only TOP20 features and prefix checks',
            'native isolated TP10SL10 label parity including gaps/collisions/positive expiry and costs',
            'J22 availability, split purges, unknown label and original population coverage',
            'new explicit GO before label implementation or fitting'],
        model_fits=0, labels_computed=0, portfolio_runs=0, sql_reads=0, sql_writes=0,
        API_calls=0, broker_calls=0, live_changes=False, statistical_gain_measured=False,
        files={name:digest(output/name) for name in ['protocol.json', 'non-duplication.json',
              'manifest.json', 'historical-top20.parquet', 'readiness.json']})
    # Recheck the bound bytes at completion; never silently rewrite an old input.
    for name, expected in sources.items():
        require_hash(name, expected)
    atomic_json(marker, report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--spec', type=Path, default=SPEC)
    args = parser.parse_args()
    with exclusive_run(args.output):
        result = prepare(args.output, args.spec)
        print(json.dumps({k:v for k,v in result.items() if k not in ('files', 'inventory')}, ensure_ascii=False))
