"""Local READ ONLY source coverage audit; no download, training, trades or P&L."""
import argparse
from datetime import date, datetime, UTC
from pathlib import Path
import json

import pandas as pd
from sqlalchemy import text

from common.market_calendar import get_market_calendar
from common.universe_files import load_universe_file_symbols
from common.winner_pyramiding import regular_bounds
from backtesting.historical_sec_capitalization import HistoricalSecCapitalizations


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dates',default='2021-07-02,2022-06-30,2023-06-30,2024-06-28,2025-06-27,2026-09-30')
    p.add_argument('--universe',default='universe-file:config/univers_batch/univers_filtred_tradable.txt')
    p.add_argument('--signals-file',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    symbols=load_universe_file_symbols(args.universe)
    from database.connection import get_sqlalchemy_engine
    from common.market_cap import load_market_cap_config
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    signals=pd.read_csv(args.signals_file) if args.signals_file else pd.DataFrame()
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    summary=[]
    with engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION READ ONLY'))
        provider=HistoricalSecCapitalizations(conn,symbols,max_age_days=load_market_cap_config().max_age_days)
        for value in args.dates.split(','):
            day=date.fromisoformat(value)
            cutoff=regular_bounds(calendar.next_session(day))[0]
            rows=provider.reconstruct(day,cutoff,symbols)
            covered={r['symbol'] for r in rows}
            cohort=signals.loc[signals.trade_date.eq(str(day))].symbol.tolist() if not signals.empty else []
            receipt=provider.receipts[-1]
            item=dict(day=str(day),requested=len(symbols),reconstructed=len(rows),
                coverage_pct=100*len(rows)/len(symbols),oracle_cohort=len(cohort),
                oracle_covered=sum(s in covered for s in cohort),
                oracle_missing={s:receipt['rejected_symbols'].get(s) for s in cohort if s not in covered},
                rejection_counts=receipt['rejection_counts'])
            summary.append(item)
            (args.output/(str(day)+'.json')).write_text(json.dumps(dict(summary=item,receipt=receipt,rows=rows),
                ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding='utf-8')
            (args.output/'progress.json').write_text(json.dumps(dict(status='RUNNING',completed=len(summary),
                total=len(args.dates.split(',')),last=item),ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(item,ensure_ascii=False),flush=True)
    report=dict(status='COMPLETED_SOURCE_AUDIT',created_at=datetime.now(UTC).isoformat(),
        source_manifest=provider.manifest,source_rejections=provider.rejections,dates=summary,
        provider_downloads=0,sql_writes=0,economic_backtest=False,
        limitations=['Current CIK/name mapping, reviewed identity breaks only; not a complete historical master',
            'Current SEC companyfacts extracts of filings; not archived API vintages',
            'Last regular raw SIP 5m close is a price proxy, not the official closing auction',
            'Known splits since the share measurement are rejected; CA completeness is not certified'])
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    (args.output/'progress.json').write_text(json.dumps(dict(status=report['status'],completed=len(summary))),encoding='utf-8')


if __name__=='__main__':main()
