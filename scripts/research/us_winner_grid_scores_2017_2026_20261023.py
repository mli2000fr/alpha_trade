"""Freeze label-free causal scores for the accepted grid window; no PnL or SQL writes."""
from datetime import date, datetime, timezone
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
from sqlalchemy import text

from common.market_calendar import get_market_calendar
from common.universe_files import load_universe_file_symbols
from modelFactory.oracle_path.predict import load_contract, select_fold
from scripts.research.us_winner_bottom_rank_filter_20261022 import digest, save_new

START = date(2017, 6, 2)
END = date(2026, 9, 30)
ROOT = Path('artifacts/research/us_winner_grid_scores_2017_2026/20261023-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
BATCHES = {
    **{year: 'model-factory-20261014113215-437ed1' for year in range(2017, 2025)},
    2025: 'model-factory-20261014113226-102eca',
    2026: 'model-factory-20261014113232-bc35a7',
}


def qualify(frame, folds, *, source, profile_hash):
    """Keep prediction fields only; never rank using future target/excursions."""
    f = frame.copy()
    f['date'] = pd.to_datetime(f.date).dt.normalize()
    if f.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate prediction key')
    scores = pd.to_numeric(f.score, errors='coerce')
    if not np.isfinite(scores).all() or not scores.between(0, 1).all():
        raise ValueError('Invalid Oracle amplitude score')
    known = {}
    for day, g in f.groupby('date'):
        selected = select_fold(day, folds)
        if not g.fold_start.map(lambda x: str(x)[:10]).eq(selected).all():
            raise ValueError(f'Non-canonical causal fold at {day.date()}')
        fold = folds[selected]
        m = fold['metrics']
        available = max(pd.Timestamp(m[k]) for k in ('train_available_max', 'val_available_max'))
        if available >= day:
            raise ValueError('Same-day/future model availability')
        if source == 'SQL':
            for key, expected in [('model_sha256', fold['model_sha256']),
                                  ('feature_profile_sha256', profile_hash),
                                  ('target_name', 'oracle_path_extreme20'), ('target_horizon', 20)]:
                if not g[key].eq(expected).all():
                    raise ValueError('Invalid stored lineage: ' + key)
            if (not pd.to_datetime(g.lineage_fold_start).eq(pd.Timestamp(selected)).all()
                    or not pd.to_datetime(g.model_available_date).eq(available).all()):
                raise ValueError('Stored fold availability mismatch')
        known[day] = dict(model_available_date=available, model_sha256=fold['model_sha256'])
    out = f[['date', 'symbol', 'score', 'fold_start']].copy()
    out['fold_start'] = pd.to_datetime(out.fold_start).dt.normalize()
    out['model_available_date'] = out.date.map(lambda d: known[d]['model_available_date'])
    out['model_sha256'] = out.date.map(lambda d: known[d]['model_sha256'])
    out['feature_profile_sha256'] = profile_hash
    out['score_source'] = source
    return out


def freeze_top10(scores, expected_days):
    """No replacement for missing signal dates, no ranking on outcome coverage."""
    if scores.duplicated(['date', 'symbol']).any():
        raise ValueError('Overlapping score populations')
    ordered = scores.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True]).copy()
    ordered['rank'] = ordered.groupby('date').cumcount() + 1
    counts = ordered.groupby('date').size()
    missing = [str(d) for d in expected_days if counts.get(pd.Timestamp(d), 0) < 20]
    top = ordered[ordered['rank'].le(10)].copy()
    return top, missing


