"""Bounded Perrier repair and Lhyfe provider check; FR research staging only."""
from datetime import UTC, date, datetime
import argparse
import hashlib
import json
import os
from pathlib import Path

import yaml

from service.fr.eodhd_daily_15b import atomic, collect, symbol_windows
from service.fr.eodhd_backfill import _fetch
from service.fr.publish_daily_bars_staging import run as publish

ROOT=Path(__file__).resolve().parents[2]


def run(output, *, write=False):
    output=output.resolve()
    if not output.is_relative_to(ROOT/'artifacts/fr') or output.exists():
        raise ValueError('Nouveau dossier artifacts/fr requis')
    cfg=yaml.safe_load((ROOT/'batch_fr.yaml').read_text(encoding='utf-8'))['fr_daily_bars_sync']
    identities=ROOT/cfg['identities_file']
    start,end=date(2026,10,9),date(2026,10,16)
    windows=symbol_windows(identities,start,end,cfg.get('provider_symbol_migrations'))
    if 'ALPER.PA' not in windows or 'PERR.PA' in windows or 'LHYFE.PA' not in windows:
        raise ValueError('Configuration migration différente du correctif borné')
    result=dict(market_code='FR_EQ',database='alpha_trade_fr',window=[str(start),str(end)],
        selected_symbols=['ALPER.PA'], canonical_writes=False,serving_enabled=False,
        sql_writes=write,reference_sha256=hashlib.sha256(identities.read_bytes()).hexdigest(),
        provider_symbol_migrations=cfg['provider_symbol_migrations'])
    if not write:
        return {**result,'status':'PREVIEW_NO_NETWORK_NO_SQL'}
    output.mkdir(parents=True,exist_ok=False)
    token=os.environ['EODHD_API_TOKEN']
    # Keep bounded provider responses; never archive token/signed URL.
    checks={}
    for isin in ('FR0000061459','FR0014009YQ1'):
        checks[isin]=dict(observed_at=datetime.now(UTC).isoformat(),
            rows=_fetch('search/'+isin,token,{'limit':'15'},pace=.5))
    rows=_fetch('search/ALPER',token,{'limit':'5'},pace=.5)
    checks['ALPER.PA']=dict(observed_at=datetime.now(UTC).isoformat(),rows=rows)
    atomic(output/'provider_checks.json',checks)
    matches=[r for r in rows if r.get('Code')=='ALPER' and r.get('Exchange')=='PA'
             and r.get('Currency')=='EUR' and r.get('Country')=='France'
             and 'perrier' in str(r.get('Name','')).lower()]
    if len(matches)!=1:
        raise ValueError('Identité fournisseur ALPER absente/ambiguë ; aucune collecte ni SQL')
    try:
        rows=_fetch('eod/ALHYF.PA',token,{'from':str(start),'to':str(end),'period':'d'},pace=.5)
        checks['ALHYF.PA']=dict(observed_at=datetime.now(UTC).isoformat(),rows=rows)
    except RuntimeError as exc:
        checks['ALHYF.PA']=dict(observed_at=datetime.now(UTC).isoformat(),error=str(exc))
    atomic(output/'provider_checks.json',checks)
    collected=dict(received_count=0,persisted_count=0,failed_count=0,warning_count=0)
    collect(cfg,collected,root=ROOT/'artifacts/fr/operations/eodhd_daily',identities=identities,
            today=end,selected_symbols=['ALPER.PA'])
    staged=publish(start=start,end=end,write=True,identities=identities,
        selected_symbols=['ALPER.PA'],symbol_migrations=cfg['provider_symbol_migrations'],
        excluded_symbols=cfg.get('excluded_symbols'),
        output=output/'staging_report.json')
    result.update(status='PARTIAL_REPAIR_LHYFE_NOT_RESOLVED',collection=collected,
        staging=staged,remaining_blocker='LHYFE.PA / ALHYF.PA: aucune substitution de place autorisée',
        finished_at=datetime.now(UTC).isoformat(),historical_batch_statuses_rewritten=False)
    atomic(output/'report.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--write',action='store_true',help='API bornée et staging SQL FR, aucun canonique')
    args=parser.parse_args()
    result=run(args.output,write=args.write)
    print(json.dumps({'status':result['status'],'sql_writes':result['sql_writes'],
        'new_staging_rows':result.get('staging',{}).get('new_staging_rows'),
        'output':str(args.output)},ensure_ascii=False))


if __name__=='__main__':
    main()
