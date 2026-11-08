"""Dedicated guarded entry point; only simulation modules may be dispatched."""
import argparse
from pathlib import Path
import runpy
import sys
import json

from backtesting.isolation import ReadOnlyReplay


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--module',choices=['backtesting','backtesting.winner_campaign_replay'],required=True)
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    arguments=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
    if args.module=='backtesting' and arguments[:1]!=['run']:
        parser.error('Only the simulation command run may execute without an exclusive lock')
    if '--output-dir' not in arguments:
        parser.error('An explicit run-local --output-dir is required')
    output=Path(arguments[arguments.index('--output-dir')+1]).resolve()
    workspace=Path(args.workspace).resolve()
    if not output.is_relative_to(workspace) or output==workspace:
        parser.error('Output must be inside the dedicated workspace')
    print('Simulation isolée : SQL partagé en lecture seule ; rapports et caches propres au run ; aucun ordre broker.',flush=True)
    try:
        with ReadOnlyReplay(workspace).install():
            original=sys.argv
            sys.argv=[args.module,*arguments]
            try:runpy.run_module(args.module,run_name='__main__',alter_sys=True)
            finally:sys.argv=original
    finally:
        receipt_path=workspace/'isolation.json'
        report_path=output/'report.json'
        if receipt_path.is_file() and report_path.is_file():
            receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
            report=json.loads(report_path.read_text(encoding='utf-8'))
            report.setdefault('run_metadata',{})['isolation']=receipt
            if receipt['status']=='FAILED':
                report['status']='FAILED_ISOLATION'
                report.setdefault('diagnostics',{})['status']='FAILED_ISOLATION'
            report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
