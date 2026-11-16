"""Finish only this already-running research campaign; no launches or retries."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time

from scripts.research.us_concentrated_historical_tapes import atomic_json

ROOT=Path('artifacts/research/us_q051_features173/20261116-v3-sip')
CASES=['SIMPLE','VOL20_REGIME','CONTROL_SIMPLE','CONTROL_VOL20_REGIME']


def main():
    started=time.monotonic()
    try:
        while True:
            states={name:json.loads((ROOT/'cases'/name/'progress.json').read_text(encoding='utf-8')) for name in CASES}
            atomic_json(ROOT/'finish-progress.json',dict(status='WAITING_EXISTING_REPLAYS',cases=states,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if any(s.get('status')=='FAILED' for s in states.values()):raise RuntimeError('Existing replay failed; no automatic retry')
            if all(s.get('status')=='COMPLETED_EXPLORATORY' for s in states.values()):break
            if time.monotonic()-started>5400:raise TimeoutError('Research monitoring limit; no replay restarted')
            time.sleep(10)
        for phase in ['compare','publish']:
            atomic_json(ROOT/'finish-progress.json',dict(status=phase.upper(),updated_at_utc=datetime.now(timezone.utc).isoformat()))
            subprocess.run([sys.executable,'-X','utf8','-u','-m',
                'scripts.research.us_q051_features173_finalize_20261116','--phase',phase],check=True)
        atomic_json(ROOT/'finish-progress.json',dict(status='COMPLETED_EXPLORATORY_AND_PUBLISHED',
            qualification=json.loads((ROOT/'validation.json').read_text(encoding='utf-8'))['status'],
            updated_at_utc=datetime.now(timezone.utc).isoformat()))
    except BaseException as exc:
        atomic_json(ROOT/'finish-progress.json',dict(status='FINALIZATION_FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
