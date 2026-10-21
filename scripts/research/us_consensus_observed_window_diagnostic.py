"""Feature-only 11-to-18 October endpoint diagnostic, NOT the primary signal.

Explains the weekend's zero adjacent changes. No price/outcome access or SQL.
Does not replace the already frozen adjacent-snapshot protocol.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from scripts.research import us_consensus_observed_revision_pilot as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def endpoints(frame, cutoff):
    f = frame.copy()
    f = f[pd.to_datetime(f.available_at, utc=True).lt(pilot.utc(cutoff))
          & pd.to_datetime(f.observed_at, utc=True).lt(pilot.utc(cutoff))]
    keys = ['provider','symbol','fiscal_period_end','horizon_raw']
    if f.duplicated(keys+['snapshot_date']).any(): raise ValueError('Duplicate snapshot')
    out = []
    for _, group in f.groupby(keys, sort=True):
        group = group.sort_values(['snapshot_date','observed_at','id'])
        if len(group) < 2: continue
        old, new = group.iloc[0], group.iloc[-1]
        eps, eps_ratio = pilot.change(old.eps_avg, new.eps_avg)
        rev, rev_ratio = pilot.change(old.revenue_avg, new.revenue_avg)
        pattern = 'BOTH_UP' if eps is not None and rev is not None and eps > 0 and rev > 0 else (
            'BOTH_DOWN' if eps is not None and rev is not None and eps < 0 and rev < 0 else 'MIXED_UNCHANGED_OR_MISSING')
        out.append(dict(symbol=new.symbol,fiscal_period_end=new.fiscal_period_end,horizon_raw=new.horizon_raw,
            old_id=int(old.id),new_id=int(new.id),old_snapshot_date=old.snapshot_date,new_snapshot_date=new.snapshot_date,
            snapshots=len(group),eps_delta=eps,eps_change_ratio=eps_ratio,revenue_delta=rev,revenue_change_ratio=rev_ratio,
            old_eps_analysts=old.eps_analyst_count,new_eps_analysts=new.eps_analyst_count,
            old_revenue_analysts=old.revenue_analyst_count,new_revenue_analysts=new.revenue_analyst_count,
            analyst_counts_changed=bool(old.eps_analyst_count != new.eps_analyst_count or old.revenue_analyst_count != new.revenue_analyst_count),
            pattern=pattern,eligible_for_direction=False))
    return pd.DataFrame(out)


def run(root):
    p = pilot.prepare(root)
    verify_hashes(root,pilot.READ(root/'snapshot-ready.json')['files'])
    verify_hashes(root,pilot.READ(root/'report.json')['files'])
    out = root/'window-diagnostic'
    out.mkdir(exist_ok=False)
    atomic_json(out/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        diagnostic='Explicitly post-feature-review, pre-outcome diagnostic. Not an independently frozen trading hypothesis or optimization.',
        reason='Latest adjacent pairs are weekend unchanged; inspect complete actual observed 11-18 October endpoints, never backdate provider lookbacks.',
        parent_report_sha256=digest(root/'report.json'),snapshot_ready_sha256=digest(root/'snapshot-ready.json'),
        source_sha256=digest(Path(__file__)),cutoff=p['entry_cutoff_utc'],sql=False,price_outcomes=False,
        signal_qualification=False,all_patterns_remain_unqualified=True))
    frame = pd.read_parquet(root/'consensus.parquet')
    result = endpoints(frame,p['entry_cutoff_utc'])
    result.to_parquet(out/'endpoint-changes.parquet',index=False)
    top = pd.read_parquet(root/'oracle-top10.parquet')
    subset = result.merge(top[['symbol','oracle_rank']],on='symbol',how='inner',validate='many_to_one')
    subset.sort_values(['oracle_rank','fiscal_period_end','horizon_raw']).to_csv(out/'top10-endpoint-changes.csv',index=False)
    rows = []
    for r in top.to_dict('records'):
        s = subset[subset.symbol.eq(r['symbol'])]
        active = s[s.pattern.isin(['BOTH_UP','BOTH_DOWN'])]
        rows.append(dict(symbol=r['symbol'],oracle_rank=int(r['oracle_rank']),
            patterns=s.pattern.value_counts().to_dict(),active_periods=active[['fiscal_period_end','horizon_raw','pattern',
                'eps_change_ratio','revenue_change_ratio','analyst_counts_changed']].to_dict('records'),
            direction='ABSTAIN',reason='Unqualified current fiscal record/currency/units; counts may change; descriptive window only.'))
    report = dict(status='DESCRIPTIVE_OBSERVED_WINDOW_ONLY_NO_PERFORMANCE',rows=len(result),symbols=int(result.symbol.nunique()),
        pattern_counts=result.pattern.value_counts().to_dict(),top10=rows,
        issuer_composition='Changes of consensus averages can reflect changes in contributing analysts, not the same analysts revising their forecasts.',
        proof_scope='Normalized rows/raw item hashes checked by parent. Full provider-envelope checks cover only parent explicit sample, not automatically every new endpoint.',
        qualified_signals=0,files={n:digest(out/n) for n in ['protocol.json','endpoint-changes.parquet','top10-endpoint-changes.csv']})
    atomic_json(out/'report.json',report)
    print(dict(status=report['status'],rows=len(result),patterns=report['pattern_counts'],top10=rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
