"""Independent read-only recomputation of sealed IEX/SIP evidence and decision counts."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


def review(root):
    load = lambda path: json.loads(path.read_text(encoding='utf-8'))
    plan, seal, report = [load(root/name) for name in ('plan.json', 'seal.json', 'report.json')]
    for name, sha in plan['source_hashes'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha:
            raise ValueError('Frozen source changed: '+name)
    for name, sha in seal['files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != sha:
            raise ValueError('Artifact hash mismatch: '+name)
    if report['status'] != 'COMPLETED' or report['errors']:
        raise ValueError('Cannot certify complete evidence from partial audit')
    rows = []
    for case in plan['cases']:
        row = dict(case)
        current, opening = pd.Timestamp(case['at']), pd.Timestamp(case['opening'])
        for feed in ('iex', 'sip'):
            sig = json.dumps([case['symbol'], case['at'], feed], separators=(',', ':'))
            path = root/'raw'/(hashlib.sha256(sig.encode()).hexdigest()+'.json')
            evidence = load(path)
            assert evidence['http_status'] == 200
            assert evidence['symbol'] == case['symbol'] and evidence['at'] == case['at'] and evidence['feed'] == feed
            params = evidence['params']
            assert params['start'] == case['opening'] and params['end'] == case['at']
            assert params['feed'] == feed and params['asof'] == '-' and params['sort'] == 'desc' and params['limit'] == 1
            payload = evidence['payload']
            quotes = payload.get('quotes') or []
            assert len(quotes) <= 1  # Deliberate latest-asof, not a full quote history.
            reasons = {}
            if not quotes:
                reasons = {scenario: 'MISSING' for scenario in plan['scenarios']}
            else:
                q = quotes[0]
                bid, ask = float(q['bp']), float(q['ap'])
                timestamp = pd.Timestamp(q['t'])
                age = (current-timestamp).total_seconds()
                row[feed+'_age_seconds'] = age
                valid = (all(math.isfinite(v) and v > 0 for v in (bid, ask)) and ask > bid
                         and timestamp >= opening and age >= 0)
                spread = (ask-bid)*20000/(bid+ask) if valid else None
                row[feed+'_spread_bps'] = spread
                for scenario, (maximum_age, require_sizes) in plan['scenarios'].items():
                    sizes_valid = all(math.isfinite(float(q[k])) and float(q[k]) > 0 for k in ('bs', 'as'))
                    reasons[scenario] = ('INVALID' if not valid else 'STALE' if age > maximum_age else
                        'INVALID_SIZE' if require_sizes and not sizes_valid else
                        'WIDE' if spread > plan['max_spread_bps'] else 'PASS')
            row.update({feed+'_'+key: value for key, value in reasons.items()})
        rows.append(row)
    recomputed = pd.DataFrame(rows)
    stored = pd.read_csv(root/'pairs.csv')
    for key in ('symbol', 'at', 'oracle_rank', 'quote_day', 'slot'):
        assert stored[key].tolist() == recomputed[key].tolist(), key
    checked = 0
    for feed in ('iex', 'sip'):
        for scenario in plan['scenarios']:
            column = feed+'_'+scenario
            assert stored[column].tolist() == recomputed[column].tolist(), column
            checked += len(rows)
        for metric in ('spread_bps', 'age_seconds'):
            column = feed+'_'+metric
            for a, b in zip(stored[column], recomputed[column]):
                # Provider dates have ns precision; the audit's UTC datetime
                # deliberately stores microseconds (maximum 1 us truncation).
                tolerance = 2e-6 if metric == 'age_seconds' else 1e-8
                assert (pd.isna(a) and pd.isna(b)) or math.isclose(a, b, abs_tol=tolerance, rel_tol=1e-10), column
                checked += 1
    for n in (10, 20, 50):
        sub = recomputed[recomputed.oracle_rank <= n]
        for scenario in plan['scenarios']:
            i, s = sub['iex_'+scenario], sub['sip_'+scenario]
            expected = report['groups']['TOP'+str(n)]['scenarios'][scenario]
            assert expected['both_pass'] == int((i.eq('PASS') & s.eq('PASS')).sum())
            assert expected['iex_refuses_sip_passes'] == int((~i.eq('PASS') & s.eq('PASS')).sum())
            assert expected['iex_passes_sip_refuses'] == int((i.eq('PASS') & ~s.eq('PASS')).sum())
            assert expected['both_refuse'] == int((~i.eq('PASS') & ~s.eq('PASS')).sum())
            assert expected['iex_status_counts'] == i.value_counts().to_dict()
            assert expected['sip_status_counts'] == s.value_counts().to_dict()
    result = dict(status='VERIFIED', pairs=len(rows), raw_responses=2*len(rows),
                  cell_checks=checked, same_assistant_independent_recomputation=True,
                  human_independent_review=False, checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  reviewer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  source_files_verified=len(plan['source_hashes']))
    (root/'independent_recomputation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    review(parser.parse_args().output)
