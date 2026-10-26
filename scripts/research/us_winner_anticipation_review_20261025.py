"""Separate prefix review and existing-B4 strata; no additional flag search."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

from scripts.research import us_winner_anticipation_audit_20261025 as audit


def main():
    report=audit.read(audit.ROOT/'report.json')
    for name,h in report['sources'].items():
        if audit.digest(name)!=h:raise ValueError('Changed audit source')
    from scripts.research import us_winner_monthly_inputs_20261024 as inputs
    tape=inputs.Tape(audit.INPUT)
    schedule={s.session_date:s for s in inputs.grid.calendar().sessions(
        tape.pivots['close'].index.min().date(),inputs.END) if s.is_open}
    pivots={k:v.reindex(pd.to_datetime(sorted(schedule))) for k,v in tape.pivots.items()}
    full=audit.price_features(pivots,tape.cohort)
    cutoffs=['2020-01-02','2021-06-01','2023-01-03','2024-06-03']
    for cutoff in cutoffs:
        stamp=pd.Timestamp(cutoff)
        partial={k:v.loc[:stamp] for k,v in pivots.items()}
        actual=audit.price_features(partial,tape.cohort[tape.cohort.date.le(stamp)])
        for a,b in zip(full,actual):pd.testing.assert_frame_equal(a.loc[:stamp],b,check_exact=True)
    strata=[];checked=0
    for label,folder in audit.CASES.items():
        contexts=pd.read_parquet(audit.ROOT/(label.lower()+'-entry-contexts.parquet'))
        trades=pd.read_parquet(folder/'trades.parquet')
        if not (contexts.known_before<contexts.entry_at).all():raise ValueError('Future context')
        known=contexts.past_health_last_exit.dropna()
        if not (known<=contexts.loc[known.index,'known_before']).all():raise ValueError('Future exit label')
        for row in contexts.iloc[::max(1,len(contexts)//50)].itertuples():
            past=trades[pd.to_datetime(trades.exit_date,utc=True).le(row.known_before)].sort_values('exit_date').tail(20)
            expected=None if len(past)<20 else bool(float(past.pnl.clip(lower=0).sum())<float(-past.pnl.clip(upper=0).sum()))
            got=row.STRATEGY_PF20_WEAK
            if expected is None:
                if pd.notna(got):raise ValueError('Unknown health silently filled')
            elif got!=expected:raise ValueError('Health does not match independent historical prefix')
            checked+=1
        risk=pd.read_parquet(folder/'risk-decisions.parquet')
        risk=risk[risk.kind.eq('ENTRY')&risk.max_quantity.gt(0)].copy()
        risk['time']=pd.to_datetime(risk.time,utc=True)
        if risk.groupby(['time','symbol']).allocation_scale.nunique().gt(1).any():
            raise ValueError('Ambiguous original entry allocation')
        risk=risk.drop_duplicates(['time','symbol'],keep='last')
        merged=contexts.merge(risk[['time','symbol','allocation_scale']],left_on=['entry_at','symbol'],
            right_on=['time','symbol'],how='left',validate='one_to_one')
        if merged.allocation_scale.isna().any():raise ValueError('Accepted entry missing native risk approval')
        merged['native_b4_state']=np.where(merged.allocation_scale>=.999999,'FULL','REDUCED')
        for (year,state),g in merged[merged.entry_year.isin([2023,2024])].groupby(['entry_year','native_b4_state']):
            for flag in [report['selected_flag'],'STRATEGY_PF20_WEAK']:
                if flag:
                    strata.append(dict(run=label,entry_year=int(year),native_b4_state=state,**audit.aggregate(g,flag)))
        merged.to_parquet(audit.ROOT/(label.lower()+'-b4-context-review.parquet'),index=False)
    output=dict(status='PASS_PREFIX_TEMPORALITY_AND_NATIVE_B4_MATCH',
        note='Same assistant, not independent human review; stratification is descriptive, not a new selection.',
        price_prefix_cutoffs=cutoffs,feature_frames_checked=len(cutoffs)*3,
        independently_recomputed_health_rows=checked,strata=strata,
        original_report_sha256=audit.digest(audit.ROOT/'report.json'),
        sources={str(Path(__file__)):audit.digest(__file__)},no_replay=True,production_unchanged=True)
    path=audit.ROOT/'post-review.json'
    if path.exists():raise FileExistsError('Do not overwrite review')
    audit.save(path,output)
    print(json.dumps({k:v for k,v in output.items() if k!='strata'},indent=2))


if __name__=='__main__':main()
