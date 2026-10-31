"""Read-only feasibility of adding consensus to the refreshed TOP20 options audit."""
from pathlib import Path
import argparse

import numpy as np
import pandas as pd
from sqlalchemy import text, bindparam

from scripts.research.us_options_equal_mix_20261026 import digest, read, write
from scripts.research.us_consensus_reliability_20261022 import row_quality

PARENT=Path('artifacts/research/us_options_top20_refresh/20261030-v2')


def current_consensus(raw, runs, top, cutoff):
    """No future fiscal-period comparisons, missing counts or receipts inferred."""
    checks={int(r['id']):row_quality(r,runs) for r in raw.to_dict('records')}
    f=raw.copy()
    f['known_at']=pd.to_datetime([checks[int(i)]['conservative_available'] for i in f.id],utc=True)
    f['fiscal_period_end']=pd.to_datetime(f.fiscal_period_end)
    f['raw_ok']=[checks[int(i)]['raw_normalization_ok'] and checks[int(i)]['run_receipt_ok'] for i in f.id]
    rows=[]
    for r in top.to_dict('records'):
        decision=min(pd.Timestamp(r['decision_at']),cutoff)
        eligible=f[f.symbol.eq(r['symbol']) & f.raw_ok & f.known_at.lt(decision)
            & f.known_at.ge(decision-pd.Timedelta(hours=72))]
        eligible=eligible[eligible.fiscal_period_end.between(pd.Timestamp(r['signal_day'])-pd.Timedelta(days=100),
                                                           pd.Timestamp(r['signal_day'])+pd.Timedelta(days=100))]
        item={k:r[k] for k in ('signal_day','symbol','selected','combined_score','reason')}
        item.update(consensus_id=None,revisions30=np.nan,eps30=np.nan,
                    consensus_reason='NO_FRESH_QUALIFIED_RECEIPT')
        if not eligible.empty:
            # Same observable anchor policy as the preceding consensus audit;
            # latest fiscal period within a fixed window, then latest completed receipt.
            chosen=eligible.sort_values(['fiscal_period_end','known_at','id']).iloc[-1].to_dict()
            q=checks[int(chosen['id'])]
            item.update(consensus_id=int(chosen['id']),consensus_available=str(chosen['known_at']),
                fiscal_period=str(chosen['fiscal_period_end'].date()),consensus_reason='RESEARCH_ONLY')
            count=chosen.get('eps_analyst_count')
            if pd.notna(count) and count>=3 and q['eps_range_ok']:
                up,down=chosen.get('revisions_up_30d'),chosen.get('revisions_down_30d')
                if all(pd.notna(x) and np.isfinite(float(x)) and float(x)>=0 for x in (up,down)):
                    item['revisions30']=(float(up)-float(down))/(float(up)+float(down)) if up+down else 0.
                now,prior=chosen.get('eps_current'),chosen.get('eps_30d_ago')
                if all(pd.notna(x) and np.isfinite(float(x)) for x in (now,prior)) and prior!=0:
                    item['eps30']=(float(now)-float(prior))/abs(float(prior))
        rows.append(item)
    return pd.DataFrame(rows),checks


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    parent=read(PARENT/'protocol.json');cutoff=pd.Timestamp(parent['cutoff'])
    seal=read(PARENT/'seal.json')
    for n,sha in seal['files'].items():
        if digest(PARENT/n)!=sha:raise ValueError('Parent changed '+n)
    top=pd.read_csv(PARENT/'top20-filter-decisions.csv')
    top['signal_day']=pd.to_datetime(top.signal_day)
    top['decision_at']=pd.to_datetime(top.decision_at,utc=True)
    from database.connection import get_sqlalchemy_engine
    eng=get_sqlalchemy_engine()
    if eng.url.database!='alpha_trade':raise ValueError('US only')
    sources={str(p):digest(p) for p in [Path(__file__),Path('scripts/research/us_consensus_reliability_20261022.py'),
        Path('service/eodhd/consensus_snapshot.py'),PARENT/'seal.json']}
    write(output/'protocol.json',dict(cutoff=str(cutoff),parent=str(PARENT),sources=sources,
        SQL='READ ONLY REPEATABLE READ UTC rollback',new_inference=False,training=False,
        provider_calls=0,LLM_calls=0,production_changes=False,
        method='Coverage before outcomes; no combined performance if common mature cohort empty',
        consensus_policy='0q same anchor, within 100 calendar days, received <=72h before decision, >=3 EPS analysts'))
    try:
        with eng.connect() as c:
            c.execute(text("SET SESSION time_zone='+00:00'"))
            c.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            c.execute(text('SET SESSION TRANSACTION READ ONLY'))
            params=dict(symbols=sorted(top.symbol.unique()),cutoff=cutoff.tz_localize(None).to_pydatetime())
            sql='''SELECT * FROM stock_analyst_consensus_eodhd_history WHERE provider='eodhd'
                AND symbol IN :symbols AND horizon_raw='0q' AND observed_at<=:cutoff
                AND fiscal_period_end BETWEEN '2026-06-01' AND '2027-02-28'
                ORDER BY symbol,fiscal_period_end,observed_at,id'''
            raw=pd.DataFrame([dict(r) for r in c.execute(text(sql).bindparams(
                bindparam('symbols',expanding=True)),params).mappings()])
            runs=pd.DataFrame([dict(r) for r in c.execute(text('''SELECT run_id,status,started_at,finished_at
                FROM pit_collection_runs WHERE batch_name='eodhd_consensus_snapshot' AND started_at<=:cutoff'''),
                params).mappings()])
            c.rollback()
    finally:eng.dispose()
    raw.to_parquet(output/'consensus.parquet',index=False)
    runs.to_parquet(output/'runs.parquet',index=False)
    f,checks=current_consensus(raw,{r['run_id']:r for r in runs.to_dict('records')},top,cutoff)
    f.to_csv(output/'asof-consensus-coverage.csv',index=False)
    paths=pd.read_parquet(PARENT/'paths.parquet').merge(
        f[['signal_day','symbol','consensus_id','revisions30','eps30']],on=['signal_day','symbol'],validate='many_to_one')
    daily=[]
    for day,g in f.groupby('signal_day'):
        options=g.combined_score.notna()
        daily.append(dict(signal_day=str(day.date()),top20=len(g),options_scored=int(options.sum()),
            consensus_revisions=int(g.revisions30.notna().sum()),consensus_eps30=int(g.eps30.notna().sum()),
            common_revisions=int((options&g.revisions30.notna()).sum()),
            common_eps30=int((options&g.eps30.notna()).sum()),
            selected_with_revisions=int((g.selected&g.revisions30.notna()).sum())))
    result={}
    for h,g in paths.groupby('horizon'):
        common=g.combined_score.notna()&g.revisions30.notna()
        result[str(h)]=dict(common=int(common.sum()),mature_valid_common=int((common&g.status.eq('LABEL')).sum()),
            mature_ambiguous_common=int((common&g.status.eq('AMBIGUOUS_PATH')).sum()),
            immature_common=int((common&g.status.eq('NOT_MATURE')).sum()),
            mature_valid_eps30_common=int((g.combined_score.notna()&g.eps30.notna()&g.status.eq('LABEL')).sum()),
            common_auc=None,incremental_return=None)
    report=dict(status='BLOCKED_NO_MATURE_COMMON_COHORT' if not any(v['mature_valid_common'] for v in result.values())
        else 'COMMON_COHORT_REQUIRES_SEPARATE_FROZEN_COMPARISON',
        cutoff=str(cutoff),consensus_first_received=str(raw.observed_at.min()),consensus_rows=len(raw),
        technical_raw_ok=sum(q['raw_normalization_ok'] for q in checks.values()),
        completed_receipt_ok=sum(q['run_receipt_ok'] for q in checks.values()),
        daily=daily,horizons=result,production_qualified=False,
        limitations=['EPS accounting basis unlabelled; period normalization and contributor composition reserves',
            'No September consensus available; never backdate October rolling lookbacks',
            'Options scoring needs min 4 covered; do not turn single unscored feature into deployed selection',
            'No optimal weights fitted and no combined score promoted'])
    write(output/'report.json',report)
    write(output/'seal.json',dict(files={p.name:digest(p) for p in output.iterdir() if p.is_file()},sources=sources))
    print(report['status']);print(daily);print(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
