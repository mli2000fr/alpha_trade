import pandas as pd
import pytest
from scripts.research import multi_asset_trend_qualify as q


def test_precision_not_unlimited_tolerance():
    assert q.rates_match(.18853,.189)
    assert q.rates_match(1.134924,1.13492)
    assert not q.rates_match(.18853,.188)
    assert not q.rates_match(.3,.2)


def test_prices_missing_invalid_duplicate_blocked():
    days=pd.date_range('2020-01-01',periods=2)
    f=pd.DataFrame(dict(symbol=['X','X'],date=days,open=[10,10],high=[11,11],low=[9,9],close=[10,10],volume=[1,1]))
    q.validate_prices(f,['X'],days)
    with pytest.raises(ValueError,match='Incomplete'):q.validate_prices(f.iloc[:1],['X'],days)
    with pytest.raises(ValueError,match='duplicate'):q.validate_prices(pd.concat([f,f]),['X'],days)
    f.loc[0,'high']=8
    with pytest.raises(ValueError,match='OHLC'):q.validate_prices(f,['X'],days)
