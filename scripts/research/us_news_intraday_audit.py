"""Frozen retrospective news/intraday association: read-only SQL, no API or model."""
from datetime import date, datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
from sqlalchemy import text
from database.connection import get_sqlalchemy_engine
from common.universe_files import load_universe_file_symbols
from common.market_calendar import get_market_calendar
from scripts.research.us_prospective_directional_collection_audit import query
from service.market.intraday_backfill import atomic_json

HORIZONS=(5,15,30,60)
NS_MINUTE=60_000_000_000


def prepare_news(frame,sessions):
    frame=frame.copy()
    for col in ('positive_score','negative_score'):
        frame[col]=pd.to_numeric(frame[col],errors='coerce')
    frame=frame[frame.positive_score.between(0,1)&frame.negative_score.between(0,1)]
    frame=frame.sort_values('available_at').drop_duplicates(['symbol','dedupe_hash','published_at_utc'])
    published=pd.to_datetime(frame.published_at_utc,utc=True)
    # Midnight UTC can be an imprecise date-only placeholder. Do not invent the time.
    frame=frame[~(published.dt.hour.eq(0)&published.dt.minute.eq(0)&published.dt.second.eq(0))].copy()
    published=pd.to_datetime(frame.published_at_utc,utc=True)
    frame['day']=published.dt.tz_convert('America/New_York').dt.date
    frame['pub_ns']=published.astype('int64')
    frame['available_ns']=pd.to_datetime(frame.available_at,utc=True).astype('int64')
    grouped=frame.groupby(['symbol','day','pub_ns'],as_index=False).agg(
        positive=('positive_score',lambda x:x.gt(.9).any()),negative=('negative_score',lambda x:x.gt(.9).any()),
        articles=('article_id','size'),available_ns=('available_ns','max'))
    grouped['group']=np.select([grouped.positive&grouped.negative,grouped.positive,grouped.negative],
        ['mixed','positive_only','negative_only'],default='no_strong_score')
    grouped['open_ns']=grouped.day.map({s.session_date:pd.Timestamp(s.open_at_utc).value for s in sessions})
    grouped['close_ns']=grouped.day.map({s.session_date:pd.Timestamp(s.close_at_utc).value for s in sessions})
    grouped['bucket']=np.select([grouped.open_ns.isna(),grouped.pub_ns.lt(grouped.open_ns),grouped.pub_ns.lt(grouped.close_ns)],
        ['non_session','pre_open','regular'],default='post_close')
    return grouped


def valid_bars(frame):
    frame=frame.copy()
    for col in ('open','high','low','close','volume'):
        frame[col]=pd.to_numeric(frame[col],errors='coerce')
    valid=frame.is_filled.eq(0)&frame.data_adjustment.eq('raw')&frame.volume.gt(0)
    valid &= frame[['open','high','low','close']].gt(0).all(axis=1)
    valid &= np.isfinite(frame[['open','high','low','close']]).all(axis=1)
    valid &= frame.high.ge(frame[['open','close']].max(axis=1))&frame.low.le(frame[['open','close']].min(axis=1))
    valid &= frame.session_tag.eq('regular')
    frame=frame[valid].copy()
    frame['ts']=pd.to_datetime(frame.bar_timestamp,utc=True).astype('int64')
    frame['end_ts']=pd.to_datetime(frame.bar_end_timestamp,utc=True).astype('int64')
    frame=frame[frame.end_ts.eq(frame.ts+5*NS_MINUTE)]
    return frame.sort_values(['symbol','ts'])


