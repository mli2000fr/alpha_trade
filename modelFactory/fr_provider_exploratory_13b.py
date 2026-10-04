"""CLI for explicitly supplier-assumed FR research, not canonical backtesting."""
import argparse
import json
from pathlib import Path
from service.fr.provider_exploratory_13b import run

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config',type=Path,default=Path('config/research_fr/provider_exploratory_13b_v1.yaml'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    existed=args.output.exists()
    try:
        report=run(args.output,args.config)
    except Exception as exc:
        if not existed and args.output.exists() and not (args.output/'report.json').exists():
            (args.output/'failure.json').write_text(json.dumps({'status':'FAILED_EXPLORATORY',
                'error':str(exc),'economic_go_allowed':False,'serving_enabled':False},indent=2),encoding='utf-8')
        raise
    print(f'{report["status"]}: performance={report["completed_performance_cells"]}, blocked={report["blocked_cells"]}')

if __name__=='__main__':
    main()
