"""Independent scalar/date audit of the frozen revenue-only feature pilot."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))


def maturity(entry,schedule,horizon=10):
    if horizon<1:raise ValueError('Positive session horizon required')
    j=schedule.index.get_loc(pd.Timestamp(entry))
    return schedule.iloc[j+horizon-1].market_close


def audit(root):
    if (root/'final-audit.json').exists():raise ValueError('Immutable audit')
    p=READ(root/'protocol.json');r=READ(root/'report.json')
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,r['files'])
    parent=Path(p['parent']);source=pd.read_parquet(parent/'consensus.parquet')
    lookup={int(x['id']):x for x in source.to_dict('records')}
    runs={x['run_id']:x for x in pd.read_parquet(parent/'runs.parquet').to_dict('records')}
    features=pd.read_parquet(root/'qualified-features.parquet')
    assert not features.duplicated(['entry_date','symbol','fiscal_anchor']).any()
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2026-10-01',end_date='2026-11-20')
    normalize=lambda x:pd.Timestamp(x).tz_localize('UTC') if pd.Timestamp(x).tzinfo is None else pd.Timestamp(x).tz_convert('UTC')
    for row in features.itertuples():
        a,b=lookup[row.old_id],lookup[row.new_id]
        assert a['symbol']==b['symbol']==row.symbol and a['provider']==b['provider']=='eodhd'
        assert a['horizon_raw']==b['horizon_raw']=='0q'
        assert str(a['fiscal_period_end'])[:10]==str(b['fiscal_period_end'])[:10]==row.fiscal_anchor
        stamps=[]
        for item,cutoff in [(a,row.prior_entry_open_utc),(b,row.entry_open_utc)]:
            assert runs[item['run_id']]['status']=='COMPLETED'
            latest=max(normalize(item[k]) for k in ['observed_at','available_at','ingestion_at'])
            latest=max(latest,normalize(runs[item['run_id']]['finished_at']))
            assert latest<cutoff;stamps.append(latest)
        assert stamps==[row.old_available,row.new_available]
        if row.technical_pair:
            delta=float(b['revenue_avg'])-float(a['revenue_avg'])
            assert abs(delta-row.delta)<1e-8
            assert abs(delta/float(a['revenue_avg'])-row.relative)<1e-12
            assert row.pattern==('LONG' if delta>0 else 'SHORT' if delta<0 else 'ABSTAIN')
        if row.supported_research_feature:
            assert row.symbol in ('DOCN','FUN') and row.fiscal_anchor=='2026-09-30'
            assert row.currency=='USD' and row.envelope_verified and row.count_group=='UNCHANGED_COUNT'
            assert a['revenue_analyst_count']==b['revenue_analyst_count']>=3
        if row.primary_research_pattern!='ABSTAIN':assert row.in_top10 and row.supported_research_feature
        assert row.maturity_utc==maturity(row.entry_date,schedule)
        assert not row.live_admission and not row.definition_known_before_entry
    scores=pd.read_parquet(parent/'oracle-scores.parquet')
    scores['prediction_date']=pd.to_datetime(scores.prediction_date)
    for entry,group in features[features.in_top10].groupby('entry_date'):
        cutoff=schedule.loc[entry].market_open;prior=schedule.index[schedule.index.get_loc(entry)-1]
        s=scores[scores.prediction_date.eq(prior)&pd.to_datetime(scores.created_at,utc=True).lt(cutoff)]
        expected=s.sort_values(['proba_extreme','symbol'],ascending=[False,True]).head(10).symbol.tolist()
        assert group.sort_values('oracle_rank').symbol.tolist()==expected
        assert (group.new_available<cutoff).all()
    primary=features[features.primary_research_pattern.ne('ABSTAIN')]
    assert len(primary)==len(r['signals'])
    mature=pd.to_datetime(primary.maturity_utc,utc=True).le(pd.Timestamp(p['created_at_utc']))
    assert int(mature.sum())==r['h10_mature_primary_signals']==0
    assert not r['pnl_computed'] and not r['minimum_independent_history_met']
    result=dict(status='PASS_REVENUE_ONLY_FEATURES_AND_CAUSAL_CUTOFFS_H10_IMMATURE',
        finished_at_utc=datetime.now(timezone.utc).isoformat(),rows_checked=len(features),
        primary_rows=len(primary),mature_primary=0,live_admission=False,eps_used=False,
        report_sha256=digest(root/'report.json'),code_sha256=digest(Path(__file__)),
        future_prices_read=False,api_calls=0,sql=False,training=False,orders=False)
    atomic_json(root/'final-audit.json',result);print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);audit(p.parse_args().output)
