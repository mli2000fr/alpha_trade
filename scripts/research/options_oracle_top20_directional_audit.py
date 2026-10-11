"""Conditional extension of the frozen options audit; SELECT only, no API."""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import text
from database.connection import get_sqlalchemy_engine
from scripts.research.us_prospective_directional_collection_audit import query
from scripts.research.options_downloaded_directional_audit import ROOT, OUTPUT, metrics
from service.alpaca.options_history_backfill import atomic_json

BATCH = 'model-factory-20261003082853-e98332'
DEST = OUTPUT.parent/'directional-oracle-top20-feb-mar-2024-20261011-v1'


def select_top20(scores, universe_count):
    scores = scores.copy()
    scores['day'] = pd.to_datetime(scores.day)
    scores['fold_start'] = pd.to_datetime(scores.fold_start)
    if scores.duplicated(['day', 'symbol']).any():
        raise ValueError('Duplicate Oracle score')
    if not (scores.fold_start.eq(pd.Timestamp('2024-01-08')) & scores.fold_start.lt(scores.day)).all():
        raise ValueError('Unexpected/future fold lineage')
    scores['proba_extreme'] = pd.to_numeric(scores.proba_extreme, errors='coerce')
    if not (np.isfinite(scores.proba_extreme) & scores.proba_extreme.between(0, 1)).all():
        raise ValueError('Invalid Oracle probabilities')
    selections, coverage = [], []
    for day, part in scores.groupby('day'):
        qualified = len(part) >= .9*universe_count
        count = int(np.ceil(.2*len(part)))
        coverage.append(dict(day=str(day.date()), scored=len(part), selected=count, qualified=qualified))
        if qualified:
            selections.append(part.sort_values(['proba_extreme', 'symbol'], ascending=[False, True],
                                               kind='stable').head(count))
    return pd.concat(selections, ignore_index=True) if selections else scores.iloc[:0], coverage


def run():
    DEST.mkdir(parents=True, exist_ok=False)
    plan = json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
    protocol = dict(batch_id=BATCH, oracle_horizon=20, top_pct=.2,
        labels='Original full-universe signed-return deciles; NOT reranked inside Oracle',
        ranking='Oracle probability descending, symbol ascending; BEFORE options availability filter',
        options_source=str(OUTPUT), sql_writes=False, api_calls=0, training=False,
        lineage='Expected champion 2024-01-08; documented max train label 2023-07-07, validation 2024-01-05. Table-only scores may have been regenerated; not immutable original OOF archive.',
        status='EXPLORATORY_NOT_CERTIFIED_PIT',
        limitations='Inherits source audit limitations, missing 2024-02-02 options, two months and overlapping labels. No economic or live promotion.')
    atomic_json(DEST/'protocol.json', protocol)
    engine = get_sqlalchemy_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            scores = pd.DataFrame(query(conn, """SELECT prediction_date AS day,symbol,proba_extreme,fold_start
                FROM oracle_extreme_predictions WHERE batch_id=:batch AND symbol IN :symbols
                AND prediction_date BETWEEN '2024-02-01' AND '2024-03-31'""",
                plan['symbols'], batch=BATCH))
            conn.rollback()
    finally:
        engine.dispose()
    scores.to_parquet(DEST/'oracle_scores.parquet', index=False)
    selected, coverage = select_top20(scores, len(plan['symbols']))
    selected.to_parquet(DEST/'oracle_top20.parquet', index=False)
    result = dict(protocol=protocol, coverage=coverage, horizons={},
                  scores_sha256=hashlib.sha256((DEST/'oracle_scores.parquet').read_bytes()).hexdigest())
    for horizon in (3, 5, 10, 20):
        source = OUTPUT/f'pairs_h{horizon}.parquet'
        frame = pd.read_parquet(source)
        joined = frame.merge(selected, on=['day', 'symbol'], validate='one_to_one')
        joined.to_parquet(DEST/f'pairs_h{horizon}.parquet', index=False)
        block_days = sorted(frame.entry_date.unique())[::horizon]
        result['horizons'][str(horizon)] = dict(
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            standalone_same_dates=metrics(frame), oracle_top20=metrics(joined),
            monthly={month:metrics(part) for month,part in joined.groupby(joined.day.dt.strftime('%Y-%m'))},
            fixed_nonoverlapping_cohort=metrics(joined[joined.entry_date.isin(block_days)]))
        print(horizon, result['horizons'][str(horizon)]['oracle_top20'], flush=True)
    atomic_json(DEST/'report.json', result)


if __name__ == '__main__':
    run()
