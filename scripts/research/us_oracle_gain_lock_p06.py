"""P06: full-position gain-fraction protection after observed +10%, offline.

Same frozen Winner entries/cash/B4 as P01/P02. No partial exits, no SQL,
provider, training, broker or production mutation. No threshold optimization.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

from common.config_loader import load_config
from scripts.research import us_oracle_compression_p01 as parent
from scripts.research.us_oracle_partial_p02 import validate_config
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

READ=parent.READ
REFERENCE=parent.OUTPUT
OUTPUT=Path('artifacts/research/us_oracle_gain_lock_p06/20261022-v1')
ARMS=('WINNER','P06')
FEES=(8,25)
RULE=dict(stop_pct=.07,activation_pct=.10,preserved_gain_fraction=.5,horizon_sessions=20,
          activation_tick_rounding='cent',stop_tick_rounding='cent',effective='NEXT_BAR_ONLY')
ORIGINAL_LEDGER=parent.CentLedger
ORIGINAL_SCALAR=parent.scalar_exit_cents


def gain_stop(entry,observed_peak):
    """Only the hard stop until activation; no residual TR15 in the P06 arm.

    Peak must be the maximum of PRIOR completed bars and actual entry. Both
    activation threshold and standing stop are rounded to the cent. Keep the
    exact existing (1-.07) expression at half-cent floating boundaries.
    """
    stop=round(entry*(1-RULE['stop_pct']),2)
    active=observed_peak>=round(entry*(1+RULE['activation_pct']),2)
    if active:
        stop=max(stop,round(entry+RULE['preserved_gain_fraction']*(observed_peak-entry),2))
    return stop,active


class GainLockLedger(ORIGINAL_LEDGER):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.activations=[];self.activated_campaigns=set()

    def known_stop(self,symbol):
        p=self.state.positions[symbol]
        return gain_stop(p.entry_price,p.peak_high)[0]

    def observe_bar(self,bars,**kwargs):
        equity=super().observe_bar(bars,**kwargs)
        # Native observation first resolves old protections; only survivors
        # may activate after this bar. No same-bar high/low ordering invented.
        for s,p in self.state.positions.items():
            meta=self.live_meta[s];key=(int(meta['pair_id']),meta['entry_timestamp'])
            stop,active=gain_stop(p.entry_price,p.peak_high)
            if active and key not in self.activated_campaigns:
                self.activated_campaigns.add(key)
                self.activations.append(dict(symbol=s,pair_id=key[0],entry_timestamp=key[1],
                    observed_at=self.now+pd.Timedelta(minutes=5),effective_no_earlier_than=self.now+pd.Timedelta(minutes=5),
                    entry=p.entry_price,observed_peak=p.peak_high,stop=stop,expiry=meta['expiry']))
        return equity

    def finish_day(self):
        value=super().finish_day()
        if self.day==self.days[-1]:atomic_json(self.guard_output/'gain-lock-activations.json',self.activations)
        return value


def unit_outcome(path,entry,expiry,fee):
    price=float(entry['price']);peak=price;activated=False
    for r in path.itertuples():
        stop,active=gain_stop(price,peak)
        if r.open<=stop:exit_price,stamp,reason=float(r.open),r.bar_timestamp,'STOP_GAP'
        elif r.bar_timestamp>=expiry:exit_price,stamp,reason=float(r.open),r.bar_timestamp,'HORIZON_OPEN'
        elif r.low<=stop:exit_price,stamp,reason=stop,r.bar_end_timestamp,'STOP'
        else:
            peak=max(peak,float(r.high));activated=activated or gain_stop(price,peak)[1]
            continue
        return dict(net_pct=100*((exit_price-price)/price-fee*(1+exit_price/price)),
            price=exit_price,time=stamp,reason=reason,activated=activated)
    raise ValueError('Mature path must exit')


@contextmanager
def replay_variant(arm):
    """Process-local factory injection only; original source files untouched.

    Serial replay only. Baseline and P06 share all other native portfolio code.
    Always restore both factories, including on a failed audit.
    """
    from scripts.research.us_oracle_gain_lock_p06_audit import scalar_exit
    old_ledger,old_scalar=parent.CentLedger,parent.scalar_exit_cents
    try:
        if arm=='P06':parent.CentLedger,parent.scalar_exit_cents=GainLockLedger,scalar_exit
        elif arm=='WINNER':parent.CentLedger,parent.scalar_exit_cents=ORIGINAL_LEDGER,ORIGINAL_SCALAR
        else:raise ValueError('Unknown frozen arm')
        yield
    finally:
        parent.CentLedger,parent.scalar_exit_cents=old_ledger,old_scalar


def prepare(root):
    root=Path(root)
    if root.exists():raise ValueError('Fresh immutable output required')
    report=READ(REFERENCE/'report.json');verify_hashes(REFERENCE,report['files'])
    audit=READ(REFERENCE/'final-audit.json')
    if audit['status']!='PASS_P01_SEPARATE_ARITHMETIC_AND_PORTFOLIO_AUDITS' or audit['primary_report_sha256']!=digest(REFERENCE/'report.json'):
        raise ValueError('Verified Winner reference required')
    config=load_config()['winner_pyramiding'];validate_config(config)
    sources=dict(READ(REFERENCE/'protocol.json')['sources'])
    files=[Path(__file__),Path('scripts/research/us_oracle_gain_lock_p06_audit.py'),
        Path('tests/test_us_oracle_gain_lock_p06.py'),Path('doc/ml/oracle_gain_lock_p06_20261022.md'),
        Path('config.yaml'),Path('scripts/research/us_oracle_partial_p02.py'),Path('risk_management/concentration.py'),
        REFERENCE/'report.json',REFERENCE/'final-audit.json']
    sources.update({str(p):digest(p) for p in files})
    root.mkdir(parents=True)
    atomic_json(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        reference=str(REFERENCE),rule=RULE,arms=ARMS,fees_bps_per_leg=FEES,configured_winner=config,
        entry='Identical frozen WINNER entries: two completed regular5m closes above previous raw-session high after fresh crossing, next contiguous open. No P01/P02 filter.',
        intervention='Replace onlyTR15 by gain-fraction stop. Initial SL round(E*(1-.07),2). '
            'Activation after a completed bar with P>=round(E*(1+.10),2). '
            'Then max(hardSL,round(E+.50*(P-E),2)); P is monotone prior-completed-bar maximum. '
            'Update effective earliest next bar. No sale at threshold, no partial, no TP, no BE rule, no add or expiry reset.',
        unchanged='Annual4000USD,1x entry gross cap, native HALF target/SL7sizing/constraints/B4DD15; '
            'same200conditional research CatBoost PATH_H20 campaigns/69symbols, priorSPYregime, '
            '20holding sessions entry included thenOPEN21, fee8/25bps perleg. Current enabled:false not changed.',
        provenance='Existing local raw regular unfilled SIP archive; no SQL/download. '
            'Four WINNER baseline trade/marks/decision/maintenance/risk-event files must reproduce byte-exactly. '
            'Scalar exits independent of primary stop function; existing vector cash/B4 reconstruction retained.',
        evaluation='Single10%/50%setting, no search. Portfolio plus paired per-entry unit outcomes, '
            'nonoverlap per symbol conservativeOracleJ40 and monthly Oracle-date bootstrap. '
            'Known2025/2026, no pristine holdout. No2024 simulation on absent frozen intraday archive.',
        criteria=dict(min_nonoverlap_per_year=30,min_activated_per_year=10,
            positive_portfolio_increment_both_years_both_fees=True,dd_not_worse_both_years_normal_fees=True,
            positive_unit_increment_both_years_stress=True,monthly_cluster_lower95_gt_zero=True,
            minimum_months=6,draws=2000,seed=731),
        limitations=READ(REFERENCE/'protocol.json')['limitations']+[
            'Inherited commonP01coverage exclusions, not entire dailyTOP10 nor productionLightGBM.',
            'Stop-update/replacement latency and historical NBBO/queue/fills unqualified: not full live parity.',
            'Half-cent float expression follows existing Winner contract, not invented decimal conversion.'],
        training=False,sql_writes=False,provider_calls=False,broker_calls=False,production_changes=False,full_live_parity=False))
    atomic_json(root/'progress.json',dict(status='PREPARED',completed=0,total=8))


def unit_results(root,signals,groups,schedule):
    days=pd.DatetimeIndex(schedule.date);sch=schedule.set_index('date');rows=[]
    for s in signals.itertuples():
        i=days.get_loc(s.date)
        frame=pd.concat([groups[s.symbol,d] for d in days[i:i+21]],ignore_index=True)
        frame=frame[frame.bar_timestamp.between(s.timestamp,s.due_open)].reset_index(drop=True)
        row=dict(pair_id=int(s.pair_id),symbol=s.symbol,rank=int(s.rank),year=s.oracle_date.year,
            oracle_date=s.oracle_date,entry_time=s.timestamp,
            label_available=sch.loc[days[days.get_loc(s.oracle_date)+40],'market_open'])
        for fee in FEES:
            entry=dict(timestamp=s.timestamp,price=s.price)
            b=parent.history.unit_outcome(frame,entry,parent.history.BASE,parent.history.ArchiveCalendar(schedule),fee/10000)
            p=unit_outcome(frame,entry,s.due_open,fee/10000)
            row[f'WINNER_{fee}']=b['net_pct'];row[f'P06_{fee}']=p['net_pct']
            row['activated']=p['activated'];row['P06_exit']=p['time'];row['P06_exit_price']=p['price']
        rows.append(row)
    units=pd.DataFrame(rows);units.to_parquet(root/'unit-results.parquet',index=False)
    spaced=parent.history.spaced(units);spaced.to_parquet(root/'nonoverlap.parquet',index=False)
    checks=[]
    for year,g in spaced.groupby('year'):
        ci=parent.history.monthly_interval(g.oracle_date.dt.tz_localize('UTC'),g.P06_8-g.WINNER_8)
        checks.append(dict(year=int(year),n=len(g),activated=int(g.activated.sum()),
            increment_pp=float((g.P06_8-g.WINNER_8).mean()),stress_increment_pp=float((g.P06_25-g.WINNER_25).mean()),ci=ci))
    return checks


def analyze(root):
    root=Path(root)
    if (root/'report.json').exists():raise ValueError('Already sealed')
    protocol=READ(root/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    groups,_,schedule=parent.load_groups()
    original=pd.read_parquet(REFERENCE/'signals.parquet');original=original[original.arm.eq('WINNER')].copy()
    original.to_parquet(root/'entry-signals.parquet',index=False)
    signals=pd.concat([original.assign(arm=arm) for arm in ARMS],ignore_index=True)
    checks=unit_results(root,original,groups,schedule);results=[]
    for fee in FEES:
        for year in (2025,2026):
            for arm in ARMS:
                atomic_json(root/'progress.json',dict(status='RUNNING',completed=len(results),total=8,year=year,arm=arm,fee_bps=fee))
                with replay_variant(arm):r=parent.portfolio(root,arm,year,fee,signals,groups,schedule)
                out=root/f'{arm}-fee{fee}'/'cases'/str(year)
                if arm=='WINNER':
                    old=REFERENCE/f'WINNER-fee{fee}'/'cases'/str(year)
                    for name in ['trades.parquet','marks.parquet','decisions.json','maintenance.json','production-risk-events.json']:
                        if digest(out/name)!=digest(old/name):raise ValueError('Exact baseline reproduction failed:'+name)
                r['baseline_exact_reproduction']=arm=='WINNER'
                r['gain_lock_activations']=len(READ(out/'gain-lock-activations.json')) if arm=='P06' else 0
                results.append(r)
                print(f'{year} {arm} fee{fee}: {r["return_pct"]:.3f}% DD{r["max_drawdown_pct"]:.3f} trades{r["trades"]}',flush=True)
    comparisons=[]
    for fee in FEES:
        for year in (2025,2026):
            b=next(r for r in results if r['arm']=='WINNER' and r['year']==year and r['fee_bps']==fee)
            p=next(r for r in results if r['arm']=='P06' and r['year']==year and r['fee_bps']==fee)
            comparisons.append(dict(year=year,fee_bps=fee,return_increment_pp=p['return_pct']-b['return_pct'],
                dd_increment_pp=p['max_drawdown_pct']-b['max_drawdown_pct']))
    sufficient=all(any(c['year']==y and c['n']>=30 and c['activated']>=10 for c in checks) for y in (2025,2026))
    passes=sufficient and all(c['return_increment_pp']>0 for c in comparisons) and all(
        c['dd_increment_pp']<=0 for c in comparisons if c['fee_bps']==8) and all(
        c['stress_increment_pp']>0 and c['ci']['months']>=6 and c['ci']['lower95']>0 for c in checks)
    pd.DataFrame([{k:v for k,v in r.items() if k!='audit'} for r in results]).to_csv(root/'annual-summary.csv',index=False)
    verify_hashes(Path('.'),protocol['sources']);verify_hashes(REFERENCE,READ(REFERENCE/'report.json')['files'])
    report=dict(status='EXPLORATORY_P06_WORTH_CONFIRMATION' if passes else 'INSUFFICIENT_P06_SAMPLE' if not sufficient else 'NO_GO_P06_NOT_CONFIRMED',
        campaigns=len(original),symbols=int(original.symbol.nunique()),results=results,comparisons=comparisons,
        unit_checks=checks,production_promoted=False,
        files={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.name not in ['run.lock','progress.json','report.json']})
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status=report['status'],completed=8,total=8,failed=0))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=OUTPUT)
    p.add_argument('--phase',choices=['prepare','analyze','run'],default='run');a=p.parse_args()
    from scripts.research.oracle_path_confirmation import exclusive_run
    try:
        if a.phase in ('prepare','run'):prepare(a.output_dir)
        if a.phase in ('analyze','run'):
            with exclusive_run(a.output_dir):analyze(a.output_dir)
    except Exception as exc:
        if (a.output_dir/'protocol.json').exists() and not (a.output_dir/'report.json').exists():
            atomic_json(a.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
