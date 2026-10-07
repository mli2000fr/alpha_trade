"""Offline audit of the ten highest Oracle scores, not the top ten percent.

Only archived predictions are read. No SQL, training, serving or PnL.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_numeric_effect import read_json

LOG = logging.getLogger(__name__)
POLICIES = ('ORACLE_TOP10_TITLES', 'ORACLE_ATR_INTERSECTION_TOP10_TITLES', 'ATR_TOP10_TITLES')
OUTCOMES = ['oracle_extreme10', 'oracle_decile', 'future_return']


def validate_predictions(frame):
    needed = ['date', 'symbol', 'score', 'atr20_pct', 'fold_start', *OUTCOMES]
    if set(needed) - set(frame):
        raise ValueError('Missing prediction columns')
    if frame.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate prediction keys')
    if frame.date.isna().any() or frame.symbol.isna().any():
        raise ValueError('Missing prediction keys')
    if not np.isfinite(frame[['score', 'atr20_pct']].to_numpy(dtype=float)).all():
        raise ValueError('Nonfinite observable scores or ATR')


def select_top10(frame):
    """Selection is made without inspecting any realized outcome."""
    validate_predictions(frame)
    parts = []
    for _, group in frame.groupby('date', sort=True):
        if len(group) < 20:
            raise ValueError('Daily universe smaller than 20')
        ranked = group.sort_values(['score', 'symbol'], ascending=[False, True]).copy()
        ranked['oracle_rank'] = np.arange(1, len(ranked) + 1)
        atr = group.sort_values(['atr20_pct', 'symbol'], ascending=[False, True])
        count = int(np.ceil(.20 * len(group)))
        intersection = ranked.head(count)
        intersection = intersection[intersection.symbol.isin(atr.head(count).symbol)]
        # The intersection is a gate, not an alternative score or future sort.
        selections = {
            POLICIES[0]: ranked.head(10),
            POLICIES[1]: intersection.head(10),
            POLICIES[2]: ranked.set_index('symbol').loc[atr.head(10).symbol].reset_index(),
        }
        for policy, selected in selections.items():
            selected = selected.copy()
            selected['policy'] = policy
            selected['selection_rank'] = np.arange(1, len(selected) + 1)
            selected['pool_count'] = len(group)
            selected['eligible_count'] = len(intersection) if policy == POLICIES[1] else len(group)
            parts.append(selected)
    return pd.concat(parts, ignore_index=True)


def daily_metrics(selected):
    rows = []
    for (day, policy), group in selected.groupby(['date', 'policy'], sort=True):
        valid = group.dropna(subset=OUTCOMES)
        valid = valid[np.isfinite(valid.future_return)]
        returns = valid.future_return
        values = dict(selected=len(group), evaluated=len(valid), missing=len(group) - len(valid),
            coverage=len(valid) / len(group), pool_count=int(group.pool_count.iloc[0]),
            eligible_count=int(group.eligible_count.iloc[0]),
            full_top10=len(group) == 10, mean_abs_return=None, median_abs_return=None,
            mean_signed_return=None, positive_rate=None, negative_rate=None,
            zero_rate=None, abs_ge20_rate=None, abs_ge50_rate=None,
            gain_ge20_rate=None, loss_ge20_rate=None, gain_ge50_rate=None,
            loss_ge50_rate=None, precision=None, d1_rate=None, d10_rate=None)
        if len(valid):
            values.update(mean_abs_return=float(returns.abs().mean()),
                median_abs_return=float(returns.abs().median()), mean_signed_return=float(returns.mean()),
                positive_rate=float(returns.gt(0).mean()), negative_rate=float(returns.lt(0).mean()),
                zero_rate=float(returns.eq(0).mean()), abs_ge20_rate=float(returns.abs().ge(.20).mean()),
                abs_ge50_rate=float(returns.abs().ge(.50).mean()),
                gain_ge20_rate=float(returns.ge(.20).mean()), loss_ge20_rate=float(returns.le(-.20).mean()),
                gain_ge50_rate=float(returns.ge(.50).mean()), loss_ge50_rate=float(returns.le(-.50).mean()),
                precision=float(valid.oracle_extreme10.mean()), d1_rate=float(valid.oracle_decile.eq(1).mean()),
                d10_rate=float(valid.oracle_decile.eq(10).mean()))
        rows.append(dict(date=day, policy=policy, **values))
    return pd.DataFrame(rows)


def summarize(selected, daily):
    result = []
    scope = pd.to_datetime(selected.date)
    periods = [('ALL', scope.min(), scope.max())]
    periods += [(str(year), pd.Timestamp(year=year, month=1, day=1),
                 pd.Timestamp(year=year, month=12, day=31)) for year in sorted(scope.dt.year.unique())]
    periods += [('2026Q1', pd.Timestamp('2026-01-01'), pd.Timestamp('2026-03-31'))]
    for name, start, end in periods:
        part = selected[selected.date.between(start, end)]
        days = daily[daily.date.between(start, end)]
        for policy, group in part.groupby('policy'):
            d = days[days.policy.eq(policy)]
            valid = group.dropna(subset=OUTCOMES)
            valid = valid[np.isfinite(valid.future_return)]
            r = valid.future_return
            count = valid.symbol.value_counts()
            result.append(dict(period=name, policy=policy, days=len(d),
                start=str(d.date.min().date()), end=str(d.date.max().date()),
                selected=len(group), evaluated=len(valid), missing=len(group)-len(valid),
                full_top10_days=int(d.full_top10.sum()), coverage=len(valid)/len(group),
                mean_selected=float(d.selected.mean()), unique_symbols=int(group.symbol.nunique()),
                mean_daily_precision=float(d.precision.mean()),
                mean_daily_abs_return=float(d.mean_abs_return.mean()),
                mean_daily_median_abs_return=float(d.median_abs_return.mean()),
                median_abs_return_pooled=float(r.abs().median()) if len(r) else None,
                mean_daily_positive_rate=float(d.positive_rate.mean()),
                mean_daily_negative_rate=float(d.negative_rate.mean()),
                mean_daily_abs_ge20_rate=float(d.abs_ge20_rate.mean()),
                mean_daily_abs_ge50_rate=float(d.abs_ge50_rate.mean()),
                mean_daily_gain_ge50_rate=float(d.gain_ge50_rate.mean()),
                mean_daily_loss_ge50_rate=float(d.loss_ge50_rate.mean()),
                mean_daily_d1_rate=float(d.d1_rate.mean()), mean_daily_d10_rate=float(d.d10_rate.mean()),
                top10_symbols_evaluated_share=float(count.head(10).sum()/len(valid)) if len(valid) else None,
                top_symbols=[dict(symbol=str(symbol), count=int(n)) for symbol,n in count.head(10).items()]))
    return result


def paired_deltas(old, new):
    paired = old.merge(new, on=['date', 'policy'], how='outer', suffixes=('_legacy', '_corrected'),
                       indicator=True, validate='one_to_one')
    if not paired._merge.eq('both').all():
        raise ValueError('Unpaired selection dates')
    records = []
    metrics = ('precision', 'mean_abs_return', 'median_abs_return', 'positive_rate',
               'abs_ge20_rate', 'abs_ge50_rate')
    for policy, group in paired.groupby('policy'):
        group = group.sort_values('date')
        for metric in metrics:
            diff = (group[f'{metric}_corrected'] - group[f'{metric}_legacy']).dropna().to_numpy()
            if not len(diff):
                continue
            rng = np.random.default_rng(42)
            block = min(20, len(diff))
            boot = []
            for _ in range(1000):
                start = rng.integers(0, len(diff)-block+1, size=int(np.ceil(len(diff)/block)))
                indices = (start[:,None] + np.arange(block)).ravel()[:len(diff)]
                boot.append(float(diff[indices].mean()))
            records.append(dict(policy=policy, metric=metric, days=len(diff),
                delta_times100=float(diff.mean()*100),
                descriptive_block20_ci_times100=[float(x*100) for x in np.quantile(boot,[.025,.975])]))
    return records


def load_pair(root, source):
    protocol = read_json(root / 'protocol.json')
    report = read_json(root / 'report.json')
    if 'COMPLETED' not in report['status']:
        raise ValueError('Completed prediction experiment required')
    frames, hashes = {}, {}
    for arm in ('legacy', 'corrected'):
        paths = ([root/arm/start/'predictions.parquet' for start in protocol['expected_fold_starts']]
                 if source == 'historical_oof' else [root/f'{arm}-predictions.parquet'])
        hashes[arm] = [{'path':str(path), 'sha256':digest(path)} for path in paths]
        if source == 'historical_oof':
            for item in hashes[arm]:
                path = Path(item['path'])
                if read_json(path.parent/'done.json')['predictions.parquet'] != item['sha256']:
                    raise ValueError('OOF prediction checksum mismatch')
        frames[arm] = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
        validate_predictions(frames[arm])
        frames[arm] = frames[arm].sort_values(['date','symbol']).reset_index(drop=True)
    untreated = ['date','symbol','atr20_pct','fold_start',*OUTCOMES]
    if not frames['legacy'][untreated].equals(frames['corrected'][untreated]):
        raise ValueError('Unpaired outcomes or observable pools')
    return frames, hashes


def run(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    protocol = dict(historical=str(args.historical), external=str(args.external),
        input_protocol_hashes=[digest(root/'protocol.json') for root in (args.historical,args.external)],
        code_sha256=digest(__file__), top_n=10, gate_pct=.20, atr='atr20_pct',
        thresholds=[.20,.50], sorting='Oracle score descending, symbol ascending for ties',
        training=False, sql=False, realized_sort=False, pnl=False)
    path = output/'protocol.json'
    if path.exists() and read_json(path) != protocol:
        raise ValueError('Output protocol mismatch')
    atomic_json(path,protocol)
    final = dict(status='COMPLETED_OFFLINE_TOP10_AUDIT',sources={}, limitations=[
        '2026 already examined, not virgin holdout', 'One seed and frozen formulas',
        'Current universe and prices, not exhaustive PIT or independent price certification',
        'Repeated overlapping H20 observations, block intervals descriptive',
        'Mean signed returns are not portfolio PnL; no costs, sizing or stops',
        'H20 is measured from signal-day close, not entry at J+1'])
    for source, root in [('historical_oof',args.historical),('external_frozen',args.external)]:
        atomic_json(output/'progress.json',dict(status='RUNNING',phase='load_predictions',source=source))
        frames, hashes = load_pair(root,source)
        summaries, daily, selections = {}, {}, {}
        for arm, frame in frames.items():
            LOG.info('Selecting %s %s rows=%d',source,arm,len(frame))
            selected=select_top10(frame)
            daily[arm]=daily_metrics(selected)
            summaries[arm]=summarize(selected,daily[arm])
            selected.to_parquet(output/f'{source}-{arm}-selected.parquet',index=False)
            daily[arm].to_parquet(output/f'{source}-{arm}-daily.parquet',index=False)
            selections[arm]=selected
        overlap=[]
        for policy in POLICIES:
            old=selections['legacy'][selections['legacy'].policy.eq(policy)]
            new=selections['corrected'][selections['corrected'].policy.eq(policy)]
            shared=old[['date','symbol']].merge(new[['date','symbol']],on=['date','symbol'])
            overlap.append(dict(policy=policy,shared=len(shared),selected_legacy=len(old),
                selected_corrected=len(new),fraction_legacy_retained=len(shared)/len(old)))
        extremes={}
        for arm in ('legacy','corrected'):
            extremes[arm]={}
            for policy,group in selections[arm].groupby('policy'):
                # Post-selection examples only, explicitly not used as candidates.
                example=group.assign(abs_return=group.future_return.abs()).nlargest(15,'abs_return')
                extremes[arm][policy]=json.loads(example[['date','symbol','score','oracle_rank',
                    'selection_rank','future_return']].to_json(orient='records',date_format='iso'))
        final['sources'][source]=dict(input_hashes=hashes,summaries=summaries,
            paired_deltas=paired_deltas(daily['legacy'],daily['corrected']),
            selection_overlap=overlap,largest_post_selection_examples=extremes)
    atomic_json(output/'report.json',final)
    atomic_json(output/'progress.json',dict(status='COMPLETED',phase='top10_audit'))
    LOG.info('TOP10 audit complete: %s',output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--historical',type=Path,required=True)
    parser.add_argument('--external',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        run(args)
    except Exception as exc:
        if args.output.is_dir():
            atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,
                error=str(exc) if isinstance(exc,(ValueError,KeyError)) else 'See stderr'))
        raise


if __name__=='__main__':
    main()
