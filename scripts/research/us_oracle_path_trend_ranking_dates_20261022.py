"""V2 reader amendment: normalize archived fold_start dates before concatenation."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import logging

import pandas as pd

from scripts.research import us_oracle_path_trend_ranking_20261022 as study

PARENT = study.ROOT
ROOT = Path('artifacts/research/us_oracle_path_trend_ranking/20261022-v2')
ORIGINAL_FREEZE_RECENT = study.freeze_recent


def normalize_recent(frame):
    result = frame.copy()
    result['fold_start'] = pd.to_datetime(result.fold_start).dt.normalize()
    return result


def freeze_recent(protocol):
    return normalize_recent(ORIGINAL_FREEZE_RECENT(protocol))


def freeze(output):
    if output.exists():
        raise FileExistsError('Fresh output required')
    p = study.read(PARENT/'protocol.json')
    study.verify(p['sources'])
    if (PARENT/'dataset.parquet').exists() or (PARENT/'report.json').exists():
        raise ValueError('Date amendment must precede first target/outcome calculation')
    p['preparation_parent'] = str(PARENT)
    p['date_reader_amendment'] = 'fold_start datetime.date -> pandas Timestamp; calendar dates unchanged; no target/rank/price change'
    p['amended_at_utc'] = datetime.now(timezone.utc).isoformat()
    for path in [PARENT/'protocol.json', Path(__file__),
                 Path('tests/test_us_oracle_path_trend_ranking_dates_20261022.py')]:
        p['sources'][str(path)] = study.digest(path)
    output.mkdir(parents=True)
    study.save(output/'protocol.json', p)
    return p


def run(output=ROOT):
    old_freeze, old_recent = study.freeze, study.freeze_recent
    study.freeze, study.freeze_recent = freeze, freeze_recent
    try:
        return study.run(output)
    finally:
        study.freeze, study.freeze_recent = old_freeze, old_recent


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args, **kwargs):
        raise RuntimeError('Network forbidden')
    requests.Session.request = forbidden
    result = run(args.output)
    print({k: result[k] for k in ('status', 'verdict', 'selected_before_confirmation', 'stable_features')})