def run(root=ROOT):
    from database.connection import get_sqlalchemy_engine
    if root.exists():
        raise FileExistsError('Fresh immutable score snapshot required')
    root.mkdir(parents=True)
    calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    expected = [s.session_date for s in calendar.sessions(START, END) if s.is_open]
    universe = set(load_universe_file_symbols('universe-file:' + UNIVERSE.as_posix()))
    inputs = {str(UNIVERSE): digest(UNIVERSE), str(Path(__file__)): digest(__file__)}
    models = {}; reports = []; parts = []
    for batch in sorted(set(BATCHES.values())):
        folder, protocol, profile, folds = load_contract('artifacts/models', batch)
        path = folder / 'oof_predictions.parquet'
        for file in [path, folder/'protocol.json', folder/'report.json', folder/'feature_profile.json']:
            inputs[str(file)] = digest(file)
        for fold in folds.values():
            for file in [Path(fold['model_file']), Path(fold['model_file']).with_name('done.json')]:
                inputs[str(file)] = digest(file)
        columns = ['date', 'symbol', 'proba_path_extreme', 'fold_start']
        f = pd.read_parquet(path, columns=columns).rename(columns={'proba_path_extreme': 'score'})
        f['date'] = pd.to_datetime(f.date)
        years = [y for y, b in BATCHES.items() if b == batch]
        f = f[f.date.dt.year.isin(years) & f.date.between(pd.Timestamp(START), pd.Timestamp(END))
              & f.symbol.isin(universe)].copy()
        profile_hash = digest(folder/'feature_profile.json')
        q = qualify(f, folds, source='OOF', profile_hash=profile_hash)
        q['batch_id'] = batch; parts.append(q)
        models[batch] = (folds, profile_hash)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with engine.connect() as conn, conn.begin():
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=30000'))
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
                raise ValueError('US database only')
            for year in range(2017, 2027):
                batch = BATCHES[year]
                local = pd.concat([f[f.date.dt.year.eq(year)] for f in parts], ignore_index=True)
                local_days = set(local.date.dt.date)
                missing_days = [d for d in expected if d.year == year and d not in local_days]
                if not missing_days:
                    reports.append(dict(year=year, SQL_rows=0, missing_OOF_dates=0)); continue
                # Fetch only missing days; never splice a partial SQL day into an OOF ranking.
                from sqlalchemy import bindparam
                query = text('SELECT p.prediction_date AS date,p.symbol,p.proba_extreme AS score,p.fold_start, '
                    'l.fold_start AS lineage_fold_start,l.model_available_date,l.model_sha256, '
                    'l.feature_profile_sha256,l.target_name,l.target_horizon '
                    'FROM oracle_extreme_predictions p LEFT JOIN oracle_path_prediction_lineage l '
                    'ON p.prediction_date=l.prediction_date AND p.symbol=l.symbol AND p.batch_id=l.batch_id '
                    'WHERE p.batch_id=:batch AND p.prediction_date IN :days').bindparams(bindparam('days', expanding=True))
                raw = pd.read_sql(query, conn, params=dict(batch=batch, days=missing_days))
                raw = raw[raw.symbol.isin(universe)].copy()
                if not raw.empty:
                    folds, ph = models[batch]
                    q = qualify(raw, folds, source='SQL', profile_hash=ph)
                    q['batch_id'] = batch; parts.append(q)
                reports.append(dict(year=year, SQL_rows=len(raw), missing_OOF_dates=len(missing_days)))
    finally:
        engine.dispose()
    scores = pd.concat(parts, ignore_index=True)
    top, missing = freeze_top10(scores, expected)
    top.to_parquet(root/'causal-top10.parquet', index=False)
    coverage = scores.groupby(['date', 'batch_id', 'score_source']).size().rename('scored_symbols').reset_index()
    coverage.to_parquet(root/'score-date-coverage.parquet', index=False)
    years = [dict(year=int(y), dates=int(g.date.nunique()), top10_rows=len(g), symbols=int(g.symbol.nunique()),
                  first=str(g.date.min().date()), last=str(g.date.max().date())) for y, g in top.groupby(top.date.dt.year)]
    report = dict(status='SCORES_AVAILABLE_INTRADAY_QUALIFICATION_PENDING' if not missing else 'BLOCKED_MISSING_SCORE_DATES',
        observed_at_utc=datetime.now(timezone.utc).isoformat(), accepted_start=str(START), accepted_end=str(END),
        first_entry_earliest='2017-06-05', signal_available_after_close=True,
        expected_signal_sessions=len(expected), missing_score_dates=missing, by_year=years, SQL_inventory=reports,
        model_allocation=BATCHES, inputs=inputs,
        files={name:digest(root/name) for name in ['causal-top10.parquet', 'score-date-coverage.parquet']},
        labels_read=False, SQL_writes=False, provider_calls=0, training=False, economic_grid_started=False,
        top3=None, population_completeness_certified=False,
        limitations=['Current static universe and current model archives; survivorship/non-PIT universe bias.',
            'OOF test dates preferred; stored SQL used only for entirely absent OOF dates, with causal lineage.',
            'At least 20 scores per date is a minimum gate, not proof of a fully scored eligible population.',
            'Intraday, daily, corporate actions and exact grid protocol still require qualification.',
            '2017 and 2026 partial; already observed years are not an independent holdout.'])
    save_new(root/'report.json', report)
    print(json.dumps({k:report[k] for k in ['status','expected_signal_sessions','missing_score_dates','by_year']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT)
    run(parser.parse_args().output)
