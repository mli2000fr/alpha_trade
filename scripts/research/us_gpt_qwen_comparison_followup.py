"""Refresh comparison receipts until both already-launched jobs are terminal.

No API calls, retries, inference, training, SQL server writes or trading.
"""
from datetime import datetime, timezone
import argparse
from pathlib import Path
import time

from scripts.research.us_gpt_winner_ab import ROOT,SOURCE,compare,read
from scripts.research.us_concentrated_historical_tapes import atomic_json


def run(root,local,timeout_hours=24):
    started=time.monotonic()
    while True:
        if (root/'analyses.sqlite3').exists() and (local/'analyses.sqlite3').exists():
            comparison=compare(root)
        else:
            comparison=dict(status='WAITING_FOR_CACHES')
        cloud_report=read(root/'report.json') if (root/'report.json').exists() else None
        local_report=read(local/'campaign/report.json') if (local/'campaign/report.json').exists() else None
        terminal=cloud_report is not None and local_report is not None
        status='FINISHED_COMPARISON_READ_ONLY' if terminal else 'WAITING_FOR_RUNNING_JOBS'
        if time.monotonic()-started>timeout_hours*3600:
            status='MONITOR_TIMEOUT_NO_JOB_RESTART'
        result=dict(status=status,updated_at_utc=datetime.now(timezone.utc).isoformat(),
            comparison=comparison,gpt_terminal_status=cloud_report.get('status') if cloud_report else None,
            qwen_terminal_status=local_report.get('status') if local_report else None,
            gpt_replay_available=(root/'replay/report.json').exists(),
            qwen_replay_available=(local/'replay/report.json').exists(),
            api_calls=0,automatic_retry=False,broker_calls=0)
        atomic_json(root/'comparison-followup.json',result)
        if terminal or status=='MONITOR_TIMEOUT_NO_JOB_RESTART':return result
        time.sleep(45)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=ROOT)
    a=p.parse_args();run(a.output_dir,SOURCE)


if __name__=='__main__':main()
