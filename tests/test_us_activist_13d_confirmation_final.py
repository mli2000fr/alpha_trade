import json
import pandas as pd
from scripts.research.us_activist_13d_confirmation_final import json_records


def test_unknown_immature_outcomes_remain_null_not_zero_or_nan():
    rows=json_records(pd.DataFrame([{'status':'UNKNOWN','net_return':float('nan')},
                                   {'status':'IMMATURE','net_return':float('nan')}]))
    assert [x['net_return'] for x in rows]==[None,None]
    assert 'null' in json.dumps(rows,allow_nan=False)
