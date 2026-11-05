"""SELECT-only corporate-action inventory for raw-price research qualification."""
import json
from pathlib import Path
import pandas as pd
from sqlalchemy import text,bindparam
from database.connection import get_sqlalchemy_engine
from scripts.research.us_selected_universe_intraday_inputs_20261104 import OUT
from scripts.research.us_selected_universe_oracle_20261104 import END,save,digest


def main():
    path=OUT/'inputs/corporate-actions.parquet'
    if path.exists():raise FileExistsError(path)
    names=json.loads((OUT/'inputs/manifest.json').read_text())['symbols']
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    with engine.connect() as conn:
        conn.execute(text('SET TRANSACTION READ ONLY'))
        q=text('SELECT symbol,ca_type,ex_date,split_from,split_to,provider FROM corporate_actions_events '
            'WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end').bindparams(bindparam('symbols',expanding=True))
        a=pd.read_sql(q,conn,params=dict(symbols=names,start='2024-01-01',end=str(END.date())),parse_dates=['ex_date'])
        conn.rollback()
    engine.dispose()
    a=a.drop_duplicates().sort_values(['symbol','ex_date','provider'])
    a.to_parquet(path,index=False)
    save(OUT/'inputs/corporate-actions-receipt.json',dict(rows=len(a),file_sha256=digest(path),sql_writes=False,script_sha256=digest(__file__)))
    print(a[['symbol','ca_type','ex_date','split_from','split_to']].to_string(index=False))


if __name__=='__main__':main()
