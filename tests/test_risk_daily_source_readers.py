"""Risk prices, ATR/ADV and correlation must select a source before row limits."""
import pandas as pd
import pytest
from sqlalchemy import create_engine

from common import daily_bar_sources
from risk_management.db_io import RiskRepository


@pytest.mark.parametrize('preference', ['eodhd','alpaca_sip'])
def test_risk_readers_use_same_whole_rows_before_rolling_limit(monkeypatch, preference):
    dates=pd.bdate_range('2026-09-01',periods=35)
    frame=pd.DataFrame([dict(symbol='ABC',date=day.strftime('%Y-%m-%d'),
        close=float(base+i),high=float(base+i+2),low=float(base+i-2),volume=volume,
        data_source=source)
        for source,base,volume in [('eodhd_eod',100,1000),('alpaca_sip',200,2000)]
        for i,day in enumerate(dates)])
    # When the preferred provider is absent, the other remains a legitimate
    # observed bar, not an invented or blended price/volume record.
    preferred=daily_bar_sources.SOURCES[preference]
    frame=frame.loc[~(frame.date.eq(str(dates[-1].date())) & frame.data_source.eq(preferred))]
    engine=create_engine('sqlite://')
    frame.to_sql('stock_bars_daily',engine,index=False)
    cfg={'market_data':{'daily_bars_preferred_source':preference}}
    monkeypatch.setattr(daily_bar_sources,'load_config',lambda:cfg)
    selected=daily_bar_sources.select_daily_bars(frame,config=cfg).sort_values('date')
    repo=RiskRepository(engine)
    price=repo.load_prices_asof(['ABC'],dates[-1].date())['ABC']
    assert price.last_close == selected.close.iloc[-1]
    assert price.price_asof_date == dates[-1].date() == price.atr_asof_date
    true_range=pd.concat([selected.high-selected.low,
        (selected.high-selected.close.shift()).abs(),(selected.low-selected.close.shift()).abs()],axis=1).max(axis=1)
    assert price.atr_20 == pytest.approx(true_range.tail(20).mean())
    assert price.adv_usd == pytest.approx((selected.close*selected.volume).tail(20).mean())
    returns=repo.load_return_matrix_asof(['ABC'],dates[-1].date(),lookback_days=30)
    expected=selected.close.pct_change(fill_method=None).tail(30).to_numpy()
    assert len(returns)==30
    assert returns.ABC.to_numpy() == pytest.approx(expected)
