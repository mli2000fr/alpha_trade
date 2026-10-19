"""Causal monthly symbol/side trust filter on immutable Oracle TOP10 paths.

No new ML, SQL, HTTP or orders. Hypothetical repeated-entry outcomes are not
portfolio returns. This tests historical side affinity, NOT GPT accuracy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

LOG = logging.getLogger(__name__)
SOURCE = Path('artifacts/research/us_top10_liquidity_gap/20261019-v2')
MIN_EPISODES = 8
Z = 1.6448536269514722  # lower endpoint of two-sided 90% Wilson interval
COST_PER_LEG = .0008   # commission 1bp + half-spread 5bp + slippage 2bp, assumed
BORROW_ANNUAL = .003
ARMS = ('ALL_LONG', 'ALL_SHORT', 'SYMBOL_LONG', 'SYMBOL_SHORT', 'SELECT_SIDE')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def wilson_lower(wins, count):
    if count <= 0 or not 0 <= wins <= count: raise ValueError('Invalid binomial counts')
    p = wins/count
    return (p+Z*Z/(2*count)-Z*sqrt(p*(1-p)/count+Z*Z/(4*count*count)))/(1+Z*Z/count)


def attach_costs(frame):
    f = frame.copy()
    f['assumed_cost'] = COST_PER_LEG*(1+f.exit_price/f.entry_price)
    f['assumed_borrow'] = np.where(f.side.eq('SHORT'),BORROW_ANNUAL*(f.exit_session-1).clip(lower=0)/252,0.)
    f['net_outcome'] = f.path_return-f.assumed_cost-f.assumed_borrow
    return f


def matured_history(frame, cutoff, days):
    """Use full 20-session maturity strictly BEFORE monthly selection date.

    Short early exits do not accelerate admission of their labels.
    """
    cutoff = pd.Timestamp(cutoff)
    pos = int(days.searchsorted(cutoff))
    start = days[max(0,pos-504)]
    return frame[(frame.date>=start)&(frame.date<cutoff)&(frame.last_path_date<cutoff)].copy()


def independent_episodes(frame):
    """Earliest entry first, wait until its full window is over, regardless of PnL."""
    keep=[];ends={}
    for row in frame.sort_values(['date','symbol','side']).itertuples():
        key=(row.symbol,row.side)
        if key not in ends or row.entry_date>ends[key]:
            keep.append(row.Index);ends[key]=row.last_path_date
    return frame.loc[keep].copy()


def states_at(frame, cutoff, days):
    history = matured_history(frame,cutoff,days)
    episodes = independent_episodes(history)
    baselines = {side:dict(tp=float(g.groupby('date').tp_first.mean().mean()),
                          net=float(g.groupby('date').net_outcome.mean().mean()))
                 for side,g in history.groupby('side')}
    rows=[]
    for (symbol,side),g in episodes.groupby(['symbol','side']):
        g=g.sort_values('date');n=len(g);wins=int(g.tp_first.sum());base=baselines[side]
        lower=wilson_lower(wins,n);mean=float(g.net_outcome.mean())
        half=n//2;a,b=g.iloc[:half],g.iloc[half:]
        enough=n>=MIN_EPISODES
        positive=mean>max(0.,base['net'])
        strong=lower>base['tp']
        stable=enough and all(float(x.net_outcome.mean())>0 and float(x.tp_first.mean())>base['tp'] for x in (a,b))
        passed=bool(enough and positive and strong and stable)
        failures=[]
        if not enough:failures.append('INSUFFICIENT_NONOVERLAPPING_HISTORY')
        if enough and not positive:failures.append('NET_NOT_POSITIVE_AND_ABOVE_GLOBAL')
        if enough and not strong:failures.append('WILSON_LOWER_NOT_ABOVE_GLOBAL_TP')
        if enough and not stable:failures.append('NOT_STABLE_IN_BOTH_HALVES')
        rows.append(dict(rebalance_date=pd.Timestamp(cutoff),symbol=symbol,side=side,
            episodes=n,tp_count=wins,tp_rate=float(g.tp_first.mean()),wilson90_lower=lower,
            mean_net_outcome=mean,global_tp_rate=base['tp'],global_mean_net=base['net'],
            first_half_tp=float(a.tp_first.mean()) if len(a) else None,
            second_half_tp=float(b.tp_first.mean()) if len(b) else None,
            max_known_maturity=g.last_path_date.max(),passed=passed,
            qualification='PASS_EXPLORATORY' if passed else 'INSUFFICIENT_HISTORY' if not enough else 'NOT_QUALIFIED',
            reasons=';'.join(failures)))
    return pd.DataFrame(rows), history


def apply_states(current, states):
    """Freeze membership before test labels. A both-sides pass means abstention."""
    result=current.copy()
    lookup={(r.symbol,r.side):bool(r.passed) for r in states.itertuples()}
    result['symbol_pass']=[lookup.get((s,t),False) for s,t in zip(result.symbol,result.side)]
    result['opposite_pass']=[lookup.get((s,'SHORT' if t=='LONG' else 'LONG'),False) for s,t in zip(result.symbol,result.side)]
    result['chosen_side']=result.symbol_pass & ~result.opposite_pass
    return result


def chosen(frame,arm):
    if arm=='SELECT_SIDE':return frame[frame.chosen_side]
    side='LONG' if arm.endswith('LONG') else 'SHORT'
    mask=frame.side.eq(side)
    if arm.startswith('SYMBOL_'):mask &= frame.symbol_pass
    return frame[mask]


def block_interval(series, days):
    x=series.dropna().sort_index()
    if x.empty:return dict(delta=None,ci95=[None,None],blocks=0,dates=0)
    origin=days.searchsorted(pd.Timestamp(f'{x.index.min().year}-01-01'))
    blocks=(days.get_indexer(x.index)-origin)//20
    means=x.groupby(blocks).mean().to_numpy()
    interval=[None,None]
    if len(means)>=5:
        rng=np.random.default_rng(20261019)
        samples=rng.choice(means,size=(2000,len(means)),replace=True).mean(axis=1)
        interval=[float(v) for v in np.quantile(samples,[.025,.975])]
    return dict(delta=float(x.mean()),ci95=interval,blocks=len(means),dates=len(x))


def summarize(frame,days):
    result=[]
    for year,part in frame.groupby(frame.date.dt.year):
        denominator=len(part)//2;date_n=part.date.nunique()
        for arm in ARMS:
            sub=chosen(part,arm)
            daily=sub.groupby('date')[['tp_first','net_outcome','terminal_direction_right']].mean()
            ref_side='SHORT' if arm.endswith('SHORT') else 'LONG'
            base=part[part.side.eq(ref_side)].groupby('date')[['tp_first','net_outcome']].mean()
            common=daily.index
            comparisons={}
            for metric in ('tp_first','net_outcome'):
                comparisons[metric]=block_interval(daily[metric]-base[metric].reindex(common),days)
            # Identical selected symbol/date pairs, blindly always LONG or SHORT.
            controls={}
            if arm=='SELECT_SIDE' and len(sub):
                keys=sub[['date','symbol']]
                for side in ('LONG','SHORT'):
                    blind=keys.merge(part[part.side.eq(side)],on=['date','symbol'],validate='one_to_one')
                    controls[side]=dict(n=len(blind),tp_rate=float(blind.tp_first.mean()),
                        mean_net=float(blind.net_outcome.mean()),
                        paired_net_gain=block_interval(daily.net_outcome-blind.groupby('date').net_outcome.mean(),days))
            result.append(dict(year=int(year),arm=arm,n=len(sub),symbols=int(sub.symbol.nunique()),
                dates=int(len(daily)),all_dates=int(date_n),coverage=len(sub)/denominator,
                days_abstained=int(date_n-len(daily)),
                tp_rate=float(sub.tp_first.mean()) if len(sub) else None,
                daily_tp_rate=float(daily.tp_first.mean()) if len(sub) else None,
                sl_rate=float(sub.sl_first.mean()) if len(sub) else None,
                profitable_rate=float(sub.net_outcome.gt(0).mean()) if len(sub) else None,
                mean_net_outcome=float(sub.net_outcome.mean()) if len(sub) else None,
                daily_mean_net=float(daily.net_outcome.mean()) if len(sub) else None,
                daily_terminal_right=float(daily.terminal_direction_right.mean()) if len(sub) else None,
                selected_side_counts={k:int(v) for k,v in sub.side.value_counts().items()},
                comparisons_to_all= comparisons,same_stocks_blind_side=controls,
                largest_symbol_counts={k:int(v) for k,v in sub.symbol.value_counts().head(5).items()}))
    return result


def independent_test_summary(frame):
    """Thin each arm separately by full windows; no profitable re-entry selection."""
    rows=[]
    for year,g in frame.groupby(frame.date.dt.year):
        for arm in ARMS:
            subset=independent_episodes(chosen(g,arm))
            rows.append(dict(year=int(year),arm=arm,n=len(subset),symbols=int(subset.symbol.nunique()),
                tp_count=int(subset.tp_first.sum()),
                tp_rate=float(subset.tp_first.mean()) if len(subset) else None,
                profitable_rate=float(subset.net_outcome.gt(0).mean()) if len(subset) else None,
                mean_net_outcome=float(subset.net_outcome.mean()) if len(subset) else None,
                counts={k:int(v) for k,v in subset.symbol.value_counts().items()}))
    return rows


def prepare(output):
    output.mkdir(parents=True,exist_ok=False)
    report=read(SOURCE/'report.json')
    verify_hashes(SOURCE,report['files'])
    if report['status']!='COMPLETED_EXPLORATORY_NO_PROMOTION':raise ValueError('Unqualified source study')
    source_protocol=read(SOURCE/'protocol.json')
    if digest(SOURCE/'protocol.json')!=report['protocol_sha256']:raise ValueError('Changed source protocol')
    paths=[Path(__file__),Path('tests/test_us_top10_symbol_reliability.py'),
           SOURCE/'report.json',SOURCE/'protocol.json',SOURCE/'observations.parquet']
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),source=str(SOURCE),
        source_hashes={str(p):digest(p) for p in paths},models=source_protocol['models'],
        target='TP20_BEFORE_SL7_OR_EXPIRY20_ENTRY_INCLUDED',training_year=2024,test_years=[2025,2026],
        monthly_rebalance='first observed NYSE decision session of month; label maturity strictly before this date',
        lookback_sessions=504,minimum_independent_episodes=MIN_EPISODES,
        independent_selection='earliest chronological same-symbol/same-side entry; next only after full 20-session window',
        gate='Wilson two-sided90 lower TP rate > past global same-side TP rate; mean net > max(0,global net); both chronological halves positive net and TP rate > past global',
        no_tuning=True,both_sides_pass='abstain for SELECT_SIDE',unseen_symbols='unknown, never selected',
        fee_assumptions=dict(per_leg_commission_bps=1,per_leg_half_spread_bps=5,per_leg_slippage_bps=2,
            borrow_annual=BORROW_ANNUAL,borrow_basis='entry notional * (exit session - 1)/252'),
        comparison='same-date whole TOP10 plus identical selected symbols forced LONG/SHORT',
        no_gpt_or_consensus_used=True,no_model_fit=True,no_production_universe_change=True,
        sql=False,provider_calls=False,orders=False,economic_portfolio_backtest=False,
        caveats=['Already explored years; temporal split not untouched independent holdout.',
            'Symbol side affinity, not proof that GPT/news or a directional ML model predicts that ticker.',
            'Eight episodes are a minimum exploratory support, not proof; intervals not multiplicity-corrected across symbols.',
            'Monthly symbols can disappear from future TOP10; no replacement outside its original ten.',
            'Repeated overlapping test entries; no capital compounding, portfolio sizing or reinforcement rules.',
            'Hypothetical proportional execution/borrow costs; no certified historic fills, locates or recalls.',
            'Current survivor universe and archived retrospective split-adjusted prices; source quality caveats retained.',
            '2026 decisions mature only through 1 September; data observation limit 30 September.'])
    atomic_json(output/'protocol.json',protocol)
    return protocol


def run(output):
    protocol=read(output/'protocol.json');verify_hashes(Path('.'),protocol['source_hashes'])
    if (output/'report.json').exists():raise ValueError('Immutable completed output exists')
    f=attach_costs(pd.read_parquet(SOURCE/'observations.parquet'))
    from modelFactory.oracle.build_labels import nyse_sessions
    days=nyse_sessions('2023-01-01','2026-10-09')
    # Decision fields alone choose the schedule; never future outcome values.
    tests=f[f.date.dt.year.isin(protocol['test_years'])]
    schedule=tests.groupby(tests.date.dt.to_period('M')).date.min().sort_values()
    memberships=[];evaluations=[];audit=[]
    for i,cutoff in enumerate(schedule,1):
        states,history=states_at(f,cutoff,days)
        if not states.empty:
            if not states.max_known_maturity.lt(cutoff).all():raise AssertionError('Immature history leakage')
            memberships.append(states)
        month=tests[tests.date.dt.to_period('M').eq(cutoff.to_period('M'))]
        selected=apply_states(month,states)
        selected['rebalance_date']=cutoff;evaluations.append(selected)
        audit.append(dict(date=cutoff,history_rows=len(history),history_max_date=history.date.max(),
            max_known_maturity=history.last_path_date.max(),qualified_states=int(states.passed.sum()) if not states.empty else 0,
            enough_history_states=int(states.episodes.ge(MIN_EPISODES).sum()) if not states.empty else 0,
            states_with_history=len(states)))
        LOG.info('Rebalance %s: %d qualified states, %d have >=8 independent episodes',
                 cutoff.date(),audit[-1]['qualified_states'],audit[-1]['enough_history_states'])
        atomic_json(output/'progress.json',dict(status='RUNNING',completed=i,total=len(schedule),rebalance=str(cutoff.date())))
    evaluated=pd.concat(evaluations,ignore_index=True)
    states=pd.concat(memberships,ignore_index=True)
    evaluated.to_parquet(output/'evaluations.parquet',index=False)
    states.to_parquet(output/'monthly-memberships.parquet',index=False)
    states.to_csv(output/'monthly-memberships.csv',index=False)
    selected=evaluated[evaluated.chosen_side]
    selected.to_csv(output/'selected-occasions.csv',index=False)
    summary=summarize(evaluated,days)
    independent=independent_test_summary(evaluated)
    pd.DataFrame(independent).to_csv(output/'nonoverlapping-test-summary.csv',index=False)
    temporal=[]
    for (year,half),part in evaluated.groupby([evaluated.date.dt.year,(evaluated.date.dt.month>6).astype(int)+1]):
        for arm in ARMS:
            sub=chosen(part,arm)
            temporal.append(dict(year=int(year),half=int(half),arm=arm,n=len(sub),symbols=int(sub.symbol.nunique()),
                tp_rate=float(sub.tp_first.mean()) if len(sub) else None,
                mean_net_outcome=float(sub.net_outcome.mean()) if len(sub) else None))
    pd.DataFrame(temporal).to_csv(output/'semester-summary.csv',index=False)
    pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in summary]).to_csv(output/'summary.csv',index=False)
    # Pure outcome-order selection, no additional liquidity or cap filter.
    diagnostics=[]
    for (year,side),g in states.groupby([states.rebalance_date.dt.year,'side']):
        diagnostics.append(dict(year=int(year),side=side,states=len(g),
            enough_history=int(g.episodes.ge(MIN_EPISODES).sum()),qualified=int(g.passed.sum()),
            largest_episode_count=int(g.episodes.max()),
            failures={k:int(v) for k,v in g.qualification.value_counts().items()}))
    report=dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',protocol_sha256=digest(output/'protocol.json'),
        initial_history_year=2024,evaluated_decision_rows=len(evaluated)//2,summary=summary,
        nonoverlapping_test_summary=independent,semester_summary=temporal,
        monthly_audit=audit,history_support=diagnostics,
        qualified_states=states[states.passed][['rebalance_date','symbol','side','episodes','tp_rate','wilson90_lower','global_tp_rate','mean_net_outcome']].to_dict('records'),
        selected_occasions=len(selected),
        sensitivity_excluding_ambiguous=summarize(evaluated[~evaluated.ambiguity],days),
        files={n:digest(output/n) for n in ['evaluations.parquet','monthly-memberships.parquet','monthly-memberships.csv','selected-occasions.csv','summary.csv','nonoverlapping-test-summary.csv','semester-summary.csv']},
        interpretation='Selection of past symbol/side affinities with costs, not a directional ML/GPT accuracy study or portfolio PnL.')
    verify_hashes(Path('.'),protocol['source_hashes'])
    atomic_json(output/'report.json',report)
    atomic_json(output/'progress.json',dict(status=report['status'],completed=len(schedule),total=len(schedule)))
    LOG.info('Completed %d decisions; %d selected occasions',len(evaluated)//2,len(selected))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=['prepare','run'],required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    {'prepare':prepare,'run':run}[args.phase](args.output)


if __name__=='__main__':main()
