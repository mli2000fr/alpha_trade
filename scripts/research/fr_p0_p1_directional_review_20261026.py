"""Offline review: use current dated provider scope, not warmup alias union.

Keep the initial frozen snapshot intact. Its September warmup includes PERR
before its migration; October decisions use ALPER only. No new SQL or provider.
"""
from pathlib import Path
import json,gzip,hashlib
from collections import Counter
from datetime import date
import pandas as pd
import yaml

from scripts.research import fr_p0_p1_directional_audit_20261026 as audit

PARENT=audit.OUTPUT
ROOT=PARENT.parent/'20261026-v1-reviewed'


def scoped_labels(labels,symbols):
    if labels.duplicated(['symbol','entry_day','horizon']).any():raise ValueError('Duplicate sample')
    result=labels[labels.symbol.isin(symbols)].copy()
    available=pd.to_datetime(result.feature_available_at,utc=True)
    if not available.lt(pd.to_datetime(result.entry_at,utc=True)).all():raise ValueError('Future observation leaked')
    if result[result.horizon.eq(20)].status.ne('NOT_MATURE').any():raise ValueError('Unexpected H20 maturity at fixed cutoff')
    return result


def main():
    seal=audit.read(PARENT/'seal.json')
    for name,expected in seal['files'].items():
        if audit.digest(PARENT/name)!=expected:raise ValueError('Frozen input changed')
    cfg=yaml.safe_load((PARENT/'batch_fr.yaml').read_text(encoding='utf-8-sig'))['fr_daily_bars_sync']
    report=audit.read(PARENT/'report.json');day=date.fromisoformat(report['latest_closed_session'])
    from service.fr.eodhd_daily_15b import symbol_windows
    windows=symbol_windows(PARENT/'identities.jsonl.gz',day,day,cfg['provider_symbol_migrations'],
        excluded_symbols=cfg['excluded_symbols'])
    labels=pd.read_parquet(PARENT/'protected-path-diagnostics.parquet')
    scoped=scoped_labels(labels,set(windows));stats=audit.statistics(scoped)
    with gzip.open(PARENT/'identities.jsonl.gz','rt',encoding='utf-8') as stream:
        reference=[json.loads(line) for line in stream if line.strip()]
    by_symbol={r['provider_symbol']:r for r in reference}
    for migration in cfg['provider_symbol_migrations']:
        by_symbol[migration['new_symbol']]=by_symbol[migration['old_symbol']]
    isins={by_symbol[s]['isin'] for s in windows}
    public=audit.read(PARENT/'public-observations.json')
    docs=[r for r in public['dila'] if r['isin'] in isins]
    snapshot=public['amf'][-1]
    positions={isin:values for isin,values in snapshot['positions'].items() if isin in isins}
    report.update(universe_symbols=len(windows),diagnostic=stats,
        reviewed_at_utc=pd.Timestamp.now(tz='UTC'),source_snapshot=str(PARENT),
        scope_amendment='October decisions exclude old PERR warmup alias; use current dated ALPER. No bars/labels modified.',
        removed_aliases=sorted(set(labels.symbol)-set(windows)),
        scoped_AMF_current_isins_with_public_position=len(positions),
        scoped_DILA_unique_documents=len(docs),scoped_DILA_isins=len({r['isin'] for r in docs}),
        scoped_DILA_categories=dict(Counter(r['category'] for r in docs)),
        primary_H20_mature_labels=0,secondary_H5_H10_not_independent_validation=True)
    ROOT.mkdir(parents=True,exist_ok=False)
    scoped.to_parquet(ROOT/'protected-path-diagnostics.parquet',index=False)
    audit.write(ROOT/'report.json',report)
    audit.write(ROOT/'scope.json',dict(symbols=sorted(windows),isins=sorted(isins),
        excluded_aliases=report['removed_aliases'],source_config_sha256=audit.digest(PARENT/'batch_fr.yaml')))
    sources={str(PARENT/n):sha for n,sha in seal['files'].items()}
    sources.update({str(p):audit.digest(p) for p in [Path(__file__),Path(audit.__file__),
        Path('tests/test_fr_p0_p1_directional_review_20261026.py')]})
    audit.write(ROOT/'sources.json',sources)
    audit.write(ROOT/'seal.json',dict(at_utc=pd.Timestamp.now(tz='UTC'),
        files={p.name:audit.digest(p) for p in ROOT.iterdir() if p.is_file()}))
    print(json.dumps(dict(output=str(ROOT),symbols=len(windows),removed_aliases=report['removed_aliases'],
        AMF_isins=len(positions),DILA_documents=len(docs),DILA_isins=report['scoped_DILA_isins'],
        secondary={h:{k:v for k,v in d.items() if k!='features'} for h,d in stats.items()}),default=str))


if __name__=='__main__':main()
