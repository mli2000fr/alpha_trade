"""Read-only SEC/Finnhub coverage on local US fundamentals; no provider calls.

An archived observation is not a newly collected record. SEC shares coverage
is reported separately from availability of a positive, non-filled close.
This diagnostic never changes the batch threshold or canonical tables.
"""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path

from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from service.forward_pit.batch import _symbols, _market_cap_covered_symbols


def summarize(scope, sec, finnhub, priced):
    scope = set(scope)
    shares = scope & set(sec)
    fh = scope & set(finnhub)
    computable_sec = shares & set(priced)
    observed = shares | fh
    computable = computable_sec | fh
    return dict(symbols=len(scope), sec_shares=len(shares), finnhub=len(fh),
                finnhub_incremental_over_sec=len(fh - shares),
                covered_observations=len(observed),
                observation_coverage_ratio=len(observed)/len(scope) if scope else None,
                sec_with_reference_close=len(computable_sec),
                sec_missing_reference_close=len(shares - computable_sec),
                potentially_computable_market_cap=len(computable),
                potentially_computable_ratio=len(computable)/len(scope) if scope else None,
                missing_observations=sorted(scope-observed),
                missing_computable=sorted(scope-computable))


def audit(engine, scopes, *, as_of, price_date, max_age_days=365):
    if engine.url.database != 'alpha_trade':
        raise ValueError('Audit US alpha_trade uniquement')
    if price_date > as_of:
        raise ValueError('Le cours de référence ne peut être postérieur au cutoff')
    if max_age_days < 0:
        raise ValueError('Âge maximal positif ou nul requis')
    all_symbols = sorted(set().union(*scopes.values()))
    sec = _market_cap_covered_symbols(engine, all_symbols, as_of, max_age_days, ('SEC_EDGAR',))
    fh = _market_cap_covered_symbols(engine, all_symbols, as_of, max_age_days, ('FINNHUB',))
    query = text('''SELECT DISTINCT symbol FROM stock_bars_daily
        WHERE symbol IN :symbols AND `date`=:price_date AND `close`>0 AND is_filled=0
        ''').bindparams(bindparam('symbols', expanding=True))
    with engine.connect() as conn:
        priced = set(conn.execute(query, dict(symbols=all_symbols, price_date=price_date)).scalars())
    return dict(observed_at=datetime.now(UTC).isoformat(), available_date_cutoff=as_of.isoformat(),
                future_availability_cutoff=as_of>datetime.now(UTC).date(),
                reference_price_date=price_date.isoformat(), max_age_days=max_age_days,
                providers=['SEC_EDGAR','FINNHUB'], sql_writes=False, provider_calls=0,
                scopes={name:summarize(scope,sec,fh,priced) for name,scope in scopes.items()},
                limitations=['Existing database observations only; not the coverage of a new collection.',
                  'SEC shares multiplied by a reference close are computable, not a validated corporate-action-adjusted valuation.',
                  'Price date may precede availability cutoff; no future opening or executable price claimed.',
                  'Finnhub snapshots and sector classification are not retroactive PIT history.',
                  'Batch coverage threshold and tradability policy unchanged.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of',type=date.fromisoformat,required=True)
    parser.add_argument('--price-date',type=date.fromisoformat,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-age-days',type=int,default=365)
    args=parser.parse_args()
    paths={'collection':Path('config/univers_batch/stock_bars_daily.txt'),
           'tradable_reference':Path('config/univers_batch/univers_filtred_tradable.txt')}
    if args.output.exists():
        raise ValueError('Dossier neuf requis')
    scopes={name:set(_symbols({'symbols_file':str(path)})) for name,path in paths.items()}
    result=audit(get_sqlalchemy_engine(),scopes,as_of=args.as_of,price_date=args.price_date,max_age_days=args.max_age_days)
    result['universe_hashes']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths.values()}
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({name:{k:v for k,v in row.items() if not isinstance(v,list)} for name,row in result['scopes'].items()},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
