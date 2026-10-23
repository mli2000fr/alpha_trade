"""Post-hoc exploratory inventory of all available rolling EPS diagnostics.

Seven-day DOWN counter absent in native payload; no zero imputation or hidden
replacement. New explicit protocol AFTER revenue results, no promotion.
"""
import json
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_consensus_reliability_20261022 as parent
from scripts.research.us_consensus_reliability_sip_20261022 import CHILD


FEATURES=('REVISION_IMBALANCE_30D','EPS_CURRENT_MINUS_7D','EPS_CURRENT_MINUS_30D',
          'EPS_CURRENT_MINUS_60D','EPS_CURRENT_MINUS_90D')


def run():
    parent.check(CHILD)
    root=CHILD/'rolling-diagnostic'
    if root.exists():raise FileExistsError('New immutable diagnostic required')
    root.mkdir()
    parent.save(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        status='POST_HOC_EXPLORATORY_AFTER_REVENUE_RESULTS_NOT_INDEPENDENT_CONFIRMATION',
        reason='Native seven-day DOWN absent; explicitly examine ALL available pre-listed rolling fields, not silent substitution',
        parent_report_sha256=parent.digest(CHILD/'report.json'),source_sha256=parent.digest(Path(__file__)),
        features=list(FEATURES),rule='Sign of current EPS minus provider lag, or UP30 minus DOWN30; zero/missing abstains',
        constraints='Same received 0q source row and conservative cutoff; EPS technical check, unchanged EPS analyst count>=3',
        horizons=[1,3,5],eps_basis_unknown=True,no_rolling_vintages_backdated=True,
        no_threshold_or_best_feature_selection=True,sql_writes=False,api_calls=0,llm_calls=0,training=False))
    source=pd.read_parquet(CHILD/'consensus.parquet').set_index('id')
    records=source.to_dict('index')
    result=dict(status='COMPLETED_ALL_ROLLING_DIAGNOSTICS_EXPLORATORY_ONLY',horizons={})
    native_keys=set()
    for text in source.raw_payload_json:
        native_keys.update(k for k in json.loads(text) if 'revis' in k.lower())
    result['native_revision_keys']=sorted(native_keys)
    result['down7_present_rows']=int(source.revisions_down_7d.notna().sum())
    for horizon in (1,3,5):
        f=pd.read_parquet(CHILD/f'diagnostic-H{horizon}.parquet')
        for name in FEATURES:
            signs=[]
            for row in f.itertuples():
                current=records[row.new_id]
                if name=='REVISION_IMBALANCE_30D':
                    a,b=current['revisions_up_30d'],current['revisions_down_30d']
                else:
                    lag=name.split('_')[-1][:-1]
                    a,b=current['eps_current'],current['eps_'+lag+'d_ago']
                valid=pd.notna(a) and pd.notna(b) and np.isfinite([a,b]).all()
                signs.append(int(np.sign(a-b)) if valid else 0)
            f[name]=signs
        f.to_parquet(root/f'features-H{horizon}.parquet',index=False)
        independent=parent.reserve_windows(f)
        groups={}
        for name in FEATURES:
            valid=f.eps_technical_ok&f.eps_count_group.eq('UNCHANGED_COUNT')
            g=f[valid]
            groups[name]=dict(all=parent.metric(g,name),
                no_overlap=parent.metric(independent.loc[independent.index.intersection(g.index)],name))
        result['horizons'][str(horizon)]=groups
    result['files']={p.name:parent.digest(p) for p in root.iterdir() if p.is_file()}
    parent.save(root/'report.json',result)
    print(result['status'],flush=True)


if __name__=='__main__':run()
