"""Reuse only proven identical 2025 cases; every corrected 2026 case starts fresh."""
import argparse
from pathlib import Path

import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import read
from scripts.research.us_oracle_barrier_exit_grid import PROFILES


def seed(source, inputs, output):
    protocol = read(source/'protocol.json')
    previous_inputs = Path(protocol['inputs'])
    verify_hashes(Path('.'),protocol['source_hashes'])
    for path in (previous_inputs,inputs):
        verify_hashes(path,read(path/'prepared.json')['files'])
    if digest(previous_inputs/'prepared.json') != protocol['prepared_sha256']:
        raise ValueError('Previous inputs changed')
    # Include the 2025 warm-up and the January 2026 exit tail, not just decision dates.
    for name in ('prices.parquet','scores.parquet','macro.parquet'):
        frames=[]
        for path in (previous_inputs,inputs):
            frame=pd.read_parquet(path/name)
            date_column='trade_date' if name=='macro.parquet' else 'date'
            frame=frame.loc[pd.to_datetime(frame[date_column]).le('2026-01-30')]
            keys=[date_column]+(['symbol'] if 'symbol' in frame else [])
            frames.append(frame.sort_values(keys).reset_index(drop=True))
        pd.testing.assert_frame_equal(*frames,check_exact=True)
    reused=[]
    for n in (10,20,50):
        for arm in ('OLD_TERMINAL_LONG','NEW_BARRIER_LONG'):
            for profile,tp,sl in PROFILES:
                key=f'2025-TOP{n}-{arm}-{profile}'
                path=source/key/'case-report.json'
                case=read(path)
                if case['status']!='COMPLETED' or case['tp_pct']!=tp or case['sl_pct']!=sl:
                    raise ValueError('2025 case not complete or wrong profile')
                for filename in ('trades.parquet','daily.parquet','report.json'):
                    if not (Path(case['output'])/filename).is_file():
                        raise ValueError('2025 immutable case outputs missing')
                target=output/key
                target.mkdir(parents=True,exist_ok=True)
                case.update(reused_identical_2025_inputs=True,reused_from=str(path),reused_case_sha256=digest(path))
                if (target/'case-report.json').exists() and read(target/'case-report.json')!=case:
                    raise ValueError('Never overwrite different existing case')
                atomic_json(target/'case-report.json',case)
                reused.append(dict(case=key,source_sha256=digest(path)))
    output.mkdir(parents=True,exist_ok=True)
    atomic_json(output/'reuse-2025.json',dict(status='IDENTICAL_2025_DECISION_WARMUP_AND_EXIT_INPUTS',
        source=str(source),inputs=str(inputs),cases=reused,case_count=len(reused),
        every_2026_case_replayed=True,previous_protocol_sha256=digest(source/'protocol.json')))
    print('Reused',len(reused),'proven identical 2025 cases; no 2026 results reused',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    seed(**vars(parser.parse_args()))
