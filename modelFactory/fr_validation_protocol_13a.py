"""Sprint 13-A FR: freeze comparison protocol and check existing evidence."""
import argparse
import json
from pathlib import Path

from service.fr.validation_protocol_13a import run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scope',type=Path,default=Path('artifacts/fr/research/exploitable_scope_12e/audit-20261004-v2'))
    parser.add_argument('--preflight',type=Path,default=Path('artifacts/fr/research/economic_references_11a/preflight-20261004-v2'))
    args=parser.parse_args()
    report=run(args.output,scope=args.scope,preflight=args.preflight)
    print(json.dumps({k:report[k] for k in ['status','candidate_paths','qualified_common_paths','net_pnl']}))


if __name__=='__main__':
    main()
