"""Isolated annual B29 SHORT study. Never imported by PAPER/live execution.

Reuse frozen causal annual Oracle scores and original B feature origins. Train
SHORT heads on past-only own-stock labels. All output stays in this campaign.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research import us_q051_feature_groups_20261116 as base
from scripts.research.us_q051_b_early_sl_20261116 import fit_model
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT = Path('artifacts/research/us_q051_b_short/20261118-v1')
END = pd.Timestamp('2026-10-01')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def prepare():
    if (ROOT/'protocol.json').exists():
        return read(ROOT/'protocol.json')
    ROOT.mkdir(parents=True, exist_ok=True)
    original = read(base.ROOT/'protocol.json')
    cols = original['features']['B']
    if len(cols) != 29:
        raise ValueError('Expected frozen B29 feature definition')
    sources = {str(base.ROOT/'protocol.json'): digest(base.ROOT/'protocol.json')}
    tasks = original['tasks']
    for task in tasks:
        for name in [task['source'], *task['future']]:
            if name not in sources:
                actual = digest(Path(name))
                if actual != original['sources'][name]:
                    raise ValueError('Changed annual price archive: ' + name)
                sources[name] = actual
    for year in range(2021, 2027):
        for name in ['pool.parquet', 'oracle.parquet']:
            file = base.ROOT/'years'/str(year)/name
            sources[str(file)] = digest(file)
        benchmark = Path(original['models'][str(year)]['benchmark'])
        sources[str(benchmark)] = digest(benchmark)
    from scripts.research.us_q051_global_rank_h10_20261115 import FEATURE_2026
    data_protocol = read(base.ORIGINAL/'protocol.json')
    for year in range(2021, 2027):
        name = Path(data_protocol['models'][str(year+1)]['benchmark']) if year < 2026 else FEATURE_2026/'directional/benchmark.parquet'
        sources[str(name)] = digest(name)
    for name in [Path(__file__), Path(base.__file__), Path('modelFactory/oracle_path/directional.py'),
                 Path('modelFactory/features.py'), Path('modelFactory/factor_features.py')]:
        sources[str(name)] = digest(name)
    data = dict(status='FROZEN_BEFORE_FITS', start='2021-01-01', end=str(END.date()), initial_equity=4000.,
        models=original['models'], tasks=tasks, sources=sources, features=cols,
        selection='Fixed annual TOP179 Oracle -> TOP10 SHORT, probability>.50, calibration AUC>=.50; no refill',
        target='Native SHORT net profitable after SL5/open11 and8bps per leg, before borrow/dividends',
        learner=dict(algorithm='LightGBM120/depth3/leaves7 + Platt', min_fit=756, min_calibration=126,
            fit_class_minimum=40, calibration_class_minimum=15),
        chronology='For signal yearY fit beforeY-1, calibrateY-1; labels fully available before each boundary',
        execution=dict(side='SHORT_ONLY', entry='J+1 daily open, no confirmation', stop=.05, horizon=10,
            exit='open11', take_profit=None, trailing=None, initial_fraction=1., risk_per_trade=.0125,
            max_weight=.20, max_positions=20, max_gross=1., margin_capacity=2., min_notional=50.,
            cost_reserve_per_leg=.0025, fee_per_leg=.0008, assumed_annual_borrow=.03,
            no_B4=True, no_regime=True, no_vol_budget=True, no_factors=True, no_sector_caps=True,
            no_correlation=True, no_anti_SL=True),
        mode='Isolated research daily OHLC replay with existing SHORT ledger; native Winner LONG engine unchanged',
        borrow_qualification='Assumed historical availability and3%annual fee; no observed locates/recalls',
        price_basis='Same repaired frozen daily matrices as B reference; source data quality reserves retained',
        drawdown='Daily close and separate simultaneous-high stress bound, never called exact intradayDD',
        independent_holdout=False, provider_calls=0, LLM_calls=0, SQL_writes=0, orders=0,
        production_changes=False, created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json', data)
    atomic_json(ROOT/'progress.json', dict(status='PREPARED', completed=0, total=len(tasks)))
    return data


def worker(key):
    import joblib
    from modelFactory.oracle_path import directional as d
    from modelFactory.oracle_path.directional_metrics import predict, classification_metrics
    from modelFactory.oracle.build_labels import nyse_sessions
    from common.config_loader import replay_market_registry
    from scripts.research.us_q051_global_rank_h10_20261115 import FEATURE_2026
    plan = read(ROOT/'protocol.json')
    task = next(t for t in plan['tasks'] if t['key'] == key)
    out = ROOT/'jobs'/key
    out.mkdir(parents=True, exist_ok=True)
    if (out/'done.json').exists():
        for name, expected in read(out/'done.json')['outputs'].items():
            if digest(out/name) != expected:
                raise ValueError('Changed completed SHORT output')
        return
    try:
        for name in [task['source'], *task['future'], str(Path(__file__))]:
            if digest(Path(name)) != plan['sources'][name]:
                raise ValueError('Changed frozen input: ' + name)
        year = task['year'];item = plan['models'][str(year)]
        end = min(END, pd.Timestamp(year, 12, 31))
        pieces = [pd.read_parquet(task['source'])]
        for name in task['future']:
            f = pd.read_parquet(name)
            pieces.append(f[f.date.gt(item['training_end']) & f.date.le(end)])
        bars = base.repair_bars(pd.concat(pieces, ignore_index=True))
        bars = bars[bars.symbol.isin(task['symbols']) & bars.date.le(end)]
        bench = pd.read_parquet(item['benchmark'])
        original = read(base.ORIGINAL/'protocol.json')
        nextfile = Path(original['models'][str(year+1)]['benchmark']) if year < 2026 else FEATURE_2026/'directional/benchmark.parquet'
        newer = pd.read_parquet(nextfile)
        bench = pd.concat([bench, newer[newer.date.gt(bench.date.max())]], ignore_index=True)
        if bench.date.duplicated().any():
            raise ValueError('Duplicate benchmark dates')
        pool = pd.read_parquet(base.ROOT/'years'/str(year)/'pool.parquet')
        # Freeze the same explicit security discontinuities used by the annual Oracle.
        source_root = Path(task['source']).parents[2]
        protocol = read(source_root/'protocol.json')
        from modelFactory.oracle.security_continuity import SecurityDiscontinuity
        registry = {}
        for symbol, events in protocol.get('security_discontinuities', {}).items():
            registry[symbol] = [SecurityDiscontinuity(**{
                **e, 'last_predecessor_date': pd.Timestamp(e['last_predecessor_date']),
                'first_successor_date': pd.Timestamp(e['first_successor_date'])}) for e in events]
        predictions = [];records = [];skipped = [];labels = []
        with replay_market_registry(base.shared.restore_registry(base.shared.ROOT)), patch.object(requests.Session, 'request', base.no_http):
            calendar = nyse_sessions(pd.Timestamp(item['training_start']).date(), end.date())
            for number, (symbol, g) in enumerate(bars.groupby('symbol')):
                atomic_json(out/'progress.json', dict(status='FITTING_SHORT', symbol=symbol,
                    completed=number, total=len(task['symbols'])))
                features = base.common_panel(g, bench, calendar)
                targets = d.labels(g, calendar, d.Settings(horizon_sessions=10), registry.get(symbol, ()))
                panel = features.merge(targets, on='date', how='left', validate='one_to_one')
                wanted = pool[pool.symbol.eq(symbol)][['date', 'symbol']].merge(features,
                    on=['date', 'symbol'], validate='one_to_one')
                for model_year, requested in wanted.groupby(wanted.date.dt.year):
                    fit, cal = d.split(panel, int(model_year), 'short')
                    qualified = (len(fit) >= 756 and len(cal) >= 126
                        and fit.short.value_counts().reindex([0., 1.], fill_value=0).min() >= 40
                        and cal.short.value_counts().reindex([0., 1.], fill_value=0).min() >= 15)
                    if not qualified:
                        skipped.append(dict(symbol=symbol, model_year=int(model_year), reason='INSUFFICIENT_PAST_ROWS_OR_CLASSES',
                            fit_rows=len(fit), calibration_rows=len(cal)))
                        continue
                    weights, metric = fit_model(fit, cal, plan['features'], 'short', item['seed'])
                    if weights is None:
                        skipped.append(dict(symbol=symbol, model_year=int(model_year), **metric))
                        continue
                    available = cal.available.max()
                    if not (fit.available.lt(pd.Timestamp(model_year-1, 1, 1)).all()
                            and cal.available.lt(pd.Timestamp(model_year, 1, 1)).all()
                            and requested.date.gt(available).all()):
                        raise ValueError('Future model/label in SHORT fitting')
                    import hashlib
                    name = hashlib.sha256(symbol.encode()).hexdigest()[:16] + f'-short-{model_year}.joblib'
                    file = out/'models'/name;file.parent.mkdir(exist_ok=True)
                    joblib.dump(weights, file, compress=3);checksum = digest(file)
                    records.append(dict(symbol=symbol, model_year=int(model_year), file=str(file), sha256=checksum,
                        fit_rows=len(fit), calibration_rows=len(cal), fit_start=str(fit.date.min().date()),
                        fit_end=str(fit.date.max().date()), fit_available_max=str(fit.available.max().date()),
                        calibration_start=str(cal.date.min().date()), calibration_end=str(cal.date.max().date()),
                        available=str(available.date()), calibration=metric, features=plan['features']))
                    p = requested[['date', 'symbol']].copy()
                    p['short_probability'] = predict(weights, requested);p['short_model_sha256'] = checksum
                    p['short_auc'] = metric['auc'];p['short_available'] = available
                    predictions.append(p)
                labels.append(panel[panel.date.isin(wanted.date)][['date', 'symbol', 'available', 'short']])
        empty = pd.DataFrame(columns=['date', 'symbol', 'short_probability', 'short_model_sha256', 'short_auc', 'short_available'])
        data = pd.concat(predictions, ignore_index=True) if predictions else empty
        data.to_parquet(out/'probabilities.parquet', index=False)
        pd.concat(labels, ignore_index=True).to_parquet(out/'labels.parquet', index=False)
        atomic_json(out/'models.json', dict(models=records, skipped=skipped))
        atomic_json(out/'done.json', dict(status='COMPLETED', models=len(records),
            outputs={name: digest(out/name) for name in ['probabilities.parquet', 'labels.parquet', 'models.json']}))
        atomic_json(out/'progress.json', dict(status='COMPLETED', models=len(records), skipped=len(skipped)))
    except BaseException as exc:
        atomic_json(out/'progress.json', dict(status='FAILED', error=repr(exc)))
        raise


def rank_short(oracle, probabilities):
    a = oracle[['date', 'symbol', 'proba_extreme']].copy()
    a['date'] = pd.to_datetime(a.date)
    if a.duplicated(['date', 'symbol']).any() or not a.proba_extreme.between(0, 1).all():
        raise ValueError('Invalid frozen Oracle scores')
    a = a.sort_values(['date', 'proba_extreme', 'symbol'], ascending=[True, False, True])
    a['oracle_rank'] = a.groupby('date').cumcount() + 1
    a = a.merge(probabilities, on=['date', 'symbol'], how='left', validate='one_to_one')
    known = a.short_probability.notna()
    if ((known & ~a.short_probability.between(0, 1)).any()
            or (known & pd.to_datetime(a.short_available).ge(a.date)).any()):
        raise ValueError('Invalid/future SHORT probabilities')
    pool = a[a.oracle_rank.le(179) & known].sort_values(
        ['date', 'short_probability', 'oracle_rank', 'symbol'], ascending=[True, False, True, True])
    ranks = pool[['date', 'symbol']].assign(short_rank=pool.groupby('date').cumcount() + 1)
    a = a.merge(ranks, on=['date', 'symbol'], how='left', validate='one_to_one')
    a['selected_before_threshold'] = a.short_rank.le(10)
    a['selected'] = a.selected_before_threshold & a.short_probability.gt(.5) & a.short_auc.ge(.5)
    a['side'] = 'short'
    a['rank'] = a.short_rank.where(a.selected)
    return a


def assemble():
    plan = read(ROOT/'protocol.json');signals = [];classifications = []
    for year in range(2021, 2027):
        parts = [];labels = []
        for task in [t for t in plan['tasks'] if t['year'] == year]:
            folder = ROOT/'jobs'/task['key'];done = read(folder/'done.json')
            for name, checksum in done['outputs'].items():
                if digest(folder/name) != checksum:
                    raise ValueError('Changed SHORT model/prediction')
            parts.append(pd.read_parquet(folder/'probabilities.parquet'))
            labels.append(pd.read_parquet(folder/'labels.parquet'))
        probabilities = pd.concat(parts, ignore_index=True)
        oracle = pd.read_parquet(base.ROOT/'years'/str(year)/'oracle.parquet')
        ranked = rank_short(oracle, probabilities)
        out = ROOT/'years'/str(year);out.mkdir(parents=True, exist_ok=True)
        ranked.to_parquet(out/'rankings.parquet', index=False)
        chosen = ranked[ranked.selected].copy();chosen['entry_year'] = year
        chosen['oracle_batch_id'] = plan['models'][str(year)]['oracle_batch']
        signals.append(chosen)
        from modelFactory.oracle_path.directional_metrics import classification_metrics
        sample = ranked[ranked.oracle_rank.le(179)].merge(pd.concat(labels, ignore_index=True),
            on=['date', 'symbol'], how='left', validate='one_to_one')
        sample = sample[sample.short.notna() & sample.short_probability.notna()
            & pd.to_datetime(sample.available).le(min(END, pd.Timestamp(year, 12, 31)))]
        classifications.append(dict(year=year, **classification_metrics(sample.short, sample.short_probability)))
    pd.concat(signals, ignore_index=True).to_parquet(ROOT/'signals.parquet', index=False)
    pd.DataFrame(classifications).to_csv(ROOT/'classification.csv', index=False)


def run(limit=4):
    plan = prepare();waiting = [t['key'] for t in plan['tasks'] if not (ROOT/'jobs'/t['key']/'done.json').exists()]
    total = len(plan['tasks']);active = []
    try:
        while waiting or active:
            while waiting and len(active) < limit:
                key = waiting.pop(0);logs = ROOT/'logs';logs.mkdir(exist_ok=True)
                stdout = (logs/(key+'.out.log')).open('ab');stderr = (logs/(key+'.err.log')).open('ab')
                process = subprocess.Popen([sys.executable, '-X', 'utf8', '-u', '-m', __spec__.name,
                    '--phase', 'worker', '--key', key], stdout=stdout, stderr=stderr,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                active.append((key, process, stdout, stderr))
            for item in active[:]:
                key, process, stdout, stderr = item
                if process.poll() is None:
                    continue
                stdout.close();stderr.close();active.remove(item)
                if process.returncode:
                    raise RuntimeError('SHORT worker failed: ' + key)
            atomic_json(ROOT/'progress.json', dict(status='TRAINING_ANNUAL_SHORT',
                completed=total-len(waiting)-len(active), total=total, active=[x[0] for x in active],
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if active:
                time.sleep(1)
        assemble()
        atomic_json(ROOT/'progress.json', dict(status='READY_FOR_ISOLATED_REPLAY', completed=total, total=total))
    except BaseException as exc:
        atomic_json(ROOT/'progress.json', dict(status='FAILED', error=repr(exc)))
        raise
    finally:
        for key, process, stdout, stderr in active:
            if process.poll() is None:
                process.terminate();process.wait()
            stdout.close();stderr.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('--phase', choices=['prepare', 'worker', 'all', 'assemble'], required=True)
    parser.add_argument('--key');parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.phase == 'prepare':prepare()
    elif args.phase == 'worker':worker(args.key)
    elif args.phase == 'assemble':assemble()
    else:run(args.workers)
