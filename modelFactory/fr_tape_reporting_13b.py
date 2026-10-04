"""Prepare shared FR execution templates and frozen reporting tasks; no replay."""
import argparse
import json
from pathlib import Path
from service.fr.tape_reporting_13b import prepare


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frozen',type=Path,default=Path('artifacts/fr/research/validation_protocol_13a/frozen-20261004-v1'))
    args=parser.parse_args()
    report=prepare(args.output,args.frozen)
    print(json.dumps({'status':report['status'],'tasks':len(report['tasks']),'net_pnl':None}))


if __name__=='__main__':
    main()
