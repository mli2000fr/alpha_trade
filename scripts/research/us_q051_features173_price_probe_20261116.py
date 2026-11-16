"""Read-only local quote-basis investigation; never downloads or rewrites SQL."""
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from database.connection import get_sqlalchemy_engine

ROOT=Path('artifacts/research/us_q051_features173/20261116-v2')

if __name__=='__main__':
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    with engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        frame=pd.read_sql(text("SELECT symbol,date,open,high,low,close,volume,data_source,data_adjustment,is_filled "
            "FROM stock_bars_daily WHERE symbol='DD' AND date BETWEEN '2026-05-25' AND '2026-06-30' "
            "ORDER BY date,data_source,data_adjustment"),conn)
    frame.to_csv(ROOT/'DD-price-basis-sql.csv',index=False)
    print(frame[['date','open','close','data_source','data_adjustment']].to_string(index=False))
