"""Separate accounting/key/availability audit before one TP15/SL7 filter fit."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_oracle_path_profit_tp15_sl7_dataset as data


def verify_rows(frame, pool, spec, days, per_leg):
    if len(frame)!=len(pool) or frame.duplicated(['date','symbol']).any():
        raise ValueError('Lost/duplicate original candidate')
    check=pool[['date','symbol','score','oracle_rank','fold_start']].merge(
        frame[['date','symbol','score','oracle_rank','fold_start']],on=['date','symbol'],suffixes=('_a','_b'),validate='one_to_one')
    if len(check)!=len(pool):raise ValueError('Candidate membership changed')
    for column in ('score','oracle_rank','fold_start'):
        if not check[column+'_a'].eq(check[column+'_b']).all():raise ValueError('Original priority changed '+column)
    known=frame[frame.label.notna()].copy();unknown=frame[frame.label.isna()]
    if known.empty or not known.reason.eq('').all() or unknown.reason.eq('').any():
        raise ValueError('Unknown label turned into a loss or missing exclusion reason')
    if unknown.net_return.notna().any() or not known.J_qualified.all():
        raise ValueError('Invalid J-only qualification/unknown outcome')
    j=days.get_indexer(pd.DatetimeIndex(known.date))
    if (j<0).any() or (j+22>=len(days)).any():raise ValueError('Unmatured labels admitted')
    if not np.array_equal(pd.to_datetime(known.entry_date).to_numpy(),days[j+1].to_numpy()):
        raise ValueError('Entry not next open')
    if not np.array_equal(pd.to_datetime(known.label_available).to_numpy(),days[j+22].to_numpy()):
        raise ValueError('Availability not conservative J22')
    exit_index=days.get_indexer(pd.DatetimeIndex(known.exit_date))
    if (exit_index<j+1).any() or (exit_index>j+21).any():raise ValueError('Exit outside twenty-session contract')
    expiry=known.exit_reason.eq('expiry_open').to_numpy()
    if not (exit_index[expiry]==(j+21)[expiry]).all():raise ValueError('Wrong expiry open')
    for key in ('label','net_return','native_pnl','entry_outlay','exit_proceeds','entry_notional','reference_financing'):
        if not np.isfinite(known[key]).all():raise ValueError('Nonfinite accounting '+key)
    expected_financing=.5*known.entry_notional*.065*(known.exit_date-known.entry_date).dt.days/360.
    expected_net=(known.exit_proceeds-known.entry_outlay-expected_financing)/known.entry_notional
    for a,b in [(known.reference_financing,expected_financing),
                (known.native_pnl,known.exit_proceeds-known.entry_outlay),
                (known.entry_outlay,known.entry_notional*(1+per_leg)),
                (known.exit_proceeds,known.quantity*known.exit_price*(1-per_leg)),
                (known.net_return,expected_net)]:
        if not np.allclose(a,b,rtol=1e-9,atol=1e-6):raise ValueError('Native cash/financing mismatch')
    if not np.array_equal(known.label.to_numpy(),(expected_net>0).astype(float).to_numpy()):
        raise ValueError('Net-win label mismatch')
    stops=known.exit_reason.eq('initial_stop');tp=known.exit_reason.isin(['take_profit','take_profit_gap_limit'])
    if not np.allclose(known.loc[stops,'exit_price'],known.loc[stops,'entry_price']*.93):raise ValueError('SL7 changed')
    if not np.allclose(known.loc[tp,'exit_price'],known.loc[tp,'entry_price']*1.15):raise ValueError('TP15 changed')
    for name in ('FIT','VALIDATION','CONTROL'):
        part=known[known.split.eq(name)];rule=spec['splits'][name.lower()]
        if not part.date.between(rule['decision_start'],rule['decision_end']).all() or not part.label_available.lt(rule['label_before']).all():
            raise ValueError('Label leaked across split '+name)
        if not np.isfinite(part[spec['features']]).all().all():raise ValueError('Future imputation or missing J feature')
    return dict(original_candidates=len(frame),known_labels=len(known),unknown_labels=len(unknown),
        positive_expiries=int((known.exit_reason.eq('expiry_open') & known.label.eq(1)).sum()),
        conservative_intrabar_collisions=int(known.intrabar_ambiguous.sum()),
        adverse_gaps=int(known.exit_reason.eq('initial_stop_gap_open').sum()))


def run(folder):
    folder=Path(folder);report=data.read(folder/'report.json');p=data.read(folder/'protocol.json')
    for name,expected in p['sources'].items():data.plan.original.require_hash(name,expected)
    for name,expected in report['files'].items():data.plan.original.require_hash(folder/name,expected)
    spec=p['specification'];model=p['native_cost_model'];micro=p['native_microstructure']['slippage']
    if micro['model']!='fixed' or micro['base_bps']!=0 or p['native_tiered_commission'] or p['native_cost_multiplier']!=1:
        raise ValueError('Independent fee check requires the frozen canonical fixed native configuration')
    per_leg=(model['commission_bps']+model['slippage_bps']+model['spread_bps'])/10000.
    frame=pd.read_parquet(folder/'dataset.parquet');pool=pd.read_parquet(p['original_population'])
    result=verify_rows(frame,pool,spec,data.nyse_sessions('2016-01-01','2023-12-29'),per_leg)
    parities=data.read(folder/'native-parity.json');prefix=data.read(folder/'prefix-checks.json')
    if len(parities)!=24 or not all(x['native_parity'] for x in parities):raise ValueError('Real native parity missing')
    if len(prefix)!=pool.symbol.nunique() or not all(x['prefix_exact'] for x in prefix):raise ValueError('Prefix causality missing')
    result.update(status='AUDITED_NATIVE_TP15_SL7_DATASET',source_report_sha256=data.digest(folder/'report.json'),
        source_dataset_sha256=data.digest(folder/'dataset.parquet'),audit_source_sha256=data.digest(__file__),
        native_probes=24,prefix_symbols=len(prefix),features=spec['features'],model_fits=0,portfolio_runs=0,
        strict_historical_PIT_certified=False,API_calls=0,sql_writes=False)
    data.atomic_json(folder/'completion-audit.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dataset',type=Path,required=True)
    args=parser.parse_args();print(run(args.dataset))