def event_returns(events,bars):
    """Strict continuous windows; no forward fill; regular session only.

    Publication -> ceil5m +5m delay (5..10min), then entry at bar OPEN.
    Exit is CLOSE of last fully completed bar. No same-news containing-bar return.
    """
    output=[]
    groups={symbol:part for symbol,part in bars.groupby('symbol',sort=False)}
    for symbol,part in events.groupby('symbol',sort=False):
        prices=groups.get(symbol)
        if prices is None:continue
        stamps=prices.ts.to_numpy(dtype='int64');ends=prices.end_ts.to_numpy(dtype='int64')
        opens=prices.open.to_numpy();closes=prices.close.to_numpy()
        part=part.sort_values('pub_ns')
        all_pubs=part.pub_ns.to_numpy(dtype='int64')
        for event in part.itertuples():
            if event.bucket not in ('regular','pre_open'):continue
            pub=int(event.pub_ns)
            entry=int(event.open_ns) if event.bucket=='pre_open' else ((pub+5*NS_MINUTE-1)//(5*NS_MINUTE)+1)*5*NS_MINUTE
            if entry>=event.close_ns:continue
            index=int(np.searchsorted(stamps,entry))
            if index>=len(stamps) or stamps[index]!=entry:continue
            row=dict(symbol=symbol,day=str(event.day),month=str(event.day)[:7],group=event.group,
                bucket=event.bucket,articles=int(event.articles),published_at_utc=pd.Timestamp(pub,tz='UTC').isoformat(),
                entry_at_utc=pd.Timestamp(entry,tz='UTC').isoformat(),lag_minutes=(entry-pub)/NS_MINUTE,
                metadata_available_before_entry=event.available_ns<entry)
            before=int(np.searchsorted(ends,pub,side='right'))-1
            if event.bucket=='regular' and before>=6 and pub-ends[before]<=5*NS_MINUTE:
                prior=before-6
                if stamps[prior]>=event.open_ns and ends[before]-ends[prior]==30*NS_MINUTE:
                    row['pre30_pct']=(closes[before]/closes[prior]-1)*100
            next_index=int(np.searchsorted(all_pubs,pub,side='right'))
            next_pub=all_pubs[next_index] if next_index<len(all_pubs) else np.iinfo(np.int64).max
            for horizon in HORIZONS:
                count=horizon//5;last=index+count-1
                exit_time=entry+horizon*NS_MINUTE
                if last>=len(stamps) or exit_time>event.close_ns:continue
                expected=entry+np.arange(count)*5*NS_MINUTE
                if not np.array_equal(stamps[index:last+1],expected):continue
                row[f'post{horizon}_pct']=(closes[last]/opens[index]-1)*100
                row[f'no_following_news_{horizon}']=bool(next_pub>=exit_time)
            if any(f'post{h}_pct' in row for h in HORIZONS):output.append(row)
    return pd.DataFrame(output)


def metrics(frame):
    result={}
    for group,part in frame.groupby('group'):
        entry=dict(events=len(part),symbols=int(part.symbol.nunique()),days=int(part.day.nunique()),returns={})
        for col in ('pre30_pct',)+tuple(f'post{h}_pct' for h in HORIZONS):
            if col not in part:continue
            values=part[col].dropna()
            if not len(values):continue
            daily=part.groupby('day')[col].mean().dropna()
            entry['returns'][col]=dict(n=len(values),mean=float(values.mean()),median=float(values.median()),
                up_pct=float(values.gt(0).mean()*100),equal_day_mean=float(daily.mean()),
                days=len(daily),positive_days_pct=float(daily.gt(0).mean()*100),
                p01=float(values.quantile(.01)),p99=float(values.quantile(.99)))
        result[group]=entry
    return result


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    universe=Path('config/univers_batch/univers_filtred_tradable.txt')
    symbols=load_universe_file_symbols('universe-file:'+str(universe))
    protocol=dict(start='2025-01-01',end='2025-02-28',source='alpaca_iex',interval='5m',
        universe=str(universe),universe_count=len(symbols),universe_sha256=hashlib.sha256(universe.read_bytes()).hexdigest(),
        threshold_strict=.9,primary='regular publication, entry ceil5m+5m, returns 5/15/30/60 min',
        primary_label='any article >0.9 at publication timestamp, positive-only/negative-only/mixed/neither',
        secondary='pre-open publication, entry official session open, same horizons',
        common_cohort='>=10 valid regular-session dates in EACH month; not full coverage certification',
        continuity='all 5m bars in holding window present, valid, positive-volume, session regular; no filling',
        identity='current universe, raw intraday prices, no overnight return, historical identities not qualified',
        availability='GREATEST current news/sentiment updated_at: conservative diagnostic, not immutable PIT proof',
        snapshot_at_utc=datetime.now(timezone.utc).isoformat(),sql_writes=False,api_calls=0,trained=False,
        limitations=['Retrospective association not causality or exploitable strategy',
            'Partial backfill (especially February), IEX-only prices/volumes',
            'Overlapping events, current universe survivorship, date-only timestamps excluded',
            'No market/sector-adjusted return, bid/ask, fees, execution or historical sentiment availability proof'])
    atomic_json(output/'protocol.json',protocol)
    atomic_json(output/'progress.json',dict(status='RUNNING',stage='SQL snapshot'))
    engine=get_sqlalchemy_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            news=pd.DataFrame(query(conn,"""SELECT STRAIGHT_JOIN n.article_id,s.symbol,n.published_at_utc,
                n.dedupe_hash,s.positive_score,s.negative_score,GREATEST(n.updated_at,s.updated_at) available_at
                FROM news_raw n FORCE INDEX(idx_news_raw_published_utc)
                JOIN news_ticker_sentiment s ON s.article_id=n.article_id
                WHERE n.published_at_utc>='2025-01-01' AND n.published_at_utc<'2025-03-01 05:00:00'
                AND s.symbol IN :symbols AND s.inference_status='success'""",symbols))
            bars=pd.DataFrame(query(conn,"""SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,
                open,high,low,close,volume,is_filled,data_adjustment,session_tag,provider,data_source
                FROM stock_bars_intraday WHERE trade_date BETWEEN '2025-01-01' AND '2025-02-28'
                AND interval_code='5m' AND data_source='alpaca_iex' AND provider='alpaca'
                AND symbol IN :symbols""",symbols))
            conn.rollback()
    finally:engine.dispose()
    if news.empty or bars.empty:raise ValueError('News/sentiments ou barres intraday absents')
    news.to_parquet(output/'news_snapshot.parquet',index=False)
    bars.to_parquet(output/'bars_snapshot.parquet',index=False)
    atomic_json(output/'progress.json',dict(status='RUNNING',stage='event windows',news_rows=len(news),bars=len(bars)))
    clean=valid_bars(bars)
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    sessions=[s for s in calendar.sessions(date(2025,1,1),date(2025,2,28)) if s.is_open]
    events=prepare_news(news,sessions)
    joined=event_returns(events,clean)
    if joined.empty:raise ValueError('Aucune fenêtre intraday exploitable')
    clean['month']=pd.to_datetime(clean.trade_date).dt.strftime('%Y-%m')
    coverage=clean.groupby(['symbol','month']).trade_date.nunique().unstack(fill_value=0)
    common=coverage[(coverage.get('2025-01',0)>=10)&(coverage.get('2025-02',0)>=10)].index
    joined['common_cohort']=joined.symbol.isin(common)
    joined.to_parquet(output/'event_returns.parquet',index=False)
    views={}
    for cohort,frame in [('available',joined),('common_cohort',joined[joined.common_cohort])]:
        for bucket in ('regular','pre_open'):
            sub=frame[frame.bucket.eq(bucket)]
            views[f'{cohort}_{bucket}']={month:metrics(part) for month,part in sub.groupby('month')}
            isolated=sub[sub.get('no_following_news_30',pd.Series(False,index=sub.index)).eq(True)]
            views[f'{cohort}_{bucket}_no_other_scored_news_30m']={month:metrics(part) for month,part in isolated.groupby('month')}
    report=dict(protocol=protocol,raw_news_rows=len(news),timed_events=len(events),events_with_windows=len(joined),
        metadata_available_before_entry=int(joined.metadata_available_before_entry.sum()),common_symbols=len(common),
        coverage={m:dict(bars=len(p),symbols=int(p.symbol.nunique()),days=int(p.trade_date.nunique()))
            for m,p in bars.groupby(pd.to_datetime(bars.trade_date).dt.strftime('%Y-%m'))},
        valid_regular_bars=len(clean),bucket_counts=events.bucket.value_counts().to_dict(),views=views,
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.parquet')})
    atomic_json(output/'report.json',report)
    atomic_json(output/'progress.json',dict(status='COMPLETED',report=str(output/'report.json')))
    print('COMPLETED',output,flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',default='artifacts/research/us_news_intraday/jan-feb-2025-20261011-v1')
    args=parser.parse_args()
    if (Path(args.output_dir)/'report.json').exists():
        parser.error('Rapport déjà présent : utiliser un nouveau répertoire pour un nouvel instantané')
    try:run(args.output_dir)
    except Exception as exc:
        atomic_json(Path(args.output_dir)/'progress.json',dict(status='FAILED',error=str(exc)))
        raise
