"""Retrospective macro sensitivity, explicitly not certified PIT evidence."""
from pathlib import Path
from unittest.mock import patch
import json

import numpy as np
import pandas as pd

from scripts.research import us_q051_protection_feature_audit_20261118 as base
from scripts.research import us_q051_protection_adaptive_audit_20261118 as adaptive
from scripts.research.us_q051_protection_qualified_audit_20261118 import diagnostic_only
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=base.ROOT/'macro-sensitivity-v1'


def macro_features(rows,calendar):
    a=pd.DataFrame(rows).copy();a['trade_date']=pd.to_datetime(a.trade_date)
    if a.trade_date.duplicated().any():raise ValueError('Ambiguous macro dates')
    a=a.set_index('trade_date').reindex(calendar)
    result=pd.DataFrame(index=calendar)
    for name in ['vix','vix9d','vix3m','vxn','move','ten_y']:
        s=pd.to_numeric(a[name],errors='coerce');result['macro__'+name]=s
        for window in [1,5,10,20]:
            difference=s-s.shift(window) if name=='ten_y' else s/s.shift(window)-1
            result['macro__'+name+'_change'+str(window)]=difference.where(s.notna().rolling(window+1).sum().eq(window+1))
        mean=s.shift(1).rolling(126,min_periods=63).mean();std=s.shift(1).rolling(126,min_periods=63).std()
        result['macro__'+name+'_z126']=(s-mean)/std.replace(0,np.nan)
    for numerator,denominator in [('vix9d','vix'),('vix3m','vix'),('vix9d','vix3m'),('vxn','vix')]:
        result['macro__'+numerator+'_over_'+denominator]=pd.to_numeric(a[numerator])/pd.to_numeric(a[denominator])
    return result.replace([np.inf,-np.inf],np.nan)


def main():
    ROOT.mkdir(parents=True,exist_ok=True);raw=pd.read_parquet(base.ROOT/'all-audit-features.parquet')
    rows=json.loads((base.ROOT/'macro-retrospective-rows.json').read_text());calendar=pd.read_parquet(base.FULL/'close.parquet',columns=['SPY']).index
    m=macro_features(rows,calendar).reindex(raw.index)
    for cut in ['2023-12-29','2024-11-29','2025-05-30']:
        subset=[r for r in rows if pd.Timestamp(r['trade_date'])<=pd.Timestamp(cut)]
        pd.testing.assert_frame_equal(m.loc[:cut],macro_features(subset,calendar[calendar<=cut]).reindex(raw.index[raw.index<=cut]))
    extra=pd.concat([m,m.rolling(5,min_periods=5).mean().add_suffix('__mean5'),(m-m.shift(5)).add_suffix('__delta5')],axis=1)
    raw.join(extra).to_parquet(ROOT/'all-audit-features.parquet')
    pd.read_parquet(base.ROOT/'future-outcomes.parquet').to_parquet(ROOT/'future-outcomes.parquet')
    atomic_json(ROOT/'sensitivity-protocol.json',dict(script_sha256=digest(Path(__file__)),macro_columns=len(extra.columns),
        observations='Historical market indicators stored later in2026, no vintage qualification',
        main_rule_evidence=False,independent_holdout=False,production_ready=False,threshold_changes=False,
        retrospective_history_already_observed=True,source_sha256=digest(base.ROOT/'macro-retrospective-rows.json')))
    original=base.screen
    def qualified(features,outcome):
        table=original(features,outcome);table['diagnostic_only']=table.feature.map(diagnostic_only)
        table['eligible']=table.eligible&~table.diagnostic_only;return table
    with patch.object(base,'ROOT',ROOT),patch.object(adaptive,'ROOT',ROOT/'relative-qualified'),patch.object(base,'screen',qualified):adaptive.main()


if __name__=='__main__':main()
