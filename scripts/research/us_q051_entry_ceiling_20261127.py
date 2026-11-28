"""Frozen Q051 TOP10 entry ceiling; research only, no SQL/network/broker.

One prespecified ceiling = close(J) + 0.5 * SMA20(true range). Compare an
immediate opening gate with a two-session observed-open waiting policy.
The native economic engine is retained; a guarded in-memory source adapter
lets its existing scheduled-entry path coexist with canonical daily opens.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from functools import lru_cache
import inspect
import json
import logging
from multiprocessing import get_context
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research import us_q051_decline_rebound_20261126 as previous
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT=Path('artifacts/research/us_q051_entry_ceiling/20261127-v1')
INPUT=previous.ROOT/'inputs'
CASES={'REFERENCE':'Q051 témoin TOP10', 'CAP_OPEN':'Plafond : ouverture J+1 seulement',
       'CAP_WAIT2':'Plafond : attente maximale deux séances'}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def ceiling_panel(signals,high,low,close):
    if not high.index.equals(close.index) or not low.index.equals(close.index):raise ValueError('Price calendars differ')
    if close.index.has_duplicates or not close.index.is_monotonic_increasing:raise ValueError('Ambiguous calendar')
    valid=np.isfinite(high)&np.isfinite(low)&np.isfinite(close)&high.gt(0)&low.gt(0)&close.gt(0)
    prior=close.shift(1)
    tr=pd.DataFrame(np.maximum.reduce([(high-low).to_numpy(),(high-prior).abs().to_numpy(),
        (low-prior).abs().to_numpy()]),index=close.index,columns=close.columns)
    tr=tr.where(valid&valid.shift(1,fill_value=False))
    atr=tr.rolling(20,min_periods=20).mean()
    rows=close.index.get_indexer(pd.to_datetime(signals.trade_date));cols=close.columns.get_indexer(signals.symbol)
    if (rows<0).any() or (cols<0).any() or signals.duplicated(['trade_date','symbol']).any():raise ValueError('Invalid candidate identity')
    out=signals.copy();out['origin_signal_date']=pd.to_datetime(out.trade_date)
    out['origin_id']=out.origin_signal_date.dt.strftime('%Y-%m-%d')+'|'+out.symbol
    out['signal_close']=close.to_numpy()[rows,cols];out['atr20']=atr.to_numpy()[rows,cols]
    out['ceiling']=out.signal_close+.5*out.atr20
    out['qualified']=np.isfinite(out.ceiling)&out.atr20.gt(0)
    return out


def expand_windows(panel,sessions):
    """Two fixed dates per signal, never selected from future prices/returns.

    On a repeated selection of the same symbol, the most recent Oracle signal
    supersedes the unexecuted old plan. A native risk refusal is never retried.
    """
    sessions=pd.DatetimeIndex(sessions);rows=[]
    for source in panel.to_dict('records'):
        i=sessions.get_indexer([pd.Timestamp(source['origin_signal_date'])])[0]
        if i<0:raise ValueError('Signal outside official sessions')
        for offset in (1,2):
            if i+offset>=len(sessions):continue
            rows.append(dict(source,trade_date=sessions[i+offset-1],entry_day=sessions[i+offset],
                             wait_session=offset))
    expanded=pd.DataFrame(rows)
    expanded=expanded.sort_values(['trade_date','symbol','origin_signal_date'])
    superseded=expanded[expanded.duplicated(['trade_date','symbol'],keep='last')].copy()
    expanded=expanded.drop_duplicates(['trade_date','symbol'],keep='last')
    return expanded.reset_index(drop=True),superseded


def adapted_replay():
    """Two checked substitutions, in worker memory only; production untouched."""
    import backtesting.winner_intraday as native
    text=inspect.getsource(inspect.unwrap(native.run_winner_replay))
    old='if daily_entry and entry_timing_source is None and offset==0 and not liquidation.blocks_entries:'
    new='if daily_entry and offset==0 and not liquidation.blocks_entries:'
    call='                enter_daily_candidates(daily_rows,signal_day=prior_day,day=day,opening=opening,'
    replacement=('                initial_rows=(daily_rows if entry_timing_source is None else\n'
                 '                    entry_timing_source.at_daily_open(prior_day,day,opening,daily_rows))\n'
                 '                enter_daily_candidates(initial_rows,signal_day=prior_day,day=day,opening=opening,')
    if text.count(old)!=1 or text.count(call)!=1:raise ValueError('Native entry adapter contract changed')
    text=text.replace(old,new).replace(call,replacement)
    namespace=dict(native.__dict__)
    exec(compile(text,'<research_q051_entry_ceiling_adapter>','exec'),namespace)
    return namespace['run_winner_replay']


class CeilingTiming:
    def __init__(self,opens,prices):
        self.opens=opens;self.prices=prices;self.attempted=set();self.audit=[];self._day=None;self._groups={}

    def at_daily_open(self,prior_day,day,stamp,rows):
        selected=[]
        for row in rows.to_dict('records'):
            key=row['origin_id'];price=self.opens.at[pd.Timestamp(day),row['symbol']]
            if key in self.attempted:continue
            valid=bool(row['qualified'] and np.isfinite(price) and price>0)
            accepted=valid and price<=row['ceiling']+1e-10
            self.audit.append(dict(time=stamp,origin_id=key,symbol=row['symbol'],kind='DAILY_OPEN',
                wait_session=int(row['wait_session']),price=float(price) if np.isfinite(price) else None,
                ceiling=float(row['ceiling']) if row['qualified'] else None,accepted=bool(accepted)))
            if accepted:
                self.attempted.add(key);selected.append(row)
        return pd.DataFrame(selected,columns=rows.columns)

    def __call__(self,prior_day,day,stamp,rows):
        from common.winner_pyramiding import regular_bounds
        opening,closing=regular_bounds(day)
        if stamp==opening:return {}  # Canonical daily open was processed above.
        if day!=self._day:
            # Late fills require a complete, compatible protection session.
            # This is an ex-post data-quality restriction, explicitly reported;
            # never replace a missing 5m price with a daily low.
            self._day=day;self._groups={}
            expected=pd.date_range(opening,closing,freq='5min',inclusive='left')
            for symbol,frame in self.prices.day(day).items():
                g=frame.copy();g['timestamp']=pd.to_datetime(g.timestamp,utc=True)
                g=g.set_index('timestamp').sort_index()
                if g.index.has_duplicates or not g.index.equals(expected):continue
                values=g[['open','high','low','close','volume']].astype(float)
                if (not np.isfinite(values.to_numpy()).all() or not values.gt(0).all().all()
                    or not values.low.le(values[['open','close']].min(axis=1)).all()
                    or not values.high.ge(values[['open','close']].max(axis=1)).all()):continue
                canonical=self.opens.at[pd.Timestamp(day),symbol] if symbol in self.opens else np.nan
                if not np.isfinite(canonical) or abs(canonical/float(g.iloc[0].open)-1)>.01+1e-12:continue
                self._groups[symbol]=g
        due={}
        for row in rows.to_dict('records'):
            key=row['origin_id'];symbol=row['symbol']
            if key in self.attempted or not row['qualified'] or symbol not in self._groups:continue
            price=float(self._groups[symbol].at[pd.Timestamp(stamp),'open'])
            if price>row['ceiling']+1e-10:continue
            # The level is fixed after signal J, not confirmed by this candle's
            # future close/low. No additional SIP signal computation is used.
            confirmed=regular_bounds(pd.Timestamp(row['origin_signal_date']).date())[1]
            due[symbol]=dict(confirmed_at=confirmed.isoformat(),available_at=confirmed.isoformat(),
                origin_id=key,origin_signal_date=str(pd.Timestamp(row['origin_signal_date']).date()),
                entry_ceiling=float(row['ceiling']),wait_session=int(row['wait_session']),
                timing_method='PRECOMMITTED_CEILING_AT_OBSERVED_OPEN')
            self.audit.append(dict(time=stamp,origin_id=key,symbol=symbol,kind='OBSERVED_5M_OPEN',
                wait_session=int(row['wait_session']),price=price,ceiling=float(row['ceiling']),accepted=True))
            self.attempted.add(key)
        return due


def prepare():
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    ROOT.mkdir(parents=True,exist_ok=False);(ROOT/'inputs').mkdir()
    if read(previous.ROOT/'validation.json')['status']!='PASS':raise ValueError('Unvalidated witness')
    previous.configuration()
    signals=pd.read_parquet(INPUT/'signals-REFERENCE.parquet')
    fields={name:pd.read_parquet(INPUT/(name+'.parquet')) for name in ('open','high','low','close')}
    panel=ceiling_panel(signals,fields['high'],fields['low'],fields['close'])
    with replay_market_registry(previous.shared.restore_registry(previous.shared.ROOT)):
        cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=cal.session_dates(pd.to_datetime(signals.trade_date).min().date(),pd.Timestamp('2026-10-10').date())
        expanded,superseded=expand_windows(panel,sessions)
    panel.to_parquet(ROOT/'inputs/candidates.parquet',index=False)
    expanded.to_parquet(ROOT/'inputs/expanded.parquet',index=False)
    superseded.to_parquet(ROOT/'inputs/superseded.parquet',index=False)
    # Opening-only audit: all values on each entry day are opening prices,
    # never returns or the eventual high/low.
    audit=[]
    for row in expanded.to_dict('records'):
        if row['entry_day']>pd.Timestamp('2026-10-01'):continue
        price=float(fields['open'].at[row['entry_day'],row['symbol']])
        audit.append(dict(origin_id=row['origin_id'],symbol=row['symbol'],entry_day=str(row['entry_day'].date()),
            wait_session=row['wait_session'],qualified=bool(row['qualified']),
            price=price if np.isfinite(price) else None,ceiling=float(row['ceiling']) if row['qualified'] else None,
            below_ceiling=bool(row['qualified'] and np.isfinite(price) and price<=row['ceiling']+1e-10)))
    pd.DataFrame(audit).to_csv(ROOT/'opening-audit.csv',index=False)
    sources={str(p):digest(p) for p in INPUT.iterdir() if p.is_file()}
    for name in ('scripts/research/us_q051_decline_rebound_20261126.py','backtesting/winner_intraday.py',
                 'backtesting/winner_daily_entry.py','backtesting/winner_daily_protection.py',str(Path(__file__))):
        sources[name]=digest(name)
    for p in (ROOT/'inputs').iterdir():sources[str(p)]=digest(p)
    old=read(previous.ROOT/'protocol.json')
    protocol=dict(start='2021-01-01',end='2026-10-01',cases=CASES,initial_equity=4000.,annual_reset=False,
        reference=old['reference'],annual_models=old['annual_models'],configuration=asdict(previous.configuration()),
        rule=dict(ceiling='close(J)+0.5*mean20(true_range)',atr='SMA20 of max(high-low,abs(high-prev_close),abs(low-prev_close)); 21 valid sessions',
            multiplier=.5,wait_sessions=2,primary='CAP_WAIT2',no_refill=True,
            repeated_signal='Newest signal replaces the unexecuted older carry; original rank and score unchanged',
            risk_refusal='One attempt only, no retry',holding='10 held sessions, exit actual entry-session+10 open',
            latency='Precommitted ceiling known after J close, not a delayed 5m confirmation signal',
            fill_proxy='daily open, or regular observed 5m OPEN <= ceiling; never low touch',
            intraday_coverage='Late entries only on complete compatible 5m days, an ex-post archive quality restriction'),
        sources=sources,market_files=old['market_files'],baseline_root=str(previous.BASE),
        training=False,new_inference=False,SQL_writes=0,provider_calls=0,broker_orders=0,production_changes=False,
        limitations=['Previously studied period and retrospective universe','Partial 5m/daily OHLC protection fallback',
            'Observed-open fills are exploratory, no certified quote/order-book execution',
            'Late-entry completeness restriction uses ex-post archive coverage; not strict PIT/live parity'],
        prepared_at_utc=datetime.now(timezone.utc).isoformat())
    adapted_replay()  # Validate adapter before freezing the protocol.
    atomic_json(ROOT/'protocol.json',protocol)
    atomic_json(ROOT/'feasibility.json',dict(candidates=len(panel),missing_ATR=int((~panel.qualified).sum()),
        opening_J1_under_ceiling=sum(x['below_ceiling'] for x in audit if x['wait_session']==1),
        superseded_old_plans=len(superseded),sources_sealed=True,status='READY'))
    atomic_json(ROOT/'progress.json',dict(status='READY',completed=0,total=len(CASES)))


def run_case(case):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    import backtesting.winner_intraday as native
    plan=read(ROOT/'protocol.json');folder=ROOT/'cases'/case;folder.mkdir(parents=True,exist_ok=False)
    out=folder/'result';out.mkdir()
    try:
        for name,checksum in plan['sources'].items():
            if digest(name)!=checksum:raise ValueError('Source changed: '+name)
        cfg=previous.configuration()
        atomic_json(folder/'protocol.json',{**plan,'case':case})
        atomic_json(out/'configuration.json',dict(profile=case,portfolio=asdict(cfg)))
        atomic_json(folder/'progress.json',dict(status='LOADING'))
        pivots={k:pd.read_parquet(INPUT/(k+'.parquet')) for k in ('open','high','low','close','volume')}
        sectors=pd.read_parquet(INPUT/'sectors.parquet');actions=pd.read_parquet(INPUT/'actions.parquet')
        class Prices(ExtendedPrices):
            @lru_cache(maxsize=6)
            def day(self,day):
                for path in (previous.shared.ROOT/'inputs/base/intraday'/f'{day}.parquet',
                             previous.shared.ROOT/'inputs/extra-intraday'/f'{day}.parquet',
                             previous.EXT/'inputs/intraday'/f'{day}.parquet'):
                    if digest(path)!=plan['market_files'].get(str(path)):raise ValueError('Changed intraday archive')
                return super().day(day)
        prices=Prices(previous.EXT)
        panel=pd.read_parquet(ROOT/'inputs/candidates.parquet')
        if case=='REFERENCE':signals=pd.read_parquet(INPUT/'signals-REFERENCE.parquet')
        elif case=='CAP_OPEN':signals=panel.copy()
        else:signals=pd.read_parquet(ROOT/'inputs/expanded.parquet')
        timing=CeilingTiming(pivots['open'],prices) if case=='CAP_WAIT2' else None
        import backtesting.winner_daily_entry as daily
        original=daily.enter_daily_candidates
        gate_audit=[]
        def capped(*args,**kw):
            rows=args[0] if args else kw.pop('rows')
            if case=='CAP_WAIT2':
                kept=rows
            else:
                kept=rows.iloc[:0].copy()
            day=pd.Timestamp(kw['day']);opens=kw['open_df']
            keep=[]
            for row in ([] if case=='CAP_WAIT2' else rows.to_dict('records')):
                price=float(opens.at[day,row['symbol']])
                accepted=bool(row['qualified'] and np.isfinite(price) and price<=row['ceiling']+1e-10)
                gate_audit.append(dict(origin_id=row['origin_id'],time=kw['opening'],symbol=row['symbol'],
                    price=price,ceiling=float(row['ceiling']),accepted=accepted,kind='DAILY_OPEN'))
                if accepted:keep.append(row)
            if case!='CAP_WAIT2':kept=pd.DataFrame(keep,columns=rows.columns)
            before=len(kw['book'].events)
            result=original(kept,**kw)
            by_symbol={row['symbol']:row for row in kept.to_dict('records')}
            for event in kw['book'].events[before:]:
                if event.get('event')=='BUY_FILL':
                    row=by_symbol[event['symbol']]
                    event.update(origin_id=row['origin_id'],origin_signal_date=str(pd.Timestamp(row['origin_signal_date']).date()),
                        entry_ceiling=float(row['ceiling']),wait_session=int(row.get('wait_session',1)))
            return result
        def no_http(*a,**kw):raise ValueError('Network forbidden in this frozen replay')
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(ReadOnlyReplay(folder).install())
            stack.enter_context(replay_market_registry(previous.shared.restore_registry(previous.shared.ROOT)))
            stack.enter_context(patch.object(requests.Session,'request',no_http))
            if case!='REFERENCE':stack.enter_context(patch.object(daily,'enter_daily_candidates',capped))
            if timing:stack.enter_context(patch.object(native,'run_winner_replay',adapted_replay()))
            def progress(done,total,day):
                atomic_json(folder/'progress.json',dict(status='REPLAYING',completed=done,total=total,last_date=str(day),case=case))
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=prices,winner_research_assumptions=True,winner_progress=progress,
                winner_corporate_actions=actions.to_dict('records'),winner_entry_timing_source=timing)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False)
            result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            report=metrics(result,4000.)
            report.update(case=case,original_signal_count=len(panel),scheduled_rows=len(signals),
                annual_models=plan['annual_models'],model_timing_oos=True,strict_pit=False,
                provider_calls=0,SQL_writes=0,broker_orders=0,finished_at_utc=datetime.now(timezone.utc).isoformat())
            if timing:report['entry_protocol']=plan['rule']
            atomic_json(out/'report.json',report)
            annual=[];opening=4000.
            for year in range(2021,2027):
                e=result.equity_curve[result.equity_curve.index.year==year];t=result.closed_trades_df;m=result.intraday_equity_curve
                part=BacktestResult(equity_curve=e,closed_trades_df=t[pd.to_datetime(t.exit_date,utc=True).dt.year.eq(year)],
                    intraday_equity_curve=m[pd.to_datetime(m.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row['year']=year;annual.append(row);opening=float(e.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
        pd.DataFrame(timing.audit if timing else gate_audit).to_csv(out/'entry-audit.csv',index=False)
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        return dict(case=case,final_equity=report['final_equity'],return_pct=report['return_pct'],max_drawdown_pct=report['max_drawdown_pct'])
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


def validate_reference():
    base=previous.BASE/'result';current=ROOT/'cases/REFERENCE/result'
    a=read(base/'report.json');b=read(current/'report.json')
    keys=('final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','costs','average_gross_capital')
    differences={k:[a[k],b[k]] for k in keys if not np.isclose(a[k],b[k],rtol=1e-10,atol=1e-6)}
    old=pd.read_csv(base/'equity-daily.csv',index_col=0);new=pd.read_csv(current/'equity-daily.csv',index_col=0)
    match=old.index.equals(new.index) and np.allclose(old.equity,new.equity,rtol=1e-10,atol=1e-6)
    status='PASS' if not differences and match else 'DIFFERENT'
    atomic_json(ROOT/'baseline-reproduction.json',dict(status=status,differences=differences,every_daily_equity_equal=bool(match)))
    if status!='PASS':raise ValueError('Witness not reproduced; do not interpret variants')


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prepare','reference','variants','case'],required=True)
    p.add_argument('--case',choices=list(CASES));args=p.parse_args();logging.basicConfig(level=logging.WARNING)
    if args.phase=='prepare':prepare()
    elif args.phase=='reference':print(json.dumps(run_case('REFERENCE')),flush=True);validate_reference()
    elif args.phase=='case':print(json.dumps(run_case(args.case)),flush=True)
    else:
        validate_reference()
        with ProcessPoolExecutor(max_workers=2,mp_context=get_context('spawn')) as pool:
            futures={pool.submit(run_case,c):c for c in ('CAP_OPEN','CAP_WAIT2')}
            for i,future in enumerate(as_completed(futures),1):
                print(json.dumps(future.result()),flush=True)
                atomic_json(ROOT/'progress.json',dict(status='REPLAYING',completed=i+1,total=3,last=futures[future]))


if __name__=='__main__':main()
