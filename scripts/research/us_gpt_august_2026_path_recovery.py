"""Evaluation-only recovery of the SQL Decimal/float extrema timestamp bug.

Preserves the paid requests, replies, original sealed source and all thresholds.
No new API call, inference, model change, portfolio or production-table write.
"""
import argparse
from pathlib import Path

import pandas as pd

from scripts.research import us_gpt_august_2026_path_audit as original
from scripts.research.us_concentrated_historical_tapes import digest,verify_hashes
from scripts.research.oracle_path_confirmation import exclusive_run
from service.llm_directional.news_cache import atomic_json

ORIGINAL_MEASURE=original.measure_path


def measure_numeric(frame,window,registry,symbol,actions):
    # SQL DECIMAL becomes a Python Decimal in parquet. The original reducer
    # converted its extremum to float, then compared that float to Decimal rows;
    # non-binary-exact prices matched no row, producing NaT instead of a timestamp.
    # Use the SAME numeric representation as its existing OHLC quality checks.
    normalized=frame.copy()
    for field in ('open','high','low','close','volume'):
        normalized[field]=pd.to_numeric(normalized[field],errors='raise').astype(float)
    return ORIGINAL_MEASURE(normalized,window,registry,symbol,actions)


def recover(engine,output):
    root=Path(output);protocol=original.read(root/'protocol.json')
    verify_hashes(Path('.'),protocol['source_hashes']);verify_hashes(root,protocol['files'])
    analysis=original.read(root/'analysis.json')
    if analysis['status']!='SCORES_COMPLETED':raise ValueError('No recovery before all paid replies are archived')
    if digest(root/'scores.json')!=analysis['score_file_sha256']:raise ValueError('Scores changed')
    amendment=root/'evaluation-recovery-v1.json'
    value=dict(reason='SQL Decimal extrema compared to float: no matching timestamp, NaT',
        fix='Normalize OHLC and volume to float64 before unchanged reducer/quality checks',
        original_source_sha256=digest(Path(original.__file__)),recovery_source_sha256=digest(Path(__file__)),
        scores_sha256=digest(root/'scores.json'),analysis_sha256=digest(root/'analysis.json'),
        requests_sha256=digest(root/'requests.json'),protocol_sha256=digest(root/'protocol.json'),
        gpt_calls=0,thresholds_changed=False,paid_replies_changed=False,original_source_changed=False)
    if amendment.exists():
        if original.read(amendment)!=value:raise ValueError('Evaluation recovery amendment changed')
    else:
        atomic_json(amendment,value)
        atomic_json(root/'progress-before-evaluation-recovery.json',original.read(root/'progress.json'))
    original.measure_path=measure_numeric
    try:return original.evaluate(engine,root)
    finally:original.measure_path=ORIGINAL_MEASURE


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with exclusive_run(args.output):
            result=recover(engine,args.output)
            print(original.dumps(result))
    finally:engine.dispose()


if __name__=='__main__':main()
