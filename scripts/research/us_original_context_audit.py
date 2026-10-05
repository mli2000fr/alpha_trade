"""Fixed lagged contexts on archived Oracle/directional candidates. Read-only."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from scripts.research.us_original_directional_monthly_audit import long_mask

BASE = Path('artifacts/research/us_common_degradation/original-monthly-20261005-v1')
SECTOR = Path('artifacts/research/us_atr_oracle_sentiment/sector-breadth-confirmation-20261004-v1/sector_context.parquet')
ROOT = Path('artifacts/research/us_common_degradation/original-context-20261005-v1')


def lag_on_sessions(frame, sessions):
    """Map J observations to next calendar session; never fill missing sessions."""
    mapping = pd.DataFrame({'observed_date': sessions[:-1], 'date': sessions[1:]})
    return frame.rename(columns={'date':'observed_date'}).merge(mapping, on='observed_date',
        how='inner', validate='many_to_one')


def statistics(group):
    valid = group[group.target_quality_valid.eq(1) & group.future_return.notna()
                  & group.oracle_decile.notna()]
    daily = valid.groupby('date').future_return.mean()
    return dict(rows=len(group), evaluated=len(valid), days=len(daily), symbols=valid.symbol.nunique(),
        mean_return_pct=float(100*valid.future_return.mean()) if len(valid) else None,
        daily_mean_return_pct=float(100*daily.mean()) if len(daily) else None,
        positive_days=int(daily.gt(0).sum()), negative_days=int(daily.lt(0).sum()),
        d1_pct=float(100*valid.oracle_decile.eq(1).mean()) if len(valid) else None,
        d10_pct=float(100*valid.oracle_decile.eq(10).mean()) if len(valid) else None)


def fixed_contexts(frame):
    # These are descriptive partitions, not optimized thresholds or validated vetoes.
    normal = frame['mode'].isin(['normal','capital_preservation','close_only','cash_only']) & frame.allow_new_entries.notna()
    return {
        'REGIME_NORMAL_ENTRIES': (normal, frame['mode'].eq('normal') & frame.allow_new_entries.eq(1)),
        'VIX_CURVE_NOT_INVERTED': (frame.term.notna(), frame.term.le(1)),
        'SPY_RET20_NONNEGATIVE': (frame.spy_ret20.notna(), frame.spy_ret20.ge(0)),
        'SECTOR_RELATIVE_POSITIVE': (frame.relative20.notna(), frame.relative20.gt(0)),
        'SECTOR_BREADTH_MAJORITY': (frame.breadth20.notna(), frame.breadth20.gt(.5)),
        'RELATIVE_AND_BREADTH': (frame.relative20.notna() & frame.breadth20.notna(),
                                frame.relative20.gt(0) & frame.breadth20.gt(.5)),
    }


def compare(group):
    results={}
    for name,(known,keep) in fixed_contexts(group).items():
        known_base=group[known]
        kept=group[known & keep]
        removed=group[known & ~keep]
        valid=known_base.target_quality_valid.eq(1)&known_base.future_return.notna()&known_base.oracle_decile.notna()
        good=valid & known_base.future_return.gt(0)
        bad=valid & known_base.future_return.lt(0)
        kept_indices=set(kept.index)
        removed_good=int((good & ~known_base.index.isin(kept_indices)).sum())
        removed_bad=int((bad & ~known_base.index.isin(kept_indices)).sum())
        results[name]=dict(known=statistics(known_base), kept=statistics(kept), removed=statistics(removed),
            unknown=statistics(group[~known]), positive_events_removed=removed_good,
            positive_events_removed_pct=100*removed_good/int(good.sum()) if good.any() else None,
            negative_events_removed=removed_bad,
            negative_events_removed_pct=100*removed_bad/int(bad.sum()) if bad.any() else None,
            cash_zero_return_same_initial_event_budget_pct=float(100*kept.loc[
                kept.target_quality_valid.eq(1)&kept.future_return.notna()&kept.oracle_decile.notna(),
                'future_return'].sum()/valid.sum()) if valid.any() else None)
    return results


def run():
    ROOT.mkdir(parents=True,exist_ok=False)
    protocol=dict(lag='previous SPY trading session, no forward fill', price_window=20,
        comparison_end='2026-03-31', sector_metadata='current, non PIT, leave-one-out >=20 peers',
        no_training=True,no_sql_writes=True,no_threshold_optimization=True,
        historical_per_symbol_scope='2024-07 to 2025-12 only; not 2020-2025',
        six_rules=list(fixed_contexts(pd.DataFrame(columns=['mode','allow_new_entries','term','spy_ret20','relative20','breadth20']))))
    (ROOT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    data=pd.read_parquet(BASE/'joined_diagnostic.parquet')
    data=data[data.date.le('2026-03-31')].copy()
    sector=pd.read_parquet(SECTOR)
    sector.date=pd.to_datetime(sector.date)
    engine=get_sqlalchemy_engine()
    symbols=pd.read_parquet(Path('artifacts/research/us_common_degradation/audit-20261005-v1/original_batch_registry.parquet')).symbols.iloc[0]
    symbols=[s.strip() for s in symbols.split(',')]+['SPY']
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise ValueError('US database required')
        macro=pd.read_sql(text("SELECT trade_date AS date,mode,allow_new_entries,vix,vxn,vix3m,move,created_at,updated_at FROM stock_macro_indicators_daily WHERE trade_date BETWEEN '2023-01-01' AND '2026-03-31'"),conn)
        query=text("SELECT date,symbol,close,adj_close,data_source FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN '2023-01-01' AND '2026-03-31'").bindparams(bindparam('symbols',expanding=True))
        bars=pd.read_sql(query,conn,params={'symbols':sorted(set(symbols))})
    bars.date=pd.to_datetime(bars.date)
    macro.date=pd.to_datetime(macro.date)
    if bars.duplicated(['date','symbol']).any() or macro.date.duplicated().any():
        raise ValueError('Ambiguous context keys')
    bars['price']=bars.adj_close.where(bars.adj_close.gt(0),bars.close).where(bars.close.gt(0))
    prices=bars.pivot(index='date',columns='symbol',values='price').sort_index()
    sessions=pd.DatetimeIndex(bars[bars.symbol.eq('SPY')].date.sort_values())
    prices=prices.reindex(sessions)
    market=pd.DataFrame({'date':sessions,'spy_ret20':(prices.SPY/prices.SPY.shift(20)-1).to_numpy()})
    returns=prices.pct_change(fill_method=None)
    spy=returns.SPY
    betas={name:returns[name].rolling(252,min_periods=252).cov(spy)/spy.rolling(252,min_periods=252).var()
           for name in prices if name!='SPY'}
    beta=pd.DataFrame(betas).rename_axis(index='date',columns='symbol').stack().rename('beta252').reset_index()
    macro['term']=macro.vix/macro.vix3m.where(macro.vix3m.gt(0))
    market=market.merge(macro,on='date',how='left',validate='one_to_one')
    market=lag_on_sessions(market,sessions).rename(columns={'observed_date':'market_observed_date'})
    sector_lag=lag_on_sessions(sector,sessions).rename(columns={'observed_date':'sector_observed_date'})
    beta_lag=lag_on_sessions(beta,sessions).rename(columns={'observed_date':'beta_observed_date'})
    data=data.merge(market,on='date',how='left',validate='many_to_one').merge(
        sector_lag,on=['date','symbol'],how='left',validate='one_to_one').merge(
        beta_lag,on=['date','symbol'],how='left',validate='one_to_one')
    for col in ['market_observed_date','sector_observed_date','beta_observed_date']:
        if not (data[col].isna()|data[col].lt(data.date)).all():
            raise ValueError('Context not prior to signal')
    pools={'ORACLE_TOP20':data,'ORACLE_SERVABLE':data[data._merge.eq('both')],
           'ORACLE_FIXED_LONG':data[data._merge.eq('both') & long_mask(data)]}
    reports={}
    for name,pool in pools.items():
        monthly=[]
        concentration={}
        for month,g in pool.groupby(pool.date.dt.strftime('%Y-%m')):
            counts=g.symbol.value_counts()
            monthly.append(dict(month=month,**statistics(g),
                vix_previous_mean=float(g.groupby('date').vix.mean().mean()),
                term_previous_mean=float(g.groupby('date').term.mean().mean()),
                spy_ret20_previous_mean=float(g.groupby('date').spy_ret20.mean().mean()),
                relative20_previous_mean=float(g.relative20.mean()),
                breadth20_previous_mean=float(g.breadth20.mean()),
                beta252_mean=float(g.beta252.mean()), beta252_coverage_pct=float(100*g.beta252.notna().mean()),
                top5_event_share_pct=float(100*counts.head(5).sum()/len(g)),
                regime_previous_counts=g.groupby('date')['mode'].first().value_counts().to_dict()))
            bysymbol=g[g.target_quality_valid.eq(1)].groupby('symbol').agg(
                events=('future_return','size'),mean_return=('future_return','mean'),sum_return=('future_return','sum'))
            bysymbol['contribution_event_mean_pct']=100*bysymbol.sum_return/len(g)
            concentration[month]=bysymbol.sort_values('contribution_event_mean_pct').reset_index().to_dict('records')
        reports[name]=dict(monthly=monthly,concentration=concentration,
            windows={label:compare(pool[mask]) for label,mask in {
                '2024H2':pool.date.lt('2025-01-01'),
                '2025H1':pool.date.ge('2025-01-01')&pool.date.lt('2025-07-01'),
                '2025H2':pool.date.ge('2025-07-01')&pool.date.lt('2026-01-01'),
                '2026Q1':pool.date.ge('2026-01-01')}.items()},
            months={m:compare(g) for m,g in pool.groupby(pool.date.dt.strftime('%Y-%m'))})
    data.to_parquet(ROOT/'context_candidates.parquet',index=False)
    payload=dict(status='COMPLETED_DESCRIPTIVE_NOT_VALIDATED_VETO',populations=reports,
        sector_context_source=str(SECTOR),original_batch='model-factory-20260903174624-014164',
        notes=['Current adjusted prices and sector metadata, not vintage-certified',
            'Macro economic dates lagged one session do not establish publication availability',
            'No net portfolio replay, no historical 2020-2024 per-symbol predictions',
            'Overlapping returns; positive days removed are descriptive, not profit sacrificed',
            'Context missing remains unknown; never counted as observed adverse regime',
            'Rules fixed but years previously inspected; no pristine OOS claim'])
    (ROOT/'report.json').write_text(json.dumps(payload,default=str,indent=2),encoding='utf-8')
    print('COMPLETED',ROOT,flush=True)
    print(pd.DataFrame(reports['ORACLE_FIXED_LONG']['monthly']).to_string(index=False),flush=True)
    for window,results in reports['ORACLE_FIXED_LONG']['windows'].items():
        for rule,r in results.items():
            print(window,rule,'base',r['known']['daily_mean_return_pct'],'kept',r['kept']['daily_mean_return_pct'],
                  'removed',r['removed']['days'],'good_removed',r['positive_events_removed_pct'],flush=True)


if __name__=='__main__':
    run()
