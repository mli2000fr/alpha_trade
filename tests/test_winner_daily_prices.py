"""A zero daily volume must not erase known protection prices for held lots."""
import pandas as pd
import pytest
from sqlalchemy import create_engine

from backtesting.winner_data import daily_bars


def test_zero_volume_retains_canonical_ohlc_without_synthesizing_liquidity(caplog):
    engine=create_engine('sqlite://')
    base=dict(symbol='TPB',date='2026-06-18',open=79.76,high=82.18,low=78.49,
              close=82.02,volume=0,is_filled=0,data_source='eodhd_eod',data_adjustment='split')
    rows=[base,dict(base,symbol='NEG',volume=-1),dict(base,symbol='NULL',volume=None),
          dict(base,symbol='BAD',low=90.),dict(base,symbol='FILLED',is_filled=1),
          dict(base,symbol='NOOPEN',open=None),dict(base,symbol='RAW',data_adjustment='raw')]
    pd.DataFrame(rows).to_sql('stock_bars_daily',engine,index=False)
    with engine.connect() as conn:
        result=daily_bars(conn,[r['symbol'] for r in rows],'2026-06-18','2026-06-18')
    assert result.symbol.tolist()==['TPB']
    assert result.iloc[0].open==79.76
    assert result.iloc[0].volume==0
    assert 'volume nul' in caplog.text and 'TPB' in caplog.text


@pytest.mark.usefixtures('isolated_winner_config')
def test_zero_volume_daily_fallback_protects_previously_held_position():
    from tests.test_winner_daily_protection import setup,set_day,buys
    from backtesting.simulator import BacktestEngine
    cfg,args,raw=setup(horizon_sessions=1)
    set_day(args,cfg.end_date,op=98.,high=100.,low=97.,close=99.)
    args['volume'].loc[pd.Timestamp(cfg.end_date),'AAA']=0.
    raw[cfg.end_date,'AAA']=raw[cfg.end_date,'AAA'].iloc[1:]
    result=BacktestEngine(cfg).run(**args)
    assert len(buys(result))==1
    trade=result.closed_trades_df.iloc[0]
    assert trade.exit_price==98. and trade.exit_reason=='HORIZON_OPEN'
    assert result.tracker_snapshot['winner_replay']['protection_resolution']['fallback_symbol_sessions']==1
