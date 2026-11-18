"""Availability metadata only: SELECT catalog/ranges, never market downloads."""
import json
import re
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from scripts.research.us_q051_protection_features_data_20261118 import ROOT


def main():
    load_dotenv(dotenv_path=Path('F:/projets/.env'),override=False)
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade');database=engine.url.database
    words=('analyst','consensus','option','news','macro','earnings','sec_filing','fundamental','borrow','sentiment','short_interest','vix','market_regime')
    with engine.connect() as conn:
        tables=[dict(r) for r in conn.execute(text('SELECT TABLE_NAME,TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_SCHEMA=:schema'),dict(schema=database)).mappings()
            if any(w in r['TABLE_NAME'].lower() for w in words)]
        columns=[dict(r) for r in conn.execute(text('SELECT TABLE_NAME,COLUMN_NAME,DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=:schema'),dict(schema=database)).mappings()]
        indexes=[dict(r) for r in conn.execute(text('SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=:schema AND SEQ_IN_INDEX=1'),dict(schema=database)).mappings()]
        for table in tables:
            names={c['COLUMN_NAME']:c['DATA_TYPE'] for c in columns if c['TABLE_NAME']==table['TABLE_NAME']};table['columns']=list(names)
            table['temporal_columns']={k:v for k,v in names.items() if v in ('date','datetime','timestamp')}
            preferred=['trade_date','snapshot_date','as_of_date','prediction_date','published_at','publication_date','filing_date','acceptance_datetime','earnings_date','bar_date','date','observed_at','created_at']
            datecol=next((c for c in preferred if c in table['temporal_columns']),None)
            indexed=any(i['TABLE_NAME']==table['TABLE_NAME'] and i['COLUMN_NAME']==datecol for i in indexes)
            if datecol and re.fullmatch(r'[A-Za-z0-9_]+',table['TABLE_NAME']) and (int(table['TABLE_ROWS'] or 0)<5000000 or indexed):
                row=conn.execute(text('SELECT MIN(`'+datecol+'`) AS first_date,MAX(`'+datecol+'`) AS last_date FROM `'+table['TABLE_NAME']+'`')).mappings().one()
                table.update(date_column=datecol,first_date=str(row['first_date']),last_date=str(row['last_date']))
        macro=[dict(r) for r in conn.execute(text('SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN :start AND :end ORDER BY trade_date'),dict(start='2020-01-01',end='2026-10-01')).mappings()]
        fundamental=[dict(r) for r in conn.execute(text('SELECT source,COUNT(*) AS rows_count,COUNT(DISTINCT symbol) AS symbols,MIN(trade_date) AS first_date,MAX(trade_date) AS last_date,MIN(available_date) AS first_available,MIN(fetched_at) AS first_fetch,SUM(available_date IS NULL) AS missing_availability FROM stock_fundamentals_daily GROUP BY source')).mappings()]
        fields=['market_cap','pe_ratio','pb_ratio','gross_margin','net_margin','debt_to_equity','current_ratio','roe','roa','eps','shares_outstanding','revenue','eps_growth_yoy','revenue_growth_yoy']
        sec=[dict(r) for r in conn.execute(text('SELECT COUNT(*) AS rows_count,COUNT(DISTINCT symbol) AS symbols,'+
            ','.join('SUM(`'+c+'` IS NOT NULL) AS `'+c+'`' for c in fields)+
            " FROM stock_fundamentals_daily WHERE source='SEC_EDGAR' AND available_date BETWEEN '2020-01-01' AND '2026-10-01'")).mappings()]
        try:
            consensus=[dict(r) for r in conn.execute(text('SELECT /*+ MAX_EXECUTION_TIME(10000) */ MIN(snapshot_date) AS first_snapshot,MAX(snapshot_date) AS last_snapshot,MIN(observed_at) AS first_observed,MAX(observed_at) AS last_observed,SUM(historical_pit_qualified=1) AS qualified_rows FROM stock_analyst_consensus_eodhd_history')).mappings()]
        except Exception as exc:consensus=[dict(range_error=type(exc).__name__)]
    result=dict(status='READ_ONLY_INVENTORY',database=database,tables=tables,SQL_writes=0,provider_calls=0,used_in_rules=False,
        qualification='Ranges do not prove PIT availability, symbol coverage, stable meaning or predictive value; large tables not fully scanned')
    (ROOT/'sql-feature-availability.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    (ROOT/'macro-retrospective-rows.json').write_text(json.dumps(macro,default=str),encoding='utf-8')
    (ROOT/'fundamental-availability.json').write_text(json.dumps(fundamental,indent=2,default=str),encoding='utf-8')
    (ROOT/'sec-fundamental-field-availability.json').write_text(json.dumps(sec,indent=2,default=str),encoding='utf-8')
    (ROOT/'consensus-availability.json').write_text(json.dumps(consensus,indent=2,default=str),encoding='utf-8')
    print(json.dumps(dict(status=result['status'],tables=len(tables))))


if __name__=='__main__':main()
