"""Read-only verification of the first real option backfill insertions."""
import json
from pathlib import Path

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


if __name__=='__main__':
    root=Path('artifacts/research/alpaca_options_history/backfill-20240120-20261009-v1')
    state=json.loads((root/'progress.json').read_text(encoding='utf-8'))
    engine=get_sqlalchemy_engine()
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        rows=conn.execute(text('''SELECT underlying_symbol,timeframe,COUNT(*) AS rows_stored,
            MIN(bar_timestamp) AS first_bar, MAX(bar_timestamp) AS last_bar,
            MIN(observed_at) AS first_observed, MIN(available_at) AS first_available
            FROM alpha_trade.stock_option_bars_delayed
            WHERE underlying_symbol IN ('A','AA') AND timeframe='1Day'
            AND bar_timestamp >= '2024-01-20' AND bar_timestamp < '2024-02-01'
            AND run_id=:run GROUP BY underlying_symbol,timeframe'''),{'run':state['run_id']}).mappings().all()
        conn.rollback()
    result={'run_id':state['run_id'],'rows':[dict(x) for x in rows],
        'total_rows_verified':sum(x['rows_stored'] for x in rows),'expected_insertions':state['persisted']}
    if result['total_rows_verified']!=state['persisted']:
        raise RuntimeError('Insert verification mismatch')
    (root/'first_insert_verification.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print(json.dumps(result,default=str),flush=True)
