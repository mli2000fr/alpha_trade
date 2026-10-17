"""Read archived Oracle TP20/SL10 evidence; no training, SQL or trading calls.

The tables describe previously observed outcomes. They do not select a new
strategy or claim that omitting losing trades would reproduce a portfolio.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


MODEL = Path('artifacts/models/model-factory-20261012183840-6d6569/oracle_barrier')
BASELINE = Path('artifacts/research/us_oracle_tp20_sl10_new/20261012-v6')
CHALLENGERS = Path('artifacts/research/us_oracle_challengers/20261013-v2')
LONG = 'proba_long_tp_before_sl'
SHORT = 'proba_short_tp_before_sl'


def digest(path):
    result = sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def describe(values, weights=None):
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(values)
    if weights is None:
        weights = np.ones(len(values))
    weights = np.asarray(weights, dtype=float)
    valid &= np.isfinite(weights) & (weights > 0)
    values, weights = values[valid], weights[valid]
    if not len(values):
        return {'count': 0}
    order = np.argsort(values, kind='stable')
    median = values[order][np.searchsorted(np.cumsum(weights[order]), weights.sum() / 2)]
    return dict(count=len(values), weight_sum=float(weights.sum()),
                mean=float(np.average(values, weights=weights)),
                median=float(median), positive_pct=float(100 * weights[values > 0].sum() / weights.sum()),
                p05=float(np.quantile(values, .05)), p95=float(np.quantile(values, .95)))


def sum_groups(frame, column):
    return [dict(group=str(name), rows=len(part), pnl_usd=float(part.pnl.sum()))
            for name, part in frame.groupby(column, dropna=False)]


def auc(target, score):
    valid = pd.DataFrame({'target': target, 'score': score}).dropna()
    return float(roc_auc_score(valid.target, valid.score)) if valid.target.nunique() > 1 else None


def actual_trades(scores, sources):
    results = []
    for folder in sorted((BASELINE / 'BASELINE').iterdir()):
        path = folder / 'trades.parquet'
        sources.add(path)
        frame = pd.read_parquet(path)
        if frame.empty:
            raise ValueError(f'Empty completed baseline: {folder}')
        frame['entry_identity'] = frame.entry_symbol.fillna(frame.symbol) if 'entry_symbol' in frame else frame.symbol
        frame['signal_date'] = pd.to_datetime(frame.signal_date)
        frame['entry_date'] = pd.to_datetime(frame.entry_date)
        frame['exit_date'] = pd.to_datetime(frame.exit_date)
        # These nine baselines contain one closed leg per original position.
        if frame.duplicated(['entry_identity', 'entry_date']).any():
            raise ValueError('Position legs require explicit aggregation before this audit')
        if not frame.side.eq('buy').all():
            raise ValueError('Expected archived LONG baseline')
        merged = frame.merge(scores, left_on=['signal_date', 'entry_identity'],
                             right_on=['date', 'symbol'], suffixes=('', '_score'),
                             how='left', validate='many_to_one')
        if merged[[LONG, SHORT]].isna().any().any():
            raise ValueError(f'Missing original entry scores in {folder}')
        gross = (merged.exit_price - merged.entry_price) * merged.quantity
        merged['total_cost_usd'] = gross - merged.pnl
        stop_gaps = merged.exit_reason.eq('initial_stop_gap_open')
        gap_excess = ((merged.replay_initial_stop_price - merged.exit_price).clip(lower=0)
                      * merged.quantity).where(stop_gaps, 0)
        merged['winner'] = merged.pnl.gt(0).astype(int)
        merged['raw_return_pct'] = 100 * (merged.exit_price / merged.entry_price - 1)
        merged = merged.sort_values(['entry_date', 'entry_identity'])
        merged['reentry'] = merged.groupby('entry_identity').cumcount().gt(0)
        previous_exit = merged.groupby('entry_identity').exit_date.shift()
        previous_pnl = merged.groupby('entry_identity').pnl.shift()
        gap_days = (merged.entry_date - previous_exit).dt.days
        merged['quick_reentry_after_loss'] = previous_pnl.lt(0) & gap_days.between(0, 5)
        grouped_loss = merged.loc[merged.pnl.lt(0)].groupby('entry_identity').pnl.sum().sort_values()
        worst = merged.nsmallest(5, 'pnl')
        winners, losers = merged.loc[merged.pnl.gt(0)], merged.loc[merged.pnl.lt(0)]
        win_mean, loss_mean = float(winners.pnl.mean()), float(-losers.pnl.mean())
        # Diagnostic break-even frequency assumes these retrospective mean payoffs
        # persist. It is not a predictive threshold for a calibrated score.
        break_even = loss_mean / (win_mean + loss_mean)
        item = dict(case=folder.name, positions=len(merged), pnl_usd=float(merged.pnl.sum()),
                    winners=len(winners), win_pct=float(100 * merged.winner.mean()),
                    total_cost_usd=float(merged.total_cost_usd.sum()),
                    adverse_stop_gap_excess_usd=float(gap_excess.sum()),
                    mean_winner_usd=win_mean, mean_loser_usd=-loss_mean,
                    realized_mean_gain_loss_ratio=win_mean / loss_mean,
                    retrospective_break_even_win_pct=100 * break_even,
                    winner_gross_return_pct=float(winners.raw_return_pct.mean()),
                    loser_gross_return_pct=float(losers.raw_return_pct.mean()),
                    raw_long_score=describe(merged[LONG]), raw_short_score=describe(merged[SHORT]),
                    stored_percentile_score=describe(merged.score),
                    auc_raw_long_vs_net_win=auc(merged.winner, merged[LONG]),
                    auc_long_minus_short_vs_net_win=auc(merged.winner, merged[LONG] - merged[SHORT]),
                    short_score_above_long_count=int(merged[SHORT].gt(merged[LONG]).sum()),
                    exit_reasons=sum_groups(merged, 'exit_reason'),
                    first_vs_reentry=sum_groups(merged, 'reentry'),
                    rapid_reentry_after_loss=sum_groups(merged, 'quick_reentry_after_loss'),
                    entry_months=sum_groups(merged.assign(entry_month=merged.entry_date.dt.strftime('%Y-%m')), 'entry_month'),
                    worst_loss_symbols=[dict(symbol=name, losing_pnl_usd=float(value)) for name, value in grouped_loss.head(5).items()],
                    worst_trades=worst[['entry_identity', 'entry_date', 'exit_date', 'pnl', 'raw_return_pct', 'exit_reason']]
                        .to_dict('records'))
        results.append(item)
    if len(results) != 9:
        raise ValueError('Nine archived baseline cases required')
    return results


def selected_summary(frame, side):
    target, outcome, score = f'{side}_tp_before_sl', f'{side}_outcome', LONG if side == 'long' else SHORT
    known = frame.dropna(subset=[target])
    return dict(selected=len(frame), known=len(known),
                tp_pct=float(100 * known[target].mean()),
                mean_score_pct=float(100 * known[score].mean()),
                mean_gross_return_pct=float(100 * known[f'{side}_gross_return'].mean()),
                outcomes={str(k): int(v) for k, v in known[outcome].value_counts().items()})


def oof_analysis(sources):
    path = MODEL / 'oof_predictions.parquet'
    sources.add(path)
    columns = ['date', 'symbol', 'fold_start', LONG, SHORT, 'long_tp_before_sl', 'short_tp_before_sl',
               'long_outcome', 'short_outcome', 'long_gross_return', 'short_gross_return']
    frame = pd.read_parquet(path, columns=columns)
    if frame.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate OOF observations')
    results = dict(rows=len(frame), dates=int(frame.date.nunique()), start=str(frame.date.min()),
                   end=str(frame.date.max()), outcome_returns={}, fixed_top_counts=[])
    for side in ('long', 'short'):
        known = frame.dropna(subset=[f'{side}_tp_before_sl'])
        results['outcome_returns'][side] = {
            outcome: dict(rows=len(part), mean_gross_return_pct=float(100 * part[f'{side}_gross_return'].mean()))
            for outcome, part in known.groupby(f'{side}_outcome')}
    last_fold = max(frame.fold_start.astype(str).unique())
    for side, score in [('long', LONG), ('short', SHORT)]:
        ranked = frame.sort_values(['date', score, 'symbol'], ascending=[True, False, True])
        ranked['selection_rank'] = ranked.groupby('date', sort=False).cumcount() + 1
        for count in (10, 20, 50):
            selected = ranked.loc[ranked.selection_rank.le(count)]
            results['fixed_top_counts'].append(dict(side=side, top=count, **selected_summary(selected, side)))
            if count == 10:
                results[f'latest_fold_top10_{side}'] = selected_summary(
                    selected.loc[selected.fold_start.astype(str).eq(last_fold)], side)
    maximum = frame.assign(max_score=frame[[LONG, SHORT]].max(axis=1)).sort_values(
        ['date', 'max_score', 'symbol'], ascending=[True, False, True])
    selected = maximum.loc[maximum.groupby('date', sort=False).cumcount().lt(10)]
    paired = selected.dropna(subset=['long_tp_before_sl', 'short_tp_before_sl'])
    for name, subset in [('all_folds', paired), ('last_fold', paired.loc[paired.fold_start.astype(str).eq(last_fold)])]:
        chosen_long = subset[LONG].gt(subset[SHORT])
        unique_choice = subset[LONG].sub(subset[SHORT]).abs().gt(1e-12)
        evaluated = subset.loc[unique_choice]
        chosen = np.where(chosen_long.loc[unique_choice], evaluated.long_tp_before_sl, evaluated.short_tp_before_sl)
        results[f'argmax_top10_{name}'] = dict(paired=len(evaluated),
            long_choices=int(chosen_long.loc[unique_choice].sum()),
            short_choices=int((~chosen_long.loc[unique_choice]).sum()),
            argmax_tp_pct=float(100 * chosen.mean()),
            always_long_tp_pct=float(100 * evaluated.long_tp_before_sl.mean()),
            always_short_tp_pct=float(100 * evaluated.short_tp_before_sl.mean()))
    return results


def auxiliary_targets(sources):
    result = {}
    for name, target in [('entry', 'unit_net_return'), ('exit', 'keep_advantage')]:
        path = CHALLENGERS / 'fit-data' / f'{name}-training.parquet'
        sources.add(path)
        columns = ['date', 'label_available', target]
        if name == 'exit':
            columns.append('weight')
        frame = pd.read_parquet(path, columns=columns)
        fit = frame.loc[frame.date.lt('2022-01-01') & frame.label_available.lt('2022-01-01')]
        val = frame.loc[frame.date.between('2022-01-01', '2022-12-31') & frame.label_available.lt('2023-01-01')]
        result[name] = {period: describe(part[target], part.weight if name == 'exit' else None)
                        for period, part in [('fit', fit), ('validation', val)]}
    model_paths = [CHALLENGERS / 'ENTRY_FILTER/models/label_win.json',
                   CHALLENGERS / 'DAILY_EXIT/models/keep_advantage.json']
    for path in model_paths:
        sources.add(path)
        result[path.parent.parent.name] = load_json(path)
    result['regression_objective'] = 'huber; early stopping on unweighted validation L1'
    result['interpretation'] = ('Huber/L1 optimize robust error, not conditional mean PnL. '
                                'This is an objective-alignment concern, not proof that another loss will improve trading.')
    return result


def model_importance(sources):
    import lightgbm as lgb
    fold = sorted((MODEL / 'folds').iterdir())[-1]
    sources.update([MODEL / 'protocol.json', MODEL / 'report.json', fold / 'done.json'])
    results = dict(fold=fold.name, metrics=load_json(fold / 'done.json')['metrics'], heads={})
    for side in ('long', 'short'):
        path = fold / f'{side}_model.txt'
        sources.add(path)
        booster = lgb.Booster(model_file=str(path))
        gains = booster.feature_importance(importance_type='gain')
        items = sorted(zip(booster.feature_name(), gains), key=lambda x: -x[1])
        total = float(gains.sum())
        results['heads'][side] = dict(trees=booster.num_trees(), features=len(items),
            zero_gain_features=int((gains == 0).sum()),
            top_features=[dict(name=name, gain_share_pct=100 * float(gain) / total)
                          for name, gain in items[:10]])
    return results


def run(output):
    sources = {Path(__file__), Path('scripts/research/us_oracle_tp20_sl10_models.py'),
               MODEL / 'labels.parquet', BASELINE / 'scores.parquet'}
    scores = pd.read_parquet(BASELINE / 'scores.parquet')
    if scores.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate archived serving scores')
    report = dict(status='ARCHIVED_DIAGNOSTICS_COMPLETE', batch_id=MODEL.parent.name,
                  model=model_importance(sources), actual_long_portfolios=actual_trades(scores, sources),
                  oof=oof_analysis(sources), auxiliary_targets=auxiliary_targets(sources),
                  limitations=['descriptive on already observed periods; no newly evaluated trading rule',
                               'OOF overlapping unit paths are not portfolio returns',
                               'no calibrated inter-head probabilities established',
                               'retrospective payoffs are not an ex-ante break-even threshold',
                               'static survivor universe, current sectors and adjusted histories',
                               'source date availability not independently certified'],
                  training_performed=False, sql_writes=False, broker_calls=False,
                  production_changes=False)
    report['input_sha256'] = {str(path): digest(path) for path in sorted(sources)}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'report.json'
    if target.exists():
        raise ValueError('Use a new output directory; existing diagnostic is preserved')
    temporary = output / 'report.pending.json'
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding='utf-8')
    temporary.replace(target)
    print(json.dumps(dict(status=report['status'], report=str(target), portfolios=9,
                         oof_rows=report['oof']['rows']), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='artifacts/research/us_oracle_loss_audit/20261013-v1')
    run(parser.parse_args().output)
