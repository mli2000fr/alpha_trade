"""Frozen TOP10 path diagnostic; no fitting, trading, provider or SQL writes.

An observation is a hypothetical independent entry, NOT a portfolio trade.
Future adverse excursion is an explanatory outcome, never an entry feature.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_top10_all_short_tp20_sl7 import freeze_top10, INPUT

LOG = logging.getLogger(__name__)
TP, SL, HOLD = .20, .07, 20
ARMS = ('ALL', 'ADV20_GE_20M', 'PAST_GAP20_LT_7PCT', 'BOTH')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def valid_bar(frame):
    p = frame[['open', 'high', 'low', 'close']]
    return (np.isfinite(p).all(axis=1) & p.gt(0).all(axis=1)
            & frame.low.le(frame[['open', 'close']].min(axis=1))
            & frame.high.ge(frame[['open', 'close']].max(axis=1))
            & frame.is_filled.eq(0) & frame.data_source.eq('eodhd_eod')
            & frame.data_adjustment.eq('split') & frame.instrument_id.notna())


def past_features(bars, days):
    """Only bars up to and including J. Reindex first: no skipping missing sessions."""
    b = bars.set_index('date').reindex(days).copy()
    good = valid_bar(b)
    same_id = b.instrument_id.eq(b.instrument_id.shift())
    previous = b.close.shift().where(good.shift(fill_value=False) & same_id)
    gap = (b.open / previous - 1).abs().where(good)
    dollar = (b.close * b.volume).where(good & np.isfinite(b.volume) & b.volume.gt(0))
    tr = pd.concat([b.high-b.low, (b.high-previous).abs(), (b.low-previous).abs()], axis=1).max(axis=1)
    tr = tr.where(good & previous.notna())
    f = pd.DataFrame(dict(adv20=dollar.rolling(20, min_periods=20).mean(),
                         past_gap20=gap.rolling(20, min_periods=20).max(),
                         atr20_pct=tr.rolling(20, min_periods=20).mean()/b.close))
    id_complete = b.instrument_id.rolling(21, min_periods=21).apply(lambda x: float(x.min()==x.max()))
    f = f.where(id_complete.eq(1))
    return b, f


def barrier_path(window, side):
    """20 sessions including entry. Stop first on an unknowable OHLC collision.

    Gap through stop executes at open; target executes at its limit, not a
    favourable open. No fees/borrow, sizing or portfolio PnL in this diagnostic.
    """
    if side not in ('LONG', 'SHORT') or len(window) != HOLD:
        raise ValueError('Exactly twenty sessions and explicit side required')
    if not valid_bar(window).all() or window.instrument_id.nunique()!=1:
        return dict(path_status='UNQUALIFIED_PATH')
    entry = float(window.open.iloc[0]); long = side == 'LONG'
    stop, take = entry*(1-SL if long else 1+SL), entry*(1+TP if long else 1-TP)
    first_tp = first_sl = None
    outcome, exit_price, exit_session, ambiguous, gap_stop = 'TIMEOUT', float(window.close.iloc[-1]), HOLD, False, False
    for i, bar in enumerate(window.itertuples(), 1):
        st = bar.low <= stop if long else bar.high >= stop
        tp = bar.high >= take if long else bar.low <= take
        if st and first_sl is None: first_sl = i
        if tp and first_tp is None: first_tp = i
        if outcome != 'TIMEOUT': continue
        # Entry is at the first open; on later days open precedes high/low.
        open_stop = i > 1 and (bar.open <= stop if long else bar.open >= stop)
        open_tp = i > 1 and (bar.open >= take if long else bar.open <= take)
        if open_stop:
            outcome, exit_price, exit_session, gap_stop = 'SL', float(bar.open), i, True
        elif open_tp:
            outcome, exit_price, exit_session = 'TP', take, i
        elif st:
            outcome, exit_price, exit_session, ambiguous = 'SL', stop, i, bool(tp)
        elif tp:
            outcome, exit_price, exit_session = 'TP', take, i
    sign = 1 if long else -1
    final = sign*(float(window.close.iloc[-1])/entry-1)
    favorable = float(window.high.max()/entry-1) if long else float(1-window.low.min()/entry)
    adverse = float(1-window.low.min()/entry) if long else float(window.high.max()/entry-1)
    extreme_pos = int(np.argmax(window.high.to_numpy()) if long else np.argmin(window.low.to_numpy()))
    # Excludes the peak bar because intraday low/high ordering is unknown.
    before = window.iloc[:extreme_pos]
    adverse_before = None if before.empty else max(0., float(1-before.low.min()/entry) if long else float(before.high.max()/entry-1))
    return dict(path_status='QUALIFIED', outcome=outcome, tp_first=outcome=='TP',
                sl_first=outcome=='SL', ambiguity=ambiguous, gap_stop=gap_stop,
                entry_price=entry, exit_price=exit_price, exit_session=exit_session,
                path_return=sign*(exit_price/entry-1), terminal_direction_right=final>0,
                terminal_signed_return=final, max_favorable=favorable, max_adverse=adverse,
                max_adverse_before_best_prior_bars=adverse_before,
                first_tp_session=first_tp, first_sl_session=first_sl,
                favorable20_but_stopped=outcome=='SL' and favorable>=TP,
                right_terminal_but_stopped=outcome=='SL' and final>0)


def filter_mask(frame, arm):
    adv = frame.adv20.ge(20e6); gap = frame.past_gap20.lt(.07)
    return {'ALL': pd.Series(True,index=frame.index), 'ADV20_GE_20M':adv,
            'PAST_GAP20_LT_7PCT':gap, 'BOTH':adv & gap}[arm]


def summarize(frame):
    """Equal-date primary rates, observation-weighted secondary. No capital return."""
    out = []
    for (year, side), base in frame.groupby(['year', 'side']):
        base_daily = base.groupby('date').tp_first.mean()
        for arm in ARMS:
            sub = base.loc[filter_mask(base,arm)]
            daily = sub.groupby('date').tp_first.mean()
            paired = daily-base_daily.reindex(daily.index)
            # Temporal dependence: twenty-decision-session block bootstrap.
            calendar = sorted(base.date.unique())
            block = {d:i//20 for i,d in enumerate(calendar)}
            means = paired.groupby([block[d] for d in paired.index]).mean()
            rng = np.random.default_rng(20261019)
            ci = [None,None]
            if len(means)>=5:
                samples=rng.choice(means.to_numpy(),size=(2000,len(means)),replace=True).mean(axis=1)
                ci=[float(v) for v in np.quantile(samples,[.025,.975])]
            nonoverlap = sub[sub.date.isin(calendar[::20])]
            out.append(dict(year=int(year),side=side,arm=arm,n=len(sub),dates=len(daily),
                coverage=len(sub)/len(base),date_coverage=len(daily)/len(base_daily),
                tp_rate=float(sub.tp_first.mean()) if len(sub) else None,
                date_mean_tp=float(daily.mean()) if len(sub) else None,
                matched_date_tp_gain=float(paired.mean()) if len(sub) else None,
                paired_block_ci95=ci,blocks=len(means),
                sl_rate=float(sub.sl_first.mean()) if len(sub) else None,
                timeout_rate=float(sub.outcome.eq('TIMEOUT').mean()) if len(sub) else None,
                ambiguity_rate=float(sub.ambiguity.mean()) if len(sub) else None,
                right_terminal_but_stopped=float(sub.right_terminal_but_stopped.mean()) if len(sub) else None,
                favorable20_but_stopped=float(sub.favorable20_but_stopped.mean()) if len(sub) else None,
                nonoverlap_n=len(nonoverlap),nonoverlap_tp_rate=float(nonoverlap.tp_first.mean()) if len(nonoverlap) else None,
                median_adv20=float(sub.adv20.median()) if len(sub) else None,
                symbols=int(sub.symbol.nunique())))
    return out


def group_tables(frame):
    rows=[]
    for feature in ('adv_bucket','gap_bucket','atr_bucket','cap_bucket'):
        for (year,side,bucket), group in frame.groupby(['year','side',feature]):
            rows.append(dict(feature=feature,year=int(year),side=side,bucket=str(bucket),n=len(group),
                tp_rate=float(group.tp_first.mean()),sl_rate=float(group.sl_first.mean()),
                terminal_right=float(group.terminal_direction_right.mean()),
                terminal_right_but_stopped=float(group.right_terminal_but_stopped.mean()),
                favorable20_but_stopped=float(group.favorable20_but_stopped.mean()),
                gap_stop=float(group.gap_stop.mean()),ambiguity=float(group.ambiguity.mean())))
    return rows


def auc_table(frame):
    rows=[]
    for (year,side),part in frame.groupby(['year','side']):
        for feature,sign in [('adv20',1),('past_gap20',-1),('atr20_pct',-1)]:
            scores=[]
            for _,day in part.groupby('date'):
                if day.tp_first.nunique()==2:
                    scores.append(roc_auc_score(day.tp_first,sign*day[feature]))
            rows.append(dict(year=int(year),side=side,feature=feature,expected_orientation=sign,
                dates=len(scores),mean_daily_auc=float(np.mean(scores)) if scores else None))
    return rows


def prepare(output, cap_archive=None):
    output.mkdir(parents=True,exist_ok=False)
    old=read(INPUT/'ready.json')
    # Verify immutable data. Changed production scripts do not alter these data.
    for name in ('candidates.parquet',):
        verify_hashes(INPUT,{name:old['files'][name]})
    prices=Path(old['prices'])
    expected=next(h for n,h in old['sources'].items() if Path(n)==prices)
    verify_hashes(Path('.'),{str(prices):expected})
    immutable={n:h for n,h in old['sources'].items()
               if 'artifacts' in Path(n).parts and Path(n).suffix not in ('.py','.yaml','.yml')}
    verify_hashes(Path('.'),immutable)
    panel=freeze_top10(pd.read_parquet(INPUT/'candidates.parquet'))
    sources={str(p):digest(p) for p in [Path(__file__),INPUT/'ready.json',INPUT/'candidates.parquet',prices,
                                      Path('tests/test_us_top10_liquidity_gap_audit.py')]}
    if cap_archive is not None:
        sources[str(cap_archive)]=digest(cap_archive)
        atomic_json(output/'capitalizations.json',read(cap_archive))
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),source=str(INPUT),prices=str(prices),
        models=old['models'],years=old['years'],events=old['events'],top=10,tp=TP,sl=SL,sessions=HOLD,
        side='BOTH_SEPARATELY_EXPLICIT_NOT_DIRECTION_PREDICTED',
        entry='J+1 open, hold at most 20 sessions including entry; exit day20 close if no barrier',
        collision='stop first unless subsequent-session opening price resolves the order; ambiguity flagged',
        features='mean close*volume20; max abs open/previous-close gap20; ATR20/close, through J only',
        adv_buckets_usd=[5e6,20e6],gap_buckets=[.03,.07],atr_buckets=[.03,.05],
        arms=list(ARMS),filters='ADV20>=20m; gap20<7%; conjunction; no fitting or threshold search',
        cap_buckets_usd=[2e9,1e10],cap_max_age_days=45,
        cap_policy='Received before UTC midnight starting J (conservative), source availability <=J, non-Yahoo Finnhub/EODHD; unknown stays unknown',
        sources=sources,training=False,sql_writes=False,provider_calls=False,orders=False,
        economic_backtest=False,portfolio_returns=False,
        caveats=['Already-examined years; 2024 descriptive reference, 2025/2026 temporal stability not untouched holdout.',
            'Independent repeated overlapping candidate entries; not actual non-reinforced portfolio trades.',
            'Daily OHLC order sometimes unknown; stop-first conservative convention.',
            'Retrospectively downloaded split-adjusted EODHD data, no certified historical spreads/fills.',
            'Close*volume is a daily dollar-turnover proxy, not bid/ask depth or execution guarantee.',
            'Current survivor universe, annual historical model availability from archives.',
            'No fees, margin, borrow certification or corporate-action-complete economic PnL.',
            'Block intervals descriptive, unadjusted for multiple comparisons, not a discovery significance gate.',
            'Cross-sectional candidate composition changes between years; no causal interpretation of liquidity/volatility.',
            'Incomplete future windows excluded even when an early barrier is known; coverage reported.'])
    atomic_json(output/'protocol.json',protocol)
    panel.to_parquet(output/'candidates.parquet',index=False)
    return protocol


def export_caps(output):
    """Explicit optional SELECT-only snapshot. SQL is never used during path replay."""
    from database.connection import get_sqlalchemy_engine
    from sqlalchemy import text, bindparam
    protocol=read(output/'protocol.json')
    destination=output/'capitalizations.json'
    if destination.exists(): raise ValueError('Immutable snapshot already exists')
    symbols=pd.read_parquet(output/'candidates.parquet').symbol.unique().tolist()
    engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade':raise ValueError('US database required')
    with engine.connect() as conn:
        conn.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
        q=text('''SELECT id,symbol,trade_date,available_date,fetched_at,source,market_cap
            FROM stock_fundamentals_daily WHERE symbol IN :symbols AND source IN ('Finnhub','EODHD')
            AND market_cap>0 AND trade_date>='2023-11-01' AND trade_date<='2026-09-30'
            AND fetched_at<'2026-10-01' ORDER BY symbol,trade_date,fetched_at,id''').bindparams(bindparam('symbols',expanding=True))
        rows=[dict(r) for r in conn.execute(q,dict(symbols=symbols)).mappings()]
    atomic_json(destination,dict(exported_at_utc=datetime.now(timezone.utc).isoformat(),rows=rows,
        scope='Non-Yahoo existing observations; no provider request, USD under provider adapter convention, not independently currency/identity certified'))
    LOG.info('Read-only cap snapshot: %d records, %d symbols',len(rows),len({r['symbol'] for r in rows}))


def run(output):
    p=read(output/'protocol.json');verify_hashes(Path('.'),p['sources'])
    if (output/'report.json').exists():raise ValueError('Completed immutable report already exists')
    cap_file=output/'capitalizations.json'
    caps=pd.DataFrame(read(cap_file)['rows']) if cap_file.exists() else pd.DataFrame()
    cap_groups={} if caps.empty else {s:g for s,g in caps.groupby('symbol')}
    panel=pd.read_parquet(output/'candidates.parquet')
    prices=pd.read_parquet(p['prices']);prices=prices[prices.symbol.isin(panel.symbol.unique())].copy()
    prices.date=pd.to_datetime(prices.date)
    if prices.duplicated(['symbol','date']).any():raise ValueError('Duplicate price key')
    days=nyse_sessions('2023-01-01','2026-10-09')
    grouped={s:past_features(b.sort_values('date'),days) for s,b in prices.groupby('symbol')}
    exclusions=[];rows=[]
    for n,row in enumerate(panel.itertuples(),1):
        if n%1000==0:
            atomic_json(output/'progress.json',dict(status='RUNNING',completed=n,total=len(panel)))
            LOG.info('Paths %d/%d',n,len(panel))
        b,f=grouped[row.symbol];j=days.get_loc(row.date);year=row.date.year
        terminal=pd.Timestamp(p['years'][str(year)]['terminal'])
        forward=days[j+1:j+1+HOLD]
        reason=None
        if not row.selected: reason='ENTRY_REJECTED_IN_ORIGINAL_J_ARCHIVE'
        elif len(forward)!=HOLD or forward[-1]>terminal:reason='NOT_MATURE_AT_OBSERVATION_END'
        elif f.loc[row.date].isna().any():reason='MISSING_CAUSAL_FEATURES'
        elif not valid_bar(b.loc[forward]).all() or b.loc[forward].instrument_id.nunique()!=1:reason='UNQUALIFIED_FUTURE_PATH'
        elif b.loc[forward[0],'instrument_id']!=b.loc[row.date,'instrument_id']:reason='ENTRY_IDENTITY_CHANGED'
        elif any(row.symbol in {ev.get('source'),ev.get('target'),ev.get('trading_symbol')}
                 and row.date-pd.Timedelta(days=40)<=pd.Timestamp(ev['day'])<=forward[-1]
                 for ev in p['events']):reason='KNOWN_IDENTITY_EVENT_IN_FEATURE_OR_PATH'
        if reason:
            exclusions.append(dict(date=row.date,symbol=row.symbol,oracle_rank=row.oracle_rank,year=year,reason=reason));continue
        feature=f.loc[row.date].to_dict()
        cap=None;cap_age=None;cap_source=None
        candidates=cap_groups.get(row.symbol)
        if candidates is not None:
            observation=pd.to_datetime(candidates.trade_date)
            available=pd.to_datetime(candidates.available_date)
            received=pd.to_datetime(candidates.fetched_at)
            eligible=candidates[(observation<=row.date)&(observation>=row.date-pd.Timedelta(days=45))
                                &(available<=row.date)&(received<row.date)]
            if not eligible.empty:
                latest=eligible.sort_values(['trade_date','fetched_at','id']).iloc[-1]
                cap=float(latest.market_cap);cap_age=int((row.date-pd.Timestamp(latest.trade_date)).days);cap_source=latest.source
        for side in ('LONG','SHORT'):
            result=barrier_path(b.loc[forward],side)
            if result['path_status']!='QUALIFIED':raise AssertionError('Prequalification mismatch')
            rows.append(dict(date=row.date,symbol=row.symbol,oracle_rank=row.oracle_rank,year=year,side=side,
                entry_date=forward[0],last_path_date=forward[-1],**feature,market_cap=cap,cap_age=cap_age,cap_source=cap_source,
                adv_bucket='LT5M' if feature['adv20']<5e6 else '5_TO20M' if feature['adv20']<20e6 else 'GE20M',
                gap_bucket='LT3PCT' if feature['past_gap20']<.03 else '3_TO7PCT' if feature['past_gap20']<.07 else 'GE7PCT',
                atr_bucket='LT3PCT' if feature['atr20_pct']<.03 else '3_TO5PCT' if feature['atr20_pct']<.05 else 'GE5PCT',
                cap_bucket='UNKNOWN' if cap is None else 'SMALL' if cap<2e9 else 'MID' if cap<1e10 else 'LARGE',**result))
    frame=pd.DataFrame(rows);excluded=pd.DataFrame(exclusions)
    frame.to_parquet(output/'observations.parquet',index=False);excluded.to_csv(output/'excluded.csv',index=False)
    summaries=summarize(frame);groups=group_tables(frame);aucs=auc_table(frame)
    pd.DataFrame(summaries).to_csv(output/'filters.csv',index=False)
    pd.DataFrame(groups).to_csv(output/'buckets.csv',index=False)
    pd.DataFrame(aucs).to_csv(output/'daily-auc.csv',index=False)
    diagnostics=[]
    for (year,side),g in frame.groupby(['year','side']):
        right=g[g.terminal_direction_right];potential=g[g.max_favorable>=TP]
        diagnostics.append(dict(year=int(year),side=side,n=len(g),
            terminal_right_n=len(right),terminal_right_stopped_n=int(right.sl_first.sum()),
            stopped_fraction_among_terminal_right=float(right.sl_first.mean()) if len(right) else None,
            potential_tp_n=len(potential),potential_tp_stopped_n=int(potential.sl_first.sum()),
            stopped_fraction_among_potential_tp=float(potential.sl_first.mean()) if len(potential) else None,
            gap_stop_n=int(g.gap_stop.sum()),
            median_adverse_before_best_prior_bars=float(g.max_adverse_before_best_prior_bars.median()),
            note='Future explanatory outcomes, forbidden entry features; future peak bar excluded for ambiguous high/low order.'))
    concentration=[]
    for (year,bucket),g in frame[frame.side.eq('LONG')].groupby(['year','adv_bucket']):
        concentration.append(dict(year=int(year),adv_bucket=bucket,n=len(g),symbols=int(g.symbol.nunique()),
                                  largest_symbols=g.symbol.value_counts().head(3).to_dict()))
    gap_cases=frame[frame.gap_stop].sort_values('path_return').head(20)
    gap_cases.to_csv(output/'largest-gap-stop-cases.csv',index=False)
    counts={str(y):dict(candidate_rows=int(panel.date.dt.year.eq(y).sum()),
        evaluable_entries=int(frame[(frame.year==y)&frame.side.eq('LONG')].shape[0]),
        cap_known_entries=int(frame[(frame.year==y)&frame.side.eq('LONG')&frame.market_cap.notna()].shape[0]),
        exclusions=dict(Counter(excluded.loc[excluded.year.eq(y),'reason']))) for y in (2024,2025,2026)}
    clean=frame[~frame.ambiguity].copy()
    report=dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',protocol_sha256=digest(output/'protocol.json'),
        coverage=counts,filters=summaries,buckets=groups,daily_auc=aucs,
        path_diagnostics=diagnostics,liquidity_group_concentration=concentration,
        cap_snapshot_trade_date_min=str(caps.trade_date.min()) if not caps.empty else None,
        cap_snapshot_trade_date_max=str(caps.trade_date.max()) if not caps.empty else None,
        sensitivity_excluding_ambiguous=summarize(clean),
        files={name:digest(output/name) for name in ['candidates.parquet','observations.parquet','excluded.csv','filters.csv','buckets.csv','daily-auc.csv','largest-gap-stop-cases.csv']},
        cap_snapshot_sha256=digest(cap_file) if cap_file.exists() else None,
        interpretation='Path/barrier diagnostic, not economic portfolio backtest or new independent holdout.')
    verify_hashes(Path('.'),p['sources'])
    atomic_json(output/'report.json',report)
    atomic_json(output/'progress.json',dict(status=report['status'],completed=len(panel),total=len(panel)))
    LOG.info('Completed: %d candidate entries, %d exclusions; no portfolio PnL',len(frame)//2,len(excluded))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','caps-readonly','run'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cap-archive',type=Path,help='Existing read-only export to reuse during prepare; no SQL query')
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.phase=='prepare':prepare(args.output,args.cap_archive)
    else:{'caps-readonly':export_caps,'run':run}[args.phase](args.output)


if __name__=='__main__':main()
