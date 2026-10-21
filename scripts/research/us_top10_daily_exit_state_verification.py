"""Offline verification of daily state chronology, features and counterfactual labels."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_top10_daily_exit_state_audit as study
from scripts.research import us_top10_three_session_confirmation_audit as scalar_reference
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def verify(root):
    p=study.READ(root/'protocol.json'); ready=study.READ(root/'data-ready.json'); report=study.READ(root/'report.json')
    verify_hashes(Path('.'),p['sources']); verify_hashes(root,ready['files']); verify_hashes(root,report['files'])
    assert report['protocol_sha256']==digest(root/'protocol.json')
    trades=pd.read_parquet(root/'baseline-trades.parquet'); states=pd.read_parquet(root/'position-states.parquet')
    source=pd.read_parquet(study.SOURCE/'evaluations.parquet'); source=source[source.side.eq('LONG')&source.direction.eq('LONG')]
    columns=list(source.columns); key=['date','symbol']
    pd.testing.assert_frame_equal(source[columns].sort_values(key).reset_index(drop=True),trades[columns].sort_values(key).reset_index(drop=True))
    assert len(trades)==ready['baseline_trades'] and len(states)==ready['states']
    assert not states.duplicated(['trade_id','state_date']).any()
    assert set(study.FEATURES).isdisjoint(study.LABELS+['baseline_winner','baseline_stopped','next_open_priority','immediate_exit_net','keep_remaining_net','keep_next3_net'])
    assert states.state_date.lt(states.execution_date).all()
    assert states.execution_date.le(states.last_path_date).all() and states.last_path_date.lt(states.label_available_date).all()
    np.testing.assert_allclose(states.groupby('trade_id').weight.sum(),1.,atol=1e-12)
    independent=study.parent.previous.execution.base.independent_fast(trades)
    assert states.independent_trade.eq(states.trade_id.isin(set(independent.trade_id))).all()
    discovery=study.discovery_states(states)
    assert discovery.label_available_date.lt('2025-01-01').all() and discovery.signal_year.eq(2024).all()
    assert len(discovery)==report['discovery_states'] and discovery.trade_id.nunique()==report['discovery_trades']
    contracts=study.READ(root/'2024-feature-contract.json')['features']
    for feature in study.FEATURES:
        d=discovery[np.isfinite(discovery[feature])]
        assert contracts[feature]['cuts']==study.weighted_quantiles(d[feature],d.weight)
        d=d.copy(); d['bin']=study.cut_bins(d[feature],contracts[feature]['cuts'])
        for label in study.LABELS:
            means={int(k):study.weighted_mean(g[label],g.weight) for k,g in d.groupby('bin')}
            low=0; high=len(contracts[feature]['cuts']); chosen=low if means.get(low,-np.inf)>=means.get(high,-np.inf) else high
            assert contracts[feature]['tails'][label]['bin']==chosen
    days=nyse_sessions('2023-01-01','2026-10-09')
    raw=pd.read_parquet(p['prices'],filters=[('symbol','in',sorted(set(trades.symbol)|{'SPY'}))])
    groups={str(s):g for s,g in raw.groupby('symbol',observed=True)}
    spy_raw=groups['SPY'].set_index('date').reindex(days)
    spy=spy_raw.adj_close.where(spy_raw.is_filled.eq(0)&spy_raw.volume.gt(0))
    assert spy.dropna().gt(0).all()
    native_checked=0; label_checked=0; prefix_checked=0
    for symbol,t in trades.groupby('symbol',observed=True):
        pos=days.get_indexer(t.date)
        grid,direction,reasons=study.parent.qualify(groups[str(symbol)],days,pos,
            identity_events=p['identity_events'].get(str(symbol),[]),price_reserve=p['price_reserves'].get(str(symbol)))
        assert (direction=='LONG').all() and (reasons=='').all()
        f=study.price_features(grid,spy)
        s=states[states.symbol.eq(symbol)]
        for row in t.itertuples():
            start=days.get_loc(row.entry_date); last=days.get_loc(row.last_path_date)
            native=scalar_reference.scalar(grid.iloc[start:last+1],row.side)
            assert native['outcome']==row.outcome and native['exit_session']==row.exit_session
            assert abs(native['exit_price']-row.exit_price)<1e-12
            own=s[s.trade_id.eq(row.trade_id)]
            assert len(own)==row.exit_session-1
            for state in own.itertuples():
                cur=days.get_loc(state.state_date); nxt=cur+1
                assert cur==start+state.holding_age-1
                assert cur<start+row.exit_session-1 and state.holding_age<10
                entry=row.entry_price; stop=.95*entry; tp=1.1*entry; op=float(grid.open.iloc[nxt])
                priority='SL_GAP' if op<=stop+abs(stop)*1e-12 else ('TP_AT_OPEN' if op>=tp-abs(tp)*1e-12 else 'NONE')
                now=tp if priority=='TP_AT_OPEN' else op
                keep3=row.exit_price if start+row.exit_session-1<=min(cur+3,last) else float(grid.close.iloc[min(cur+3,last)])
                assert priority==state.next_open_priority
                expected_now=now/entry-1-p['costs_per_leg']*(1+now/entry)
                expected3=keep3/entry-1-p['costs_per_leg']*(1+keep3/entry)
                assert abs(state.immediate_exit_net-expected_now)<1e-12
                assert abs(state.exit_advantage_remaining-(expected_now-row.net_outcome))<1e-12
                assert abs(state.exit_advantage_next3-(expected_now-expected3))<1e-12
                if priority!='NONE': assert abs(state.exit_advantage_remaining)<1e-12 and abs(state.exit_advantage_next3)<1e-12
                assert state.label_available_date==days[last+1]
                label_checked+=1
            native_checked+=1
        # One full-prefix check per represented symbol, plus all states covered by tests/causal formulas.
        if len(s):
            date=s.state_date.iloc[len(s)//2]; j=days.get_loc(date)
            prefix=study.price_features(grid.iloc[:j+1],spy.iloc[:j+1])
            pd.testing.assert_frame_equal(prefix,f.iloc[:j+1]); prefix_checked+=1
    assert native_checked==len(trades) and label_checked==len(states)
    robustness=[]
    rng=np.random.default_rng(20261019)
    for candidate in report['candidates']:
        if not candidate['all_years_and_populations_positive_descriptive']: continue
        feature=candidate['feature']; label=candidate['label']; contract=contracts[feature]
        chosen=contract['tails'][label]['bin']
        for population in ('ALL_STATES','NONOVERLAPPING_TRADES'):
            for year in (2024,2025,2026):
                values=discovery.copy() if year==2024 else states[states.signal_year.eq(year)].copy()
                if population=='NONOVERLAPPING_TRADES': values=values[values.independent_trade]
                values=values[np.isfinite(values[feature])]
                tail=values[study.cut_bins(values[feature],contract['cuts'])==chosen].copy()
                exact_age=values.copy()
                exact_age['context']=exact_age.holding_age.astype(str)+'_'+np.where(exact_age.current_pnl.lt(0),'NEG','NONNEG')
                exact_mask=pd.Series(study.cut_bins(exact_age[feature],contract['cuts'])==chosen,index=exact_age.index)
                origin=days.searchsorted(pd.Timestamp(f'{year}-01-01'))
                blocks=(days.get_indexer(tail.entry_date)-origin)//20
                aggregate=pd.DataFrame(dict(block=blocks,weighted=tail[label]*tail.weight,weight=tail.weight)).groupby('block')[['weighted','weight']].sum()
                interval=[None,None]
                if len(aggregate)>=5:
                    draws=rng.integers(0,len(aggregate),size=(2000,len(aggregate)))
                    sums=aggregate.to_numpy()[draws].sum(axis=1)
                    estimates=sums[:,0]/sums[:,1]
                    interval=[float(v) for v in np.quantile(estimates,[.025,.975])]
                weights=tail.groupby('symbol').weight.sum().sort_values(ascending=False)
                loo=[study.weighted_mean(g[label],g.weight) for symbol in tail.symbol.unique() if len(g:=tail[tail.symbol.ne(symbol)])]
                after_first=tail[tail.holding_age.ge(2)]
                robustness.append(dict(feature=feature,label=label,population=population,year=year,
                    tail_trades=tail.trade_id.nunique(),symbols=tail.symbol.nunique(),entry_blocks=len(aggregate),
                    tail_mean=study.weighted_mean(tail[label],tail.weight),entry_block_ci95=interval,
                    min_leave_one_symbol_out_mean=min(loo) if loo else None,
                    exact_age_pnl_sign_context_delta=study.context_delta(exact_age,exact_mask,label),
                    top3_symbol_weight_fraction=float(weights.head(3).sum()/weights.sum()),
                    after_entry_day_trades=after_first.trade_id.nunique(),
                    after_entry_day_mean=study.weighted_mean(after_first[label],after_first.weight),
                    reserve='Post-screen robustness, descriptive uncorrected intervals; neither an exit policy nor independent confirmation'))
    atomic_json(root/'candidate-robustness.json',dict(rows=robustness,
        interpretation='Bootstrap groups all states of a trade in its entry20-session block; few blocks and multiple testing limit inference'))
    result=dict(status='PASS_EXPLORATORY_AUDIT_ONLY',baseline_trades=native_checked,states_labels_checked=label_checked,
        symbol_prefix_checks=prefix_checked,full_window_label_purge=True,grouped_position_weights=True,
        future_open_protection_states_retained=True,no_model_trained=True,no_exit_policy_replayed=True,
        protocol_sha256=digest(root/'protocol.json'),report_sha256=digest(root/'report.json'),
        candidate_robustness_sha256=digest(root/'candidate-robustness.json'),
        audit_code_sha256=digest(Path(__file__)),scalar_reference_sha256=digest(Path(scalar_reference.__file__)),
        sql=False,api_calls=0,production_changes=False,
        reserve='Descriptive feature screen across40 hypotheses; not independent prospective confirmation or profitable strategy')
    atomic_json(root/'final-audit.json',result); return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    print(verify(parser.parse_args().output))
