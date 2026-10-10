import numpy as np
import pandas as pd

from scripts.research.alpaca_options_historical_volume_test import paired_features


def test_same_strike_nearest_tenor_pair_and_orientation():
    contracts = pd.DataFrame([
        {'contract_symbol':f'{side}{strike}', 'symbol':'ABC','expiration_date':'2025-01-22',
         'strike_price':strike,'type':side}
        for side in ['call','put'] for strike in [95,100]])
    bars = pd.DataFrame([{'contract_symbol':f'{side}{strike}','t':'2025-01-02T05:00:00Z',
                         'v':100 if side=='call' else 10}
                        for side in ['call','put'] for strike in [95,100]])
    spots=pd.DataFrame([{'day':pd.Timestamp('2025-01-02'),'symbol':'ABC','spot':100}])
    result=paired_features(bars,contracts,spots)
    assert len(result)==1
    assert result.iloc[0].strike==100
    assert np.isclose(result.iloc[0].volume_call_minus_put_log,np.log1p(100)-np.log1p(10))


def test_missing_put_is_not_zero_volume():
    contracts=pd.DataFrame([{'contract_symbol':'call','symbol':'ABC','expiration_date':'2025-01-22',
                             'strike_price':100,'type':'call'}])
    bars=pd.DataFrame([{'contract_symbol':'call','t':'2025-01-02T05:00:00Z','v':10}])
    spots=pd.DataFrame([{'day':pd.Timestamp('2025-01-02'),'symbol':'ABC','spot':100}])
    assert paired_features(bars,contracts,spots).empty
