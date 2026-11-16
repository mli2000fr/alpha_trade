"""Observed H10 prices after actual Q051 stops; descriptive, not an SL-free replay."""
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import requests
from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_stop_h10_audit/20261115-v1')
SOURCES={
    'SANS_TP':Path('artifacts/research/us_q051_global_rank_h10/20261115-v1/cases/Q051_REFERENCE/result/trades.csv'),
    'TP20':Path('artifacts/research/us_q051_vol20_regime_tp20/20261115-v1/result/trades.csv')}
TAIL=Path('artifacts/models/model-factory-20261114122842-c59bed/oracle_path')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def run(root=ROOT):
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    from modelFactory.oracle.security_continuity import load_security_discontinuities,path_crosses_known_discontinuity
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    def no_http(*args,**kwargs):raise ValueError('HTTP forbidden in frozen stop audit')
    with ReadOnlyReplay(root).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
        paths=[shared.ROOT/'inputs/base/daily.parquet',shared.ROOT/'inputs/extra-daily.parquet',
            Path('artifacts/research/us_winner_vol20_extensions/20261109-v1/inputs/daily.parquet')]
        pieces=[];source_hashes={}
        for p in paths:
            owner=shared.ROOT if p in paths[:2] else p.parent.parent
            manifest={k.replace('\\','/'):v for k,v in read(owner/'inputs/manifest.json')['files'].items()}
            relative=str(p.relative_to(owner/'inputs')).replace('\\','/')
            sha=digest(p)
            if sha!=manifest[relative]:raise ValueError('Frozen price source changed')
            source_hashes[str(p)]=sha;pieces.append(pd.read_parquet(p))
        bars=pd.concat(pieces,ignore_index=True)
        if bars.duplicated(['date','symbol']).any():raise ValueError('Duplicate price keys')
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=pd.DatetimeIndex([r.session_date for r in calendar.sessions(date(2021,1,1),date(2026,10,20)) if r.is_open])
        records=[];needed_tail=set()
        for name,path in SOURCES.items():
            source_hashes[str(path)]=digest(path);f=pd.read_csv(path)
            for r in f[f.exit_reason.isin(['STOP','STOP_GAP'])].to_dict('records'):
                entry=pd.Timestamp(r['entry_date']).tz_convert('America/New_York').tz_localize(None).normalize()
                stop=pd.Timestamp(r['exit_date']).tz_convert('America/New_York').tz_localize(None).normalize()
                i=sessions.get_loc(entry);h10=sessions[i+9];open11=sessions[i+10]
                if open11>pd.Timestamp('2026-10-01'):needed_tail.add(r['symbol'])
                records.append(dict(r,scenario=name,entry_session=entry,stop_session=stop,h10_session=h10,open11_session=open11))
        tail_receipts=[]
        for done in sorted((TAIL/'chunks').glob('*/done.json')):
            meta=read(done);symbols=needed_tail.intersection(meta['symbols'])
            if not symbols:continue
            p=done.parent/'bars.parquet'
            if digest(p)!=meta['files']['bars.parquet']:raise ValueError('Cached tail prices changed')
            source_hashes[str(p)]=digest(p)
            f=pd.read_parquet(p,filters=[('symbol','in',sorted(symbols)),('date','>=',pd.Timestamp('2026-09-01')),('date','<=',pd.Timestamp('2026-10-15'))])
            for symbol,g in f.groupby('symbol'):
                anchors=bars[bars.symbol.eq(symbol)].merge(g,on=['date','symbol'],suffixes=('_old','_new'))
                if len(anchors)<5:raise ValueError('Insufficient price-basis anchors')
                error=max(float((anchors[c+'_old']/anchors[c+'_new']-1).abs().max()) for c in ['open','high','low','close'])
                if error>1e-6:raise ValueError('Historical price basis differs at tail')
                supplement=g[g.date.gt(pd.Timestamp('2026-10-01'))].copy()
                existing=pd.MultiIndex.from_frame(bars[['date','symbol']])
                if pd.MultiIndex.from_frame(supplement[['date','symbol']]).isin(existing).any():raise ValueError('Tail would overwrite a frozen price')
                bars=pd.concat([bars,supplement],ignore_index=True)
                tail_receipts.append(dict(symbol=symbol,source=str(p),anchors=len(anchors),max_relative_ohlc_difference=error,appended=len(supplement)))
        prices={s:g.set_index('date').sort_index() for s,g in bars.groupby('symbol')}
        breaks=load_security_discontinuities();rows=[]
        for r in records:
            symbol=r['symbol'];entry=r['entry_session'];h10=r['h10_session'];op11=r['open11_session']
            dates=sessions[(sessions>=entry)&(sessions<=h10)];period=prices[symbol].reindex(dates)
            if len(period)!=10 or path_crosses_known_discontinuity(symbol,entry,op11,breaks):raise ValueError('Unqualified ten-session path')
            if not np.isclose(period.iloc[0].open,r['entry_price'],atol=1e-8,rtol=1e-10):raise ValueError('Entry price basis mismatch')
            close=period.iloc[-1].close
            opening=prices[symbol].reindex([op11]).iloc[0].open
            complete=bool(period.high.notna().all() and period.high.gt(0).all())
            after=period[period.index>r['stop_session']]
            rows.append(dict(r,h10_price_positive=bool(close>r['entry_price']) if pd.notna(close) else None,
                h10_return_pct=100*(close/r['entry_price']-1) if pd.notna(close) else np.nan,
                open11_return_pct=100*(opening/r['entry_price']-1) if pd.notna(opening) else np.nan,
                path_complete=complete,path_peak_pct=100*(period.high.max()/r['entry_price']-1) if complete else np.nan,
                after_stop_later_sessions_peak_pct=100*(after.high.max()/r['entry_price']-1) if len(after) and after.high.notna().all() else np.nan))
        frame=pd.DataFrame(rows);frame.to_csv(root/'stopped-trades-followup.csv',index=False)
        summary=[]
        for name,g in frame.groupby('scenario',sort=False):
            close=g.h10_return_pct.dropna();opening=g.open11_return_pct.dropna();peaks=g.path_peak_pct.dropna()
            later=g.after_stop_later_sessions_peak_pct.dropna()
            summary.append(dict(scenario=name,stopped_trades=len(g),symbols=int(g.symbol.nunique()),
                h10_qualified=len(close),h10_positive=int(close.gt(0).sum()),h10_positive_pct=100*close.gt(0).mean(),
                h10_nonpositive=int(close.le(0).sum()),h10_mean_return_pct=close.mean(),h10_median_return_pct=close.median(),
                h10_positive_mean_return_pct=close[close.gt(0)].mean(),
                open11_qualified=len(opening),open11_positive=int(opening.gt(0).sum()),open11_positive_pct=100*opening.gt(0).mean(),
                path_qualified=len(peaks),path_ever_positive=int(peaks.gt(0).sum()),path_ever_positive_pct=100*peaks.gt(0).mean(),
                path_touched_5pct=int(peaks.ge(5).sum()),path_touched_10pct=int(peaks.ge(10).sum()),path_touched_20pct=int(peaks.ge(20).sum()),
                later_sessions_observed=len(later),later_sessions_above_entry=int(later.gt(0).sum()),
                later_sessions_above_entry_pct_all_stops=100*later.gt(0).sum()/len(g)))
        pd.DataFrame(summary).to_csv(root/'summary.csv',index=False)
        report=dict(status='COMPLETED_READ_ONLY',results=summary,source_hashes=source_hashes,tail_price_receipts=tail_receipts,
            definition='H10 = tenth held official session, entry session included; positive means closing price > original entry price, gross price return',
            open11='Counterfactual price at the following opening, not a new portfolio replay',
            path='Maximum daily high between entry and H10, can occur BEFORE or AFTER the actual stop; not evidence of a post-stop rebound by itself',
            later_sessions='Conservative lower bound for recovery: complete days strictly after the stop date, excluding unknown same-day ordering',
            limitations=['No claim that removing SL improves capital return; exposure, severe losers and capacity would change.',
                'Gross descriptive prices, no hypothetical post-stop fees/dividends or same-day intrabar recovery invented.',
                'Same frozen/revised prices and contemporary universe limitations as reference.'],
            SQL_writes=0,provider_calls=0,orders=0)
        atomic_json(root/'report.json',report)
    return report


if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,default=str))
