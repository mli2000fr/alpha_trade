"""Historical research audit of aligned OOF scores; no supervised ensemble fitting."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oof_consensus_audit import load_component


def aligned_panel(root, definitions):
    panel = None
    inventory = []
    for name, definition in definitions.items():
        frame = load_component(Path(root), definition)
        if 'future_return' not in frame:
            raise ValueError(f'{name}: future_return missing')
        if not np.isfinite(frame[['raw_score', 'future_return']].to_numpy()).all():
            raise ValueError(f'{name}: nonfinite scores/targets')
        inventory.append({'family': name, 'rows': len(frame), 'dates': frame.date.nunique(),
            'path': definition['path'],
            'sha256': hashlib.sha256((Path(root) / definition['path']).read_bytes()).hexdigest()})
        current = frame[['date', 'symbol', 'raw_score', 'future_return']].rename(
            columns={'raw_score': name, 'future_return': f'target_{name}'})
        panel = current if panel is None else panel.merge(current, on=['date', 'symbol'], validate='one_to_one')
    if panel is None or panel.empty:
        raise ValueError('Empty aligned OOF intersection')
    targets = [f'target_{name}' for name in definitions]
    for column in targets[1:]:
        if not np.allclose(panel[targets[0]], panel[column], rtol=1e-8, atol=1e-10):
            raise ValueError('Incompatible future returns on aligned events')
    panel['future_return'] = panel[targets[0]]
    panel = panel.drop(columns=targets).sort_values(['date', 'symbol']).reset_index(drop=True)
    for name in definitions:
        panel[name] = panel.groupby('date')[name].rank(method='average', pct=True)
    panel['realized_rank'] = panel.groupby('date').future_return.rank(method='average', pct=True)
    return panel, inventory


def daily_corr(frame, left, right):
    return frame.groupby('date').apply(
        lambda g: g[left].corr(g[right]) if len(g) >= 10 and g[left].nunique() > 1
        and g[right].nunique() > 1 else np.nan, include_groups=False).dropna()


def block_ci(values, block, samples=2000):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2 * block:
        return [None, None]
    rng = np.random.default_rng(20260914)
    means = []
    for _ in range(samples):
        starts = rng.integers(0, len(values) - block + 1, size=int(np.ceil(len(values) / block)))
        indices = (starts[:, None] + np.arange(block)).ravel()[:len(values)]
        means.append(values[indices].mean())
    return np.quantile(means, [.025, .975]).tolist()


def residual_oof(panel, family, others, horizon, minimum_train=252, test_size=126):
    """Project scores on other scores using past dates only; never fit future returns."""
    dates = np.sort(panel.date.unique())
    pieces, windows = [], []
    for start in range(minimum_train + horizon, len(dates), test_size):
        train_dates, test_dates = dates[:start-horizon], dates[start:start+test_size]
        train = panel[panel.date.isin(train_dates)]
        test = panel[panel.date.isin(test_dates)].copy()
        x = np.column_stack([np.ones(len(train)), train[others].to_numpy()])
        weights = 1 / train.date.map(train.groupby('date').size()).to_numpy()
        beta = np.linalg.lstsq(x * np.sqrt(weights[:, None]),
            train[family].to_numpy() * np.sqrt(weights), rcond=None)[0]
        test['residual'] = test[family] - np.column_stack(
            [np.ones(len(test)), test[others].to_numpy()]) @ beta
        test.loc[test.residual.abs().lt(1e-12), 'residual'] = 0.
        test['residual'] = test.groupby('date').residual.rank(method='average', pct=True)
        pieces.append(test)
        windows.append({'train_end': str(pd.Timestamp(train_dates[-1]).date()),
            'test_start': str(pd.Timestamp(test_dates[0]).date()),
            'test_end': str(pd.Timestamp(test_dates[-1]).date()), 'train_rows': len(train),
            'test_rows': len(test), 'embargo_sessions': horizon})
    if not pieces:
        raise ValueError('Insufficient history for past-only projection')
    return pd.concat(pieces), windows


def audit_panel(panel, families, horizon):
    individuals, pairs, incremental = [], [], []
    errors = panel.copy()
    for family in families:
        ic = daily_corr(panel, family, 'realized_rank')
        errors[f'error_{family}'] = panel[family] - panel.realized_rank
        individuals.append({'family': family, 'ic_equal_date': float(ic.mean()),
            'ci95': block_ci(ic, max(20, horizon)+1), 'positive_ic_dates': float(ic.gt(0).mean())})
    for a, b in combinations(families, 2):
        scores = daily_corr(panel, a, b)
        errors_corr = daily_corr(errors, f'error_{a}', f'error_{b}')
        # Relative cross-sectional direction, not calibrated LONG/SHORT probabilities.
        valid = panel.realized_rank.ne(.5) & panel[a].ne(.5) & panel[b].ne(.5)
        work = panel[valid].copy()
        wrong_a = work[a].gt(.5).ne(work.realized_rank.gt(.5))
        wrong_b = work[b].gt(.5).ne(work.realized_rank.gt(.5))
        rates = pd.DataFrame({'date': work.date, 'joint_wrong': wrong_a & wrong_b,
            'a_rescues_b': ~wrong_a & wrong_b, 'b_rescues_a': wrong_a & ~wrong_b})
        pairs.append({'a': a, 'b': b, 'score_corr_equal_date': float(scores.mean()),
            'rank_error_corr_equal_date': float(errors_corr.mean()),
            **{c: float(rates.groupby('date')[c].mean().mean()) for c in rates if c != 'date'}})
    for family in families:
        others = [c for c in families if c != family]
        oof, windows = residual_oof(panel, family, others, max(20, horizon))
        ic = daily_corr(oof, 'residual', 'realized_rank')
        original_ic = daily_corr(oof, family, 'realized_rank')
        delta = ic - original_ic
        semester = ic.groupby(ic.index.year.astype(str) + np.where(ic.index.month <= 6, 'H1', 'H2')).mean()
        ci = block_ci(ic, max(20, horizon)+1)
        incremental.append({'family': family, 'conditioned_on': others,
            'residual_ic_equal_date': float(ic.mean()), 'ci95': ci,
            'original_ic_same_dates': float(original_ic.mean()),
            'residual_minus_original_ic': float(delta.mean()),
            'delta_ci95': block_ci(delta, max(20, horizon)+1),
            'positive_semester_ratio': float(semester.gt(0).mean()),
            'semesters': semester.to_dict(), 'windows': windows,
            'flag': 'DESCRIPTIVE_CANDIDATE' if ci[0] is not None and ci[0] > 0
                and semester.gt(0).mean() >= .6 else 'NO_DEMONSTRATED_INCREMENTAL_SIGNAL'})
    return {'horizon': horizon, 'rows': len(panel), 'dates': panel.date.nunique(),
        'symbols': panel.symbol.nunique(), 'first_date': str(panel.date.min().date()),
        'last_date': str(panel.date.max().date()), 'individuals': individuals,
        'pairs': pairs, 'incremental': incremental}


def run(root, output):
    root = Path(root)
    shared = 'artifacts/models/shared_directional/shared-dual-threshold-20260909124129-323684'
    ranker = 'artifacts/models/conditional_oracle_ranker/conditional-oracle-ranker-20260909124132-323684'
    definitions = lambda h: {
        'dual_threshold': {'path': f'{shared}/h{h}/oof_predictions.parquet',
            'score': {'type': 'column', 'column': 'direction_margin'}},
        'conditional_ranker': {'path': f'{ranker}/h{h}/oof_predictions.parquet',
            'score': {'type': 'column', 'column': 'conditional_rank_score'}}}
    results = []
    gate_path = root / 'artifacts/models/model-factory-20260909051302-323684/_oracle_oof_gate.parquet'
    gate = pd.read_parquet(gate_path)
    admitted = gate[gate.directional_oracle_oof_available.eq(True)
        & gate.directional_oracle_eligible.eq(True)][['date', 'symbol']].copy()
    admitted['date'] = pd.to_datetime(admitted.date).dt.normalize()
    admitted['symbol'] = admitted.symbol.astype(str).str.upper().str.strip()
    if admitted.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate canonical Oracle OOF membership')
    for horizon in [3, 10, 20]:
        panel, inventory = aligned_panel(root, definitions(horizon))
        checked = panel[['date','symbol']].merge(admitted, on=['date','symbol'],
            how='left', indicator=True, validate='one_to_one')
        if checked['_merge'].ne('both').any():
            raise ValueError('Scores contain events outside canonical Oracle OOF TOP20')
        result = audit_panel(panel, list(definitions(horizon)), horizon)
        result['inventory'] = inventory
        results.append(result)
    report = {'experiment': 'DIRECTIONAL_COMPLEMENTARITY_AUDIT_V1',
        'oracle_batch_id': 'model-factory-20260909051302-323684', 'research_only': True,
        'promotion_authorized': False, 'verdict': 'HISTORICAL_DIAGNOSTIC_ONLY',
        'gate_sha256': hashlib.sha256(gate_path.read_bytes()).hexdigest(),
        'temporal_contract': {'oracle_selection_horizon': 20, 'bootstrap_block_sessions': 21,
            'minimum_projection_train_dates': 252, 'projection_test_dates': 126,
            'projection_embargo_dates': 20, 'target_used_for_projection': False},
        'limitations': ['Previously observed history; not independent confirmation',
            'Past-only score projections do not prove supervised incremental predictability',
            'Pointwise block intervals are not corrected for multiple comparisons',
            'No PnL, execution prices or portfolio evaluated',
            'Two available compatible families only; old seven-family artifacts absent',
            'D1/D10 classifier excluded: future-conditioned tail-only coverage',
            'Opening signals excluded: later decision time and different Oracle universe',
            'Daily regime excluded: date-constant, not cross-sectional expert',
            'Raw component outputs lack per-event training cutoffs; upstream OOF provenance relied upon'],
        'results': results}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'report.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    pd.DataFrame([{'horizon': r['horizon'], **{k:v for k,v in i.items() if k not in ['windows','semesters']}}
        for r in results for i in r['incremental']]).to_csv(output / 'incremental_metrics.csv', index=False)
    pd.DataFrame([{'horizon': r['horizon'], **p} for r in results for p in r['pairs']]).to_csv(
        output / 'pair_metrics.csv', index=False)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or Path('artifacts/research/directional_complementarity') / datetime.now(UTC).strftime('audit-%Y%m%d%H%M%S')
    run(args.project_root, output)
    print(f'Directional complementarity audit complete: {output}')


if __name__ == '__main__':
    main()
