"""Check frozen outputs and qualify receipt metadata for the archived branch."""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from service.options_directional.config import OptionsFilterConfig
from service.options_directional.features import select_top

ROOTS=[Path('artifacts/research/us_options_winrate/20261109-v1'),
       Path('artifacts/research/us_options_winrate/20261109-archived-v1')]


def review(root):
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    seal=read(root/'snapshot-seal.json');protocol=read(root/'protocol.json')
    for name,sha in seal['files'].items():
        if digest(root/name)!=sha:raise ValueError('Changed frozen export '+name)
    for name,sha in seal['sources'].items():
        if digest(Path(name))!=sha:raise ValueError('Changed source '+name)
    decisions=pd.read_parquet(root/'analysis/decisions.parquet');checked=0
    for (model,rank,day),g in decisions.groupby(['model_label','top_n','signal_day']):
        features={r['symbol']:{k:r[k] for k in ['volume_feature','oi_feature','available_at','volume_expiry','oi_expiry'] if k in r}
            for r in g.to_dict('records') if pd.notna(r.get('volume_feature')) and pd.notna(r.get('oi_feature'))}
        cfg=replace(OptionsFilterConfig(**protocol['options']),oracle_top_n=int(rank))
        expected=select_top(g.to_dict('records'),features,cfg)
        actual=g.set_index('symbol')
        for row in expected:
            saved=actual.loc[row['symbol']]
            if row['selected']!=saved.selected or row['reason']!=saved.reason:raise ValueError('Production selection mismatch')
            for field in ['combined_score','volume_score','oi_score']:
                a=row.get(field,np.nan);b=saved.get(field,np.nan)
                if not ((pd.isna(a) and pd.isna(b)) or np.isclose(a,b,rtol=0,atol=1e-12)):
                    raise ValueError('Production score mismatch')
            checked+=1
    frame=pd.read_parquet(root/'analysis/outcomes.parquet');report=read(root/'analysis/report.json')
    counters=0
    for row in report['results']:
        f=frame[(frame.model_label==row['model'])&(frame.top_n==row['top_n'])&(frame.horizon==row['horizon'])]
        selected=f[f.selected];active=selected.signal_day.unique()
        cohorts={'filtered':selected,'matched_all_oracle':f[f.signal_day.isin(active)],
            'matched_covered':f[f.signal_day.isin(active)&f.combined_score.notna()]}
        for name,part in cohorts.items():
            valid=part[part.trade_status.eq('VALID')];wins=int(valid.winning.sum())
            saved=row[name]
            if saved['n']!=len(valid) or saved['wins']!=wins:raise ValueError('Published count mismatch')
            if len(valid) and not np.isclose(saved['win_rate_pct'],100*wins/len(valid),rtol=0,atol=1e-12):
                raise ValueError('Published win rate mismatch')
            counters+=1
    # The shared analyzer's generic first limitation describes the November-8
    # annual-model branch. Replace that description for archived original ranks;
    # all original reports and seals remain immutable and retained.
    if 'source_archive' in protocol:
        source=Path(protocol['source_archive'])
        if digest(source/'snapshot-seal.json')!=protocol['source_seal_sha256']:raise ValueError('Parent archive changed')
        report['limitations'][0]=('Archived original H20 rankings: OBSERVABLE cohorts require full ranking and lineage physically before entry; '
            'RECONSTRUIT cohorts were generated later. Original model binaries since deleted: archived metadata/lineage validated, '
            'current model reproducibility not certified.')
        report['source_archive']=protocol['source_archive'];report['model_binary_status']=protocol['model_binary_status']
    report['review']=dict(status='PASS',selection_rows_rechecked=checked,published_cohorts_recounted=counters,
        original_report_sha256=digest(root/'analysis/report.json'),snapshot_seal_sha256=digest(root/'snapshot-seal.json'),
        source_sha256=digest(Path(__file__)),independent_human_review=False)
    output=root/'analysis/reviewed-report.json'
    if output.exists():raise FileExistsError('Immutable reviewed report')
    atomic_json(output,report)
    return report['review']


if __name__=='__main__':
    for root in ROOTS:print(str(root),review(root))
