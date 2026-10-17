"""Bounded FR Earnings Trends access proof; no SQL/Yahoo or subscription change."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from common.public_data_http import verified_session
from service.eodhd.clientEodhd import _do_request, _get_base_url, _get_token, _redact_sensitive_text
from service.eodhd.consensus_snapshot import parse
from service.eodhd.quota import get_default_tracker


def run(root):
    root.mkdir(parents=True,exist_ok=False)
    reports=[]
    with verified_session() as session:
        for symbol in ['OR.PA','SU.PA','BN.PA','AI.PA','AAPL.US']:
            try:
                payload=_do_request(endpoint='calendar/trends',url=_get_base_url()+'/calendar/trends',
                    params={'api_token':_get_token(),'fmt':'json','symbols':symbol},session=session,
                    tracker=get_default_tracker(),feature='fr_consensus_access_probe')
                observed=datetime.now(timezone.utc)
                with (root/(symbol+'.json')).open('x',encoding='utf-8') as stream:
                    json.dump(payload,stream,ensure_ascii=False,indent=2)
                rows=parse(payload,[symbol],observed,'fr-access-proof')[symbol]
                reports.append(dict(symbol=symbol,status='ACCESS_WITH_ROWS' if rows else 'EMPTY_COVERAGE',
                    rows=len(rows),fields=sorted({k for row in rows for k,v in row.items() if v is not None}),
                    available_at=observed.isoformat()))
            except Exception as exc:
                reports.append(dict(symbol=symbol,status='FAILED',error_type=type(exc).__name__,
                    error=_redact_sensitive_text(str(exc))[:400]))
    result=dict(status='COMPLETED_ACCESS_PROBE',reports=reports,sql_writes=False,yahoo_calls=0,
        historical_pit=False,subscription_changed=False)
    with (root/'report.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().output),ensure_ascii=False))
