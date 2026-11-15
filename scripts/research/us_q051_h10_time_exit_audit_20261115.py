"""Read-only descriptive H10 time-exit/MFE audit of the causal Q051 witness."""
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import requests
from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

SOURCE=Path('artifacts/research/us_q051_global_rank_h10/20261115-v1/cases/Q051_REFERENCE')
ROOT=Path('artifacts/research/us_q051_h10_time_exit_audit/20261115-v2')
BINS=[-np.inf,0,5,10,15,20,30,np.inf]
LABELS=['<0%','0 to <5%','5 to <10%','10 to <15%','15 to <20%','20 to <30%','>=30%']


def describe(values):
    return dict(count=len(values),mean_pct=float(values.mean()),median_pct=float(values.median()),
        min_pct=float(values.min()),p10_pct=float(values.quantile(.1)),p25_pct=float(values.quantile(.25)),
        p75_pct=float(values.quantile(.75)),p90_pct=float(values.quantile(.9)),max_pct=float(values.max()))


def audit(root=ROOT):
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    def no_http(*args,**kwargs):raise ValueError('HTTP forbidden in archived trade audit')
    with ReadOnlyReplay(root).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
        source=SOURCE/'result/trades.csv';trades=pd.read_csv(source)
        report=json.loads((SOURCE/'result/report.json').read_text())
        if len(trades)!=report['closed_lot_trades'] or len(trades)!=940:raise ValueError('Reference trades changed')
        paths=[shared.ROOT/'inputs/base/daily.parquet',shared.ROOT/'inputs/extra-daily.parquet']
        manifest=json.loads((shared.ROOT/'inputs/manifest.json').read_text())['files']
        for path in paths:
            relative=str(path.relative_to(shared.ROOT/'inputs')).replace('\\','/')
            hashes={k.replace('\\','/'):v for k,v in manifest.items()}
            if digest(path)!=hashes[relative]:raise ValueError('Frozen daily prices changed')
        bars=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
        if bars.duplicated(['date','symbol']).any():raise ValueError('Duplicate daily bar')
        prices={s:g.set_index('date').sort_index() for s,g in bars.groupby('symbol')}
        cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        calendar={pd.Timestamp(r.session_date):r for r in cal.sessions(date(2021,1,1),date(2026,10,1)) if r.is_open}
        sessions=pd.DatetimeIndex(sorted(calendar))
        events=pd.read_csv(SOURCE/'result/events.csv')
        fallback={(pd.Timestamp(r.date),r.symbol) for r in events[events.event.eq('DAILY_OHLC_FALLBACK')].itertuples()}
        timed=trades[trades.exit_reason.eq('HORIZON_OPEN')].copy();rows=[];requested={}
        for row in timed.itertuples():
            first=pd.Timestamp(row.entry_date).tz_convert('America/New_York').tz_localize(None).normalize()
            last=pd.Timestamp(row.exit_date).tz_convert('America/New_York').tz_localize(None).normalize()
            for day in sessions[(sessions>=first)&(sessions<last)]:
                if (day,row.symbol) not in fallback:requested.setdefault(day,set()).add(row.symbol)
            if not np.isclose(prices[row.symbol].loc[last,'open'],row.exit_price,atol=1e-8,rtol=1e-10):
                requested.setdefault(last,set()).add(row.symbol)
        # Read only relevant Parquet columns/rows from the same three frozen tapes.
        import pyarrow.parquet as pq
        extension=Path('artifacts/research/us_winner_vol20_extensions/20261109-v1')
        folders=[shared.ROOT/'inputs/base/intraday',shared.ROOT/'inputs/extra-intraday',extension/'inputs/intraday']
        manifests={shared.ROOT:manifest,extension:json.loads((extension/'inputs/manifest.json').read_text())['files']}
        manifests={k:{a.replace('\\','/'):b for a,b in v.items()} for k,v in manifests.items()}
        observations={};intraday_sources={}
        for i,(day,names) in enumerate(sorted(requested.items())):
            pieces=[]
            for folder in folders:
                path=folder/f'{day.date()}.parquet';owner=extension if folder==folders[-1] else shared.ROOT
                relative=str(path.relative_to(owner/'inputs')).replace('\\','/')
                sha=digest(path)
                if sha!=manifests[owner][relative]:raise ValueError('Changed archived intraday prices')
                intraday_sources[str(path)]=sha
                schema=pq.read_schema(path)
                if 'symbol' not in schema.names:continue  # Canonical empty archive.
                part=pd.read_parquet(path,columns=['symbol','timestamp','open','high'],filters=[('symbol','in',sorted(names))])
                if len(part):pieces.append(part)
            frame=pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame()
            if len(frame) and frame.duplicated(['symbol','timestamp']).any():raise ValueError('Duplicate 5m observations')
            groups={s:g.sort_values('timestamp') for s,g in frame.groupby('symbol')} if len(frame) else {}
            for symbol in names:
                g=groups.get(symbol)
                session=calendar[day]
                expected=pd.date_range(session.open_at_utc,session.close_at_utc,freq='5min',inclusive='left')
                if g is None or not pd.DatetimeIndex(g.timestamp).equals(expected):raise ValueError('Unqualified native 5m session')
                observations[day,symbol]=dict(high=float(g.high.max()),open=float(g.iloc[0].open))
            if i%25==0:atomic_json(root/'progress.json',dict(status='READING_FROZEN_INTRADAY_PEAKS',completed=i+1,total=len(requested)))
        atomic_json(root/'intraday-source-receipt.json',dict(files=intraday_sources))
        for row in timed.to_dict('records'):
            first=pd.Timestamp(row['entry_date']).tz_convert('America/New_York')
            last=pd.Timestamp(row['exit_date']).tz_convert('America/New_York')
            entry=first.tz_localize(None).normalize();exit=last.tz_localize(None).normalize()
            days=sessions[(sessions>=entry)&(sessions<exit)]
            if len(days)!=10 or (first.hour,first.minute)!=(9,30) or (last.hour,last.minute)!=(9,30):
                raise ValueError('Not a ten-session open11 trade')
            period=prices[row['symbol']].reindex(days)
            if period[['open','high','low','close']].isna().any().any():raise ValueError('Incomplete holding-period prices')
            if not np.isclose(period.iloc[0].open,row['entry_price'],atol=1e-8,rtol=1e-10):raise ValueError('Entry price basis mismatch')
            exit_daily=float(prices[row['symbol']].loc[exit,'open'])
            if not np.isclose(exit_daily,row['exit_price'],atol=1e-8,rtol=1e-10):
                if not np.isclose(observations[exit,row['symbol']]['open'],row['exit_price'],atol=1e-8,rtol=1e-10):
                    raise ValueError('Exit not reconciled to actual frozen 5m opening')
            expected=(row['quantity']*(row['exit_price']-row['entry_price'])-row['entry_fees']-row['exit_fees']+row['dividends'])/(row['quantity']*row['entry_price'])
            if not np.isclose(expected,row['return_pct'],atol=1e-12):raise ValueError('Net return reconciliation failed')
            effective_high=pd.Series({d:float(prices[row['symbol']].loc[d,'high']) if (d,row['symbol']) in fallback
                else observations[d,row['symbol']]['high'] for d in days})
            peak=float(effective_high.max());peak_day=effective_high.idxmax()
            peak_including_sale=max(peak,float(row['exit_price']))
            rows.append(dict(row,net_return_pct=100*row['return_pct'],price_return_pct=100*(row['exit_price']/row['entry_price']-1),
                entry_session=str(entry.date()),exit_session=str(exit.date()),holding_sessions=10,
                daily_fallback_sessions=sum((d,row['symbol']) in fallback for d in days),
                daily_only_peak_pct=100*(float(period.high.max())/row['entry_price']-1),
                peak_10_sessions_pct=100*(peak/row['entry_price']-1),
                peak_until_sale_pct=100*(peak_including_sale/row['entry_price']-1),
                peak_session=str((exit if row['exit_price']>peak else peak_day).date()),
                giveback_from_peak_pct=100*(1-row['exit_price']/peak_including_sale)))
        frame=pd.DataFrame(rows);frame.to_csv(root/'time-exits-with-peaks.csv',index=False)
        distribution=pd.DataFrame(dict(bin=LABELS))
        fields=['net_return_pct','peak_10_sessions_pct','peak_until_sale_pct']
        for col in fields:
            counts=pd.cut(frame[col],BINS,labels=LABELS,right=False).value_counts(sort=False)
            distribution[col+'_count']=counts.to_numpy();distribution[col+'_share_pct']=100*counts.to_numpy()/len(frame)
        distribution.to_csv(root/'distribution.csv',index=False)
        annual=[]
        for year,g in frame.groupby(pd.to_datetime(frame.exit_session).dt.year):
            annual.append(dict(year=int(year),trades=len(g),net_mean_pct=g.net_return_pct.mean(),net_median_pct=g.net_return_pct.median(),
                peak_mean_pct=g.peak_until_sale_pct.mean(),peak_median_pct=g.peak_until_sale_pct.median()))
        pd.DataFrame(annual).to_csv(root/'annual.csv',index=False)
        result=dict(status='COMPLETED_READ_ONLY',reference='Q051 vol20 + regime, annual causal models, 2021-01-01 to 2026-10-01',
            closed_trades=len(trades),time_exits=len(frame),time_exit_share_pct=100*len(frame)/len(trades),
            time_exit_symbols=int(frame.symbol.nunique()),time_exit_winners=int(frame.net_return_pct.gt(0).sum()),
            time_exit_losers=int(frame.net_return_pct.lt(0).sum()),time_exit_win_pct=100*frame.net_return_pct.gt(0).mean(),
            exit_reasons=trades.exit_reason.value_counts().to_dict(),statistics={col:describe(frame[col]) for col in fields},
            peak_definition='maximum effective replay high of ten fully held regular sessions (qualified 5m or same canonical daily fallback), plus actual open11 sale price; no high/low of sale session included',
            daily_peak_coverage='396/396 have ten complete official sessions; all entries match daily opens; 37 exits use their reconciled frozen 5m opening instead of daily opening',
            daily_fallback_symbol_sessions=int(frame.daily_fallback_sessions.sum()),
            source_hashes={str(p):digest(p) for p in [source,SOURCE/'result/report.json',*paths,Path(__file__)]},
            weighting='equal weight per closed trade; no capital weighting; repeated symbols are separate trades',
            limitations=['Selected survivors reaching open11, not all entries: cannot infer TP profitability from this subset.',
                'Observed maxima are hindsight measures, not attainable sale prices guaranteed by a rule.',
                'Same qualified 5m/daily fallback price mix and historical-vintage/survivorship limitations as reference.'],
            SQL_writes=0,provider_calls=0,orders=0)
        atomic_json(root/'report.json',result)
        atomic_json(root/'progress.json',dict(status='COMPLETED_READ_ONLY',trades=len(frame)))
    return result


if __name__=='__main__':print(json.dumps(audit(),ensure_ascii=False))
