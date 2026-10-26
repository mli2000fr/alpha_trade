"""Fixed n=1/n=3 revenue confirmation and inverse-news exit, research only."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_consensus_reliability_20261022 as parent
from scripts.research.us_consensus_reliability_sip_20261022 import CHILD as SOURCE

ROOT=Path('artifacts/research/us_consensus_confirmation_exit/20261022-v1')
PROTOCOL=Path('doc/ml/consensus_confirmation_sortie_protocole_20261022.md')
PROTECTIONS=Path('config/research/us_consensus_revenue_h10_evaluation_20261020.json')
ARMS=('A_ONE_CHANGE_FIXED','B_THREE_CHANGES_FIXED','C_THREE_CHANGES_INVERSE_EXIT')


def eligible(row):
    return (bool(row.revenue_technical_ok) and row.revenue_count_group=='UNCHANGED_COUNT'
        and row.old_revenue_count==row.new_revenue_count and row.new_revenue_count>=3
        and np.isfinite(row.new_revenue_count) and row.revenue_sign in (-1,1))


def confirmation(frame):
    f=frame.copy().sort_values(['entry_idx','symbol']).reset_index(drop=True)
    if f.duplicated(['symbol','entry_idx']).any():raise ValueError('Duplicate decision')
    lookup={(r.symbol,r.entry_idx):r for r in f.itertuples()}
    signs=[];reasons=[]
    for row in f.itertuples():
        window=[lookup.get((row.symbol,i)) for i in range(row.entry_idx-2,row.entry_idx+1)]
        reason='PASS'
        if any(r is None for r in window):reason='MISSING_CONSECUTIVE_SESSION'
        elif not all(eligible(r) for r in window):reason='ZERO_MISSING_OR_UNQUALIFIED_CHANGE'
        elif len({r.revenue_sign for r in window})!=1:reason='OPPOSITE_CHANGES'
        elif len({r.fiscal_anchor for r in window})!=1:reason='FISCAL_ROLLOVER'
        elif len({r.new_revenue_count for r in window})!=1:reason='ANALYST_COUNT_CHANGED'
        elif not all(window[i].new_id==window[i+1].old_id for i in (0,1)):
            reason='NOT_FOUR_LINKED_OBSERVATIONS'
        signs.append(row.revenue_sign if reason=='PASS' else 0)
        reasons.append(reason)
    f['one_sign']=[r.revenue_sign if eligible(r) else 0 for r in f.itertuples()]
    f['three_sign']=signs
    f['confirmation_reason']=reasons
    return f


def first_inverse(entry,lookup,end_idx):
    for i in range(entry.entry_idx+1,end_idx+1):
        new=lookup.get((entry.symbol,i))
        if (new is not None and eligible(new) and new.revenue_sign==-entry.three_sign
            and new.fiscal_anchor==entry.fiscal_anchor and new.new_revenue_count==entry.new_revenue_count):
            if not new.new_available<new.entry_open:raise ValueError('Inverse not known before open')
            return i
    return None


def replay(bars,sign,tp=.1,sl=.05,inverse_offset=None):
    """Entire common window validated by caller; inverse index is zero-based."""
    if sign not in (-1,1) or not len(bars):raise ValueError('Side/path required')
    entry=float(bars.iloc[0].open)
    stop=entry*(1-sign*sl);target=entry*(1+sign*tp)
    for i,r in enumerate(bars.itertuples()):
        o,h,l=float(r.open),float(r.high),float(r.low)
        stop_gap=o<=stop if sign==1 else o>=stop
        tp_gap=o>=target if sign==1 else o<=target
        stop_hit=l<=stop if sign==1 else h>=stop
        tp_hit=h>=target if sign==1 else l<=target
        if stop_gap:price,reason=o,'STOP_GAP'
        elif tp_gap:price,reason=target,'TP_GAP_CAPPED'
        elif inverse_offset is not None and i==inverse_offset:price,reason=o,'INVERSE_AT_OPEN'
        elif stop_hit:price,reason=stop,'STOP_TOUCH_BOTH' if tp_hit else 'STOP_TOUCH'
        elif tp_hit:price,reason=target,'TP_TOUCH'
        else:continue
        return dict(entry_price=entry,exit_price=price,gross_pct=sign*(price/entry-1)*100,
            exit_reason=reason,exit_offset=i,
            full_sessions_held=i if reason in ('STOP_GAP','TP_GAP_CAPPED','INVERSE_AT_OPEN') else i+1)
    return dict(entry_price=entry,exit_price=float(bars.iloc[-1].close),
        gross_pct=sign*(float(bars.iloc[-1].close)/entry-1)*100,exit_reason='HORIZON_CLOSE',
        exit_offset=len(bars)-1,full_sessions_held=len(bars))


def prepare(root):
    if root.exists():raise FileExistsError('Fresh immutable directory required')
    parent.check(SOURCE)
    report=parent.read(SOURCE/'report.json')
    for n,h in report['files'].items():
        if parent.digest(SOURCE/n)!=h:raise ValueError('Parent snapshot changed')
    risk=parent.read(PROTECTIONS)
    if risk['take_profit_pct']!=.1 or risk['stop_loss_pct']!=.05:raise ValueError('Existing consensus contract changed')
    root.mkdir(parents=True)
    files=[Path(__file__),PROTOCOL,PROTECTIONS,SOURCE/'features.parquet',SOURCE/'protocol.json',
           SOURCE/'report.json',SOURCE/'clock-audit/report.json',
           Path('tests/test_us_consensus_confirmation_exit_20261022.py'),
           Path('scripts/research/us_consensus_reliability_20261022.py')]
    p=dict(version='CONSENSUS_CONFIRMATION_INVERSE_EXIT_V1',source=str(SOURCE),
        feature_cutoff_utc=parent.read(SOURCE/'protocol.json')['cutoff_utc'],
        price_cutoff_utc=datetime.now(timezone.utc).isoformat(),
        n=3,tp=.1,sl=.05,primary_horizon=5,secondary_horizons=[1,3],
        h10_maturity_only=True,fees_assumed_roundtrip_bps=16,
        sources={str(p):parent.digest(p) for p in files},sql_writes=False,
        api_calls=0,llm_calls=0,training=False,portfolio_backtest=False,orders=False)
    parent.save(root/'protocol.json',p)
    features=confirmation(pd.read_parquet(SOURCE/'features.parquet'))
    features.to_parquet(root/'features.parquet',index=False)
    selected=features[features.three_sign.ne(0)]
    parent.save(root/'frequency.json',dict(rows=len(features),
        one_change_signals=int(features.one_sign.ne(0).sum()),
        three_change_signals=len(selected),symbols=int(selected.symbol.nunique()),
        entry_dates=int(selected.entry_date.nunique()),
        side_counts=selected.three_sign.value_counts().to_dict(),
        by_date={str(k)[:10]:int(v) for k,v in selected.groupby('entry_date').size().items()},
        reasons=features.confirmation_reason.value_counts().to_dict(),
        feature_sha256=parent.digest(root/'features.parquet')))
    print('FREQUENCY',len(selected),'signals',selected.symbol.nunique(),'symbols',selected.entry_date.nunique(),'dates',flush=True)


def check(root):
    p=parent.read(root/'protocol.json')
    for n,h in p['sources'].items():
        if parent.digest(n)!=h:raise ValueError('Source changed: '+n)
    if parent.digest(root/'features.parquet')!=parent.read(root/'frequency.json')['feature_sha256']:
        raise ValueError('Features changed')
    return p


def prices(root):
    p=check(root)
    if (root/'prices-ready.json').exists():raise FileExistsError('Prices already frozen')
    universe=parent.read(SOURCE/'protocol.json')['symbols']
    engine,conn=parent.connect_readonly()
    try:
        rows=parent.query(conn,'''SELECT symbol,date,open,high,low,close,volume,
            is_filled,data_adjustment,data_source,instrument_id,last_updated
            FROM stock_bars_daily WHERE symbol IN :symbols AND data_source='alpaca_sip'
            AND date BETWEEN '2026-10-12' AND :cutoff ORDER BY symbol,date''',universe+['SPY'],
            cutoff=str(parent.utc(p['price_cutoff_utc']).date()))
        conn.rollback()
    finally:conn.close();engine.dispose()
    frame=pd.DataFrame(rows)
    if frame.duplicated(['symbol','date']).any():raise ValueError('Duplicate SIP daily bar')
    frame.to_parquet(root/'prices.parquet',index=False)
    parent.save(root/'prices-ready.json',dict(rows=len(frame),first=str(frame.date.min()),last=str(frame.date.max()),
        symbols=int(frame.symbol.nunique()),provider='alpaca_sip',prices_sha256=parent.digest(root/'prices.parquet')))
    print('SIP PRICES',len(frame),'through',frame.date.max(),flush=True)


def valid_window(group,days,registry,symbol):
    if group is None:return None,'MISSING_SYMBOL'
    g=group.reindex(days)
    valid=(g.is_filled.eq(0)&g[['open','high','low','close','volume']].gt(0).all(axis=1)&
        np.isfinite(g[['open','high','low','close','volume']]).all(axis=1)&
        g.high.ge(g[['open','close','low']].max(axis=1))&g.low.le(g[['open','close','high']].min(axis=1)))
    if not valid.all():return None,'MISSING_OR_INVALID_FULL_WINDOW'
    if g.data_source.isna().any() or not g.data_source.eq('alpaca_sip').all():return None,'NON_SIP'
    if g.data_adjustment.isna().any() or not g.data_adjustment.eq('raw').all():return None,'NOT_RAW'
    if g.instrument_id.isna().any() or g.instrument_id.nunique()!=1:return None,'UNKNOWN_OR_CHANGED_IDENTITY'
    if any(e.crosses(days[0],days[-1]) for e in registry.get(symbol,())):return None,'KNOWN_IDENTITY_BREAK'
    return g,'AVAILABLE_RESEARCH_NOT_PRODUCTION_QUALIFIED'


def stats(g):
    valid=g[g.status.eq('AVAILABLE_RESEARCH_NOT_PRODUCTION_QUALIFIED')]
    result=dict(signals=len(g),evaluated=len(valid),symbols=int(valid.symbol.nunique()),
        dates=int(valid.entry_date.nunique()),statuses=g.status.value_counts().to_dict())
    if valid.empty:return result
    means=valid.groupby('entry_date').gross_pct.mean()
    result.update(mean_gross_pct=float(valid.gross_pct.mean()),median_gross_pct=float(valid.gross_pct.median()),
        winning_pct=float(valid.gross_pct.gt(0).mean()*100),after_16bps_mean_pct=float(valid.gross_pct.mean()-.16),
        equal_date_mean_pct=float(means.mean()),positive_dates=int(means.gt(0).sum()),
        exit_reasons=valid.exit_reason.value_counts().to_dict(),
        mean_full_sessions_held=float(valid.full_sessions_held.mean()),
        same_dates_always_long_open_close_mean_pct=float(valid.long_open_close_pct.mean()),
        same_dates_always_short_open_close_mean_pct=float(-valid.long_open_close_pct.mean()))
    return result


def run(root):
    p=check(root)
    if (root/'report.json').exists():raise FileExistsError('Report exists')
    if parent.digest(root/'prices.parquet')!=parent.read(root/'prices-ready.json')['prices_sha256']:
        raise ValueError('Price snapshot changed')
    f=pd.read_parquet(root/'features.parquet')
    raw=pd.read_parquet(root/'prices.parquet')
    raw['date']=pd.to_datetime(raw.date)
    for c in ('open','high','low','close','volume'):raw[c]=pd.to_numeric(raw[c],errors='coerce')
    groups={s:g.set_index('date') for s,g in raw.groupby('symbol')}
    lookup={(r.symbol,r.entry_idx):r for r in f.itertuples()}
    schedule=parent.schedule()
    registry=parent.load_security_discontinuities()
    rows=[]
    report=dict(status='COMPLETED_EXPLORATORY_CONFIRMATION_AND_INVERSE_EXIT',
        frequency=parent.read(root/'frequency.json'),prices=parent.read(root/'prices-ready.json'),
        feature_cutoff_utc=p['feature_cutoff_utc'],price_cutoff_utc=p['price_cutoff_utc'],
        protections=dict(tp=p['tp'],sl=p['sl'],trailing=False),horizons={},
        production_qualified=False,portfolio_backtest=False,minimum_independent_confirmation_met=False,
        sql_writes=False,api_calls=0,llm_calls=0,training=False,orders=False)
    for h in (1,3,5,10):
        if h==10:
            chosen=f[f.three_sign.ne(0)]
            maturities=pd.to_datetime((chosen.entry_idx+9).map(schedule.closing.to_dict()),utc=True)
            report['horizons']['10']=dict(signals=len(chosen),
                mature_at_cutoff=int(maturities.lt(parent.utc(p['price_cutoff_utc'])).sum()),returns_computed=False)
            continue
        # Independent reservations are selected on all features, before any outcome.
        reserved=parent.reserve_windows(f.assign(exit_idx=f.entry_idx+h-1))
        kept=set(zip(reserved.symbol,reserved.entry_idx))
        for r in f[f.one_sign.ne(0)].itertuples():
            end=r.entry_idx+h-1
            maturity=schedule.iloc[end].closing
            inverse=first_inverse(r,lookup,end) if r.three_sign else None
            g,status=(None,'IMMATURE')
            if maturity<parent.utc(p['price_cutoff_utc']):
                g,status=valid_window(groups.get(r.symbol),schedule.day.iloc[r.entry_idx:end+1],registry,r.symbol)
            for arm in ARMS:
                if arm!=ARMS[0] and not r.three_sign:continue
                info=dict(symbol=r.symbol,entry_date=r.entry_date,entry_idx=r.entry_idx,horizon=h,
                    arm=arm,sign=int(r.one_sign),status=status,maturity=maturity,
                    no_overlap=(r.symbol,r.entry_idx) in kept,
                    inverse_idx=inverse if arm==ARMS[2] else None)
                if g is not None:
                    result=replay(g,r.one_sign,tp=p['tp'],sl=p['sl'],
                        inverse_offset=inverse-r.entry_idx if inverse is not None and arm==ARMS[2] else None)
                    info.update(**result,exit_date=schedule.iloc[r.entry_idx+result['exit_offset']].day,
                        long_open_close_pct=float((g.close.iloc[-1]/g.open.iloc[0]-1)*100))
                rows.append(info)
        cases=pd.DataFrame([r for r in rows if r['horizon']==h])
        cases.to_parquet(root/f'cases-H{h}.parquet',index=False)
        summary={arm:dict(all=stats(cases[cases.arm.eq(arm)]),
            no_overlap=stats(cases[cases.arm.eq(arm)&cases.no_overlap]),
            by_side={name:stats(cases[cases.arm.eq(arm)&cases.sign.eq(sign)])
                for name,sign in (('LONG',1),('SHORT',-1))}) for arm in ARMS}
        selected_dates=set(f.loc[f.three_sign.ne(0),'entry_date'])
        summary['A_SAME_ENTRY_DATES_AS_B']=stats(cases[cases.arm.eq(ARMS[0])&cases.entry_date.isin(selected_dates)])
        pair=cases[cases.arm.eq(ARMS[1]) & cases.status.eq('AVAILABLE_RESEARCH_NOT_PRODUCTION_QUALIFIED')].merge(
            cases[cases.arm.eq(ARMS[2]) & cases.status.eq('AVAILABLE_RESEARCH_NOT_PRODUCTION_QUALIFIED')],
            on=['symbol','entry_idx'],suffixes=('_fixed','_dynamic'),validate='one_to_one')
        summary['paired_dynamic_minus_fixed']=dict(n=len(pair),
            mean_delta_pct=float((pair.gross_pct_dynamic-pair.gross_pct_fixed).mean()) if len(pair) else None,
            inverse_exits=int(pair.exit_reason_dynamic.eq('INVERSE_AT_OPEN').sum()) if len(pair) else 0)
        report['horizons'][str(h)]=summary
        print('H',h,'confirmed evaluated',summary[ARMS[1]]['all']['evaluated'],
              'inverse exits',summary['paired_dynamic_minus_fixed']['inverse_exits'],flush=True)
    report['files']={path.name:parent.digest(path) for path in root.iterdir() if path.is_file()}
    parent.save(root/'report.json',report)
    print(report['status'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('prepare','prices','run'),required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT)
    a=parser.parse_args()
    dict(prepare=prepare,prices=prices,run=run)[a.phase](a.output_dir)
