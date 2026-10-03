"""Read-only US H20 amplitude audit using archived E22 OOF predictions."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

LOG = logging.getLogger(__name__)
DEFAULT_SOURCE = Path('artifacts/research/oracle_trajectory/e22-h20-20260915190508')


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atr_panel(bars: pd.DataFrame) -> pd.DataFrame:
    # Reuse production adjustment, ATR and continuity contracts, not new formulas.
    from modelFactory.features import _atr_value, _build_adjusted_price_frame
    from modelFactory.oracle.security_continuity import (
        load_security_discontinuities, split_frame_on_discontinuities,
    )
    discontinuities = load_security_discontinuities()
    parts = []
    for symbol, group in bars.groupby('symbol', sort=False):
        for segment in split_frame_on_discontinuities(group, symbol, discontinuities):
            segment = segment.sort_values('date').reset_index(drop=True)
            prices = _build_adjusted_price_frame(segment)
            score = _atr_value(prices.high, prices.low, prices.close, 20)
            out = segment[['date', 'symbol']].copy()
            out['atr20_pct'] = score / prices.close.clip(lower=1e-8)
            parts.append(out)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def validate_oof(frame: pd.DataFrame) -> None:
    required = {'date', 'symbol', 'fold_start', 'proba_extreme', 'oracle_extreme10'}
    if required - set(frame):
        raise ValueError(f'Missing OOF columns: {required - set(frame)}')
    if frame.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate OOF date/symbol')
    if frame['fold_start'].isna().any() or (frame.date < frame.fold_start).any():
        raise ValueError('Invalid fold provenance')
    if not frame.proba_extreme.between(0, 1).all():
        raise ValueError('Invalid Oracle probabilities')


def daily_metrics(frame: pd.DataFrame, *, pct: float = .20, seed: int = 17,
                  min_universe: int = 20) -> pd.DataFrame:
    """Select before examining label availability; tie breaker independent of target."""
    if not 0 < pct <= 1:
        raise ValueError('pct must be in (0,1]')
    rows = []
    for day, group in frame.groupby('date', sort=True):
        group = group.sort_values('symbol').reset_index(drop=True).copy()
        if len(group) < min_universe:
            continue
        if group.fold_start.nunique() != 1:
            raise ValueError('Multiple folds for a date')
        group['_tie'] = [hashlib.sha256(f'{seed}|{day}|{s}'.encode()).hexdigest()
                         for s in group.symbol]
        k = math.ceil(pct * len(group))
        selections = {
            'ORACLE': group.sort_values(['proba_extreme', '_tie'], ascending=[False, True]).index[:k],
            'ATR': group.sort_values(['atr20_pct', '_tie'], ascending=[False, True]).index[:k],
            'RANDOM': group.sort_values('_tie').index[:k],
        }
        known = group.target.notna()
        prevalence = float(group.loc[known, 'target'].mean())
        total_positive = float(group.target.sum())
        common = len(set(selections['ATR']) & set(selections['ORACLE']))
        for policy, indices in selections.items():
            selected = group.loc[indices]
            evaluated = selected.target.dropna()
            precision = float(evaluated.mean()) if len(evaluated) else np.nan
            rows.append(dict(date=day, fold_start=group.fold_start.iloc[0], policy=policy,
                             universe=len(group), selected=k, known_labels=int(known.sum()),
                             evaluated_selected=len(evaluated), prevalence=prevalence,
                             precision=precision,
                             recall=float(evaluated.sum()/total_positive) if total_positive else np.nan,
                             lift=precision/prevalence if prevalence else np.nan,
                             overlap_fraction=common/k, jaccard=common/(2*k-common)))
    if not rows:
        raise ValueError('No eligible dates')
    return pd.DataFrame(rows)


def summarize(daily: pd.DataFrame) -> dict:
    daily = daily.copy()
    dates = pd.to_datetime(daily.date)
    daily['semester'] = dates.dt.year.astype(str) + np.where(dates.dt.month.le(6), 'H1', 'H2')
    output = {}
    for level in ['overall', 'semester', 'fold_start']:
        keys = ['policy'] if level == 'overall' else [level, 'policy']
        table = daily.groupby(keys, dropna=False).agg(
            dates=('precision', 'size'), precision=('precision', 'mean'),
            recall=('recall', 'mean'), lift=('lift', 'mean'),
            overlap_fraction=('overlap_fraction', 'mean'), jaccard=('jaccard', 'mean'),
            selected=('selected', 'sum'), evaluated_selected=('evaluated_selected', 'sum'))
        output[level] = table.reset_index().astype({level: str} if level != 'overall' else {}).to_dict('records')
    paired = daily.pivot(index='date', columns='policy', values='precision')
    delta = paired.ORACLE - paired.ATR
    output['paired'] = {'mean_daily_precision_delta_oracle_minus_atr': float(delta.mean()),
                        'daily_oracle_win_fraction': float((delta > 0).mean()),
                        'daily_tie_fraction': float((delta == 0).mean())}
    return output


def split_window_sensitivity(panel: pd.DataFrame) -> dict:
    """Post-hoc diagnostic, not a corrected refit or a new selection policy."""
    dates = pd.Index(sorted(panel.date.unique()))
    excluded = set()
    for day in ['2021-07-20', '2024-06-10']:
        position = dates.searchsorted(pd.Timestamp(day))
        excluded.update(dates[max(0, position-20):position+20])
    retained = panel[~panel.date.isin(excluded)]
    return {'status': 'POST_HOC_SENSITIVITY_NOT_CORRECTED_REFIT',
            'excluded_sessions': len(excluded),
            'rule': '20 archive sessions before and 20 from each confirmed NVIDIA split',
            'metrics': summarize(daily_metrics(retained))}


def run(source: Path, output: Path) -> Path:
    from database.connection import get_sqlalchemy_engine
    from modelFactory.data_loader import load_universe_bars
    from modelFactory.oracle.dataset import load_oracle_targets
    report_path = source / 'report.json'
    oof_path = source / 'o0_baseline_oos.parquet'
    provenance = json.loads(report_path.read_text(encoding='utf-8'))
    if provenance['horizon'] != 20 or provenance['status'] != 'COMPLETED_RESEARCH_ONLY':
        raise ValueError('Expected completed E22 H20 research source')
    if provenance['experiment'] != 'E22_ORACLE_PRE_SIGNAL_TRAJECTORY':
        raise ValueError('Unsupported OOF provenance')
    frame = pd.read_parquet(oof_path)
    for col in ['date', 'fold_start']:
        frame[col] = pd.to_datetime(frame[col]).dt.normalize()
    validate_oof(frame)
    expected_folds = {pd.Timestamp(f['fold_start']) for f in provenance['results']['O0_BASELINE']['folds']}
    if set(frame.fold_start.unique()) != expected_folds:
        raise ValueError('OOF folds disagree with archived report')
    if len(frame) != provenance['results']['O0_BASELINE']['overall']['rows']:
        raise ValueError('OOF row count disagrees with archived report')
    engine = get_sqlalchemy_engine()
    if engine.url.database != 'alpha_trade':
        raise ValueError('US audit requires alpha_trade database')
    output.mkdir(parents=True, exist_ok=False)
    LOG.info('OOF rows=%s dates=%s symbols=%s', len(frame), frame.date.nunique(), frame.symbol.nunique())
    start = (frame.date.min() - pd.Timedelta(days=1100)).date()
    bars = load_universe_bars(engine, sorted(frame.symbol.unique()), start_date=start,
                              end_date=frame.date.max().date())
    LOG.info('Calculating canonical ATR on %s bars', len(bars))
    atr = atr_panel(bars)
    targets = load_oracle_targets(engine, provenance['batch_id'], horizon=20)
    engine.dispose()
    targets = targets.rename(columns={'prediction_date': 'date', 'oracle_extreme10': 'target'})
    if targets.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate canonical labels')
    panel = frame.merge(atr, on=['date', 'symbol'], how='left', validate='one_to_one')
    panel = panel.merge(targets[['date', 'symbol', 'target']], on=['date', 'symbol'],
                        how='left', validate='one_to_one')
    known = panel.target.notna()
    disagreements = int((panel.loc[known, 'target'] != panel.loc[known, 'oracle_extreme10']).sum())
    if disagreements:
        raise ValueError(f'Archived/current label disagreement: {disagreements}; audit first')
    usable = np.isfinite(panel.atr20_pct) & panel.atr20_pct.ge(0)
    matched = panel[usable].copy()
    if matched.target.notna().mean() < .95:
        raise ValueError('Current valid label coverage below 95%; audit first')
    if matched.groupby('date').target.apply(lambda values: values.notna().mean()).min() < .95:
        raise ValueError('Daily valid label coverage below 95%; audit first')
    daily = daily_metrics(matched)
    daily.to_parquet(output / 'daily_metrics.parquet', index=False)
    matched.to_parquet(output / 'comparison_panel.parquet', index=False)
    result = dict(experiment='US_H20_ATR_VS_ORACLE', status='COMPLETED_RESEARCH_ONLY',
                  batch_id=provenance['batch_id'], horizon=20,
                  source=str(source), source_oof_sha256=sha256(oof_path),
                  source_report_sha256=sha256(report_path),
                  selection={'pct': .2, 'min_universe': 20, 'seed': 17,
                             'ranking_before_label_filter': True},
                  coverage={'oof_rows': len(frame), 'matched_rows': len(matched),
                            'missing_atr_rows': int((~usable).sum()),
                            'unknown_or_invalid_labels': int(matched.target.isna().sum()),
                            'label_disagreements': disagreements,
                            'dates': int(matched.date.nunique()), 'symbols': int(matched.symbol.nunique()),
                            'start': str(matched.date.min().date()), 'end': str(matched.date.max().date())},
                  metrics=summarize(daily),
                  split_window_sensitivity=split_window_sensitivity(matched),
                  limitations=['Historical research universe, not production tradability audit',
                               'Adjusted price history is current vendor vintage, not archived daily vintages',
                               'Repeated H20 labels overlap; daily observations are not independent',
                               'Archived E22 O0 scores, not the latest serving batch',
                               'NVIDIA split corrections were research-only; corrected OOF archives under work/ are absent',
                               'Split-window exclusion cannot undo contamination of historical training features or labels',
                               'No direction, portfolio, costs or economic profitability measured'])
    (output / 'report.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    LOG.info('Finished: %s', output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    output = args.output or Path('artifacts/research/us_atr_oracle') / datetime.now(UTC).strftime('us-h20-%Y%m%d%H%M%S')
    run(args.source, output)


if __name__ == '__main__':
    main()
