import numpy as np
import pandas as pd

from scripts.research.us_q051_b_market_warning_audit_20261117 import market_features,health_features,measure


def test_price_features_do_not_use_future_rows():
    dates=pd.bdate_range('2022-01-03',periods=300)
    close=pd.DataFrame({'SPY':100*np.cumprod(np.resize([1.01,.999,.995],300)),
        'AAA':np.arange(300)+100.},index=dates)
    full,_=market_features(close);short,_=market_features(close.iloc[:220])
    pd.testing.assert_frame_equal(full.iloc[:220],short)


def test_health_excludes_future_exits_and_requires_twenty_observed_closes():
    dates=pd.bdate_range('2023-01-02',periods=30);equity=pd.Series(np.arange(30)+100.,index=dates)
    stamps=dates.tz_localize('America/New_York')+pd.Timedelta(hours=16)
    t=pd.DataFrame({'exit_date':stamps,'pnl':np.resize([1.,-2.],30)})
    full=health_features(t,equity);short=health_features(t.iloc[:22],equity.iloc[:22])
    pd.testing.assert_frame_equal(full.iloc[:22],short)
    assert pd.isna(full.iloc[18].pf20) and full.iloc[19].pf20==.5


def test_trade_warning_diagnostics_do_not_claim_portfolio_returns():
    f=pd.DataFrame({'symbol':['A','B','C'],'entry_day':pd.to_datetime(['2024-01-02']*3),
        'pnl':[-10.,20.,30.],'return_pct':[-.1,.2,.3],'flag':pd.array([True,True,False],dtype='boolean')})
    a=measure(f,'flag')
    assert a['flagged_realized_pnl']==10 and a['captured_loss_mass_pct']==100
    assert a['sacrificed_gain_mass_pct']==40 and 'portfolio_return' not in a


def test_health_preserves_fixed_ledger_order_at_equal_exit_timestamps():
    dates=pd.bdate_range('2023-01-02',periods=45);equity=pd.Series(100.,index=dates)
    times=[d.tz_localize('America/New_York')+pd.Timedelta(hours=16) for d in dates]
    t=pd.DataFrame({'exit_date':np.repeat(times,3),'pnl':np.resize([1.,-2.,4.,-8.],len(times)*3)})
    full=health_features(t,equity);prefix=t[pd.to_datetime(t.exit_date).le(times[25])]
    pd.testing.assert_frame_equal(full.iloc[:26],health_features(prefix,equity.iloc[:26]))
