import numpy as np
import pandas as pd
from scripts.research.us_overnight_intraday_readout import side_summary


def test_side_breakdown_does_not_merge_long_short_or_missing_accuracy():
    f=pd.DataFrame(dict(scope='TOP10',admission='ALL',horizon=20,policy='INTRADAY20',year=2024,
        side=[1,1,-1],date=pd.to_datetime(['2024-01-01']*3),net=[.1,-.1,-.3],net_stress=[.09,-.11,-.31],
        correct=[1,np.nan,0],net_win=[True,False,False]))
    x=side_summary(f).set_index('side')
    assert x.loc[1,'n']==2 and x.loc[1,'directional_n']==1
    assert x.loc[1,'mean_net']==0 and x.loc[1,'accuracy']==1
    assert x.loc[-1,'n']==1 and x.loc[-1,'mean_net']==-.3
