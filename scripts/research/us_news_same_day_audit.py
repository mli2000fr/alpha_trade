"""Frozen same-day news association; read-only SQL, no API or fitted model."""
from datetime import date
from pathlib import Path
import hashlib
import json
import re
import numpy as np
import pandas as pd
from sqlalchemy import text
from common.market_calendar import get_market_calendar
from database.connection import get_sqlalchemy_engine
from scripts.research.us_prospective_directional_collection_audit import query
from service.alpaca.options_history_backfill import atomic_json

OUT = Path('artifacts/research/us_news_same_day/audit-202510-20261011-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')


def attach_sessions(news, sessions):
    news = news.copy()
    published = pd.to_datetime(news.published_at_utc, utc=True)
    local = published.dt.tz_convert('America/New_York')
    days = local.dt.tz_localize(None).dt.normalize()
    opens = {pd.Timestamp(s.session_date):pd.Timestamp(s.open_at_utc) for s in sessions}
    closes = {pd.Timestamp(s.session_date):pd.Timestamp(s.close_at_utc) for s in sessions}
    news['day'] = days
    news['open_at'] = pd.to_datetime(days.map(opens), utc=True)
    news['close_at'] = pd.to_datetime(days.map(closes), utc=True)
    news['bucket'] = np.select([news.open_at.isna(), published.lt(news.open_at), published.lt(news.close_at)],
                              ['non_session', 'pre_open', 'regular'], default='post_close')
    # Exact midnight may be a date-only placeholder: do not invent publication hour.
    news['midnight_ambiguous'] = published.dt.hour.eq(0) & published.dt.minute.eq(0) & published.dt.second.eq(0)
    available = pd.to_datetime(news.available_at, utc=True)
    news['available_before_open'] = available.lt(news.open_at) & published.lt(news.open_at)
    news['available_before_close'] = available.lt(news.close_at) & published.lt(news.close_at)
    return news


def aggregate(news):
    groups = news.groupby(['day','symbol'], as_index=False).agg(
        articles=('article_id','size'), positive=('positive_score',lambda x:x.gt(.9).any()),
        negative=('negative_score',lambda x:x.gt(.9).any()))
    groups['group'] = np.select([groups.positive & groups.negative, groups.positive, groups.negative],
                               ['mixed','positive_only','negative_only'], default='no_strong_score')
    return groups


def describe(frame):
    result = {}
    for group, part in frame.groupby('group'):
        item = dict(observations=len(part), symbols=int(part.symbol.nunique()), days=int(part.day.nunique()))
        for column in ['close_close_pct','gap_pct','open_close_pct','excess_spy_pct']:
            values = part[column].dropna()
            daily = part.groupby('day')[column].mean().dropna()
            item[column] = dict(n=len(values), mean=float(values.mean()) if len(values) else None,
                median=float(values.median()) if len(values) else None,
                up_pct=float(values.gt(0).mean()*100) if len(values) else None,
                down_pct=float(values.lt(0).mean()*100) if len(values) else None,
                equal_day_mean=float(daily.mean()) if len(daily) else None)
        result[group] = item
    return result


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    raw = UNIVERSE.read_bytes()
    symbols = sorted(set(re.split(r'[,;\s]+',raw.decode('utf-8-sig').strip())))
    calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    sessions = calendar.sessions(date(2024,12,30), date(2026,10,15))
    session_days = pd.DatetimeIndex([s.session_date for s in sessions if s.is_open])
    protocol = dict(start='2025-01-01', end_inclusive='2026-10-09', universe=str(UNIVERSE),
        universe_count=len(symbols), universe_sha256=hashlib.sha256(raw).hexdigest(), threshold_strict=.9,
        rule='Any successfully scored article >0.9; positive only, negative only, mixed, neither',
        primary='Pre-open publication: previous session close -> open and open -> close',
        secondary='Full-day/regular session association only; no intraday post-publication return available',
        after_close='Mapped separately to following session; never same already closed session',
        available_at='Maximum current news/sentiment updated_at; conservative, not immutable first availability',
        sql_writes=False, api_calls=0, trained=False, threshold_tuning=False,
        limitations=['Not causal; retrospective scores may describe prior price move',
            'Current universe survivorship; no sector/size neutrality or economic backtest',
            'Midnight timestamps excluded from timed views as potentially date-only',
            'Daily split-adjusted OHLCV; no bid/ask or intraday reaction prices',
            'No-news baseline differs from companies with news; overlapping symbol/event observations'])
    atomic_json(OUT/'protocol.json',protocol)
    engine = get_sqlalchemy_engine()
    parts=[]
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            for start in pd.date_range('2025-01-01','2026-10-01',freq='MS'):
                end=min(start+pd.offsets.MonthBegin(1),pd.Timestamp('2026-10-10'))
                path=OUT/f'news-{start:%Y-%m}.parquet'
                if path.exists():
                    frame=pd.read_parquet(path)
                else:
                    rows=query(conn,"""SELECT STRAIGHT_JOIN n.article_id,s.symbol,n.published_at_utc,
                        n.dedupe_hash,s.positive_score,s.negative_score,s.model_name,s.model_version,
                        GREATEST(n.updated_at,s.updated_at) AS available_at
                        FROM news_raw n FORCE INDEX (idx_news_raw_published_utc)
                        JOIN news_ticker_sentiment s ON s.article_id=n.article_id
                        WHERE n.published_at_utc>=:start AND n.published_at_utc<:end
                        AND s.symbol IN :symbols AND s.inference_status='success'""",
                        symbols,start=start.to_pydatetime(),end=end.to_pydatetime())
                    frame=pd.DataFrame(rows,columns=['article_id','symbol','published_at_utc','dedupe_hash',
                        'positive_score','negative_score','model_name','model_version','available_at'])
                    frame.to_parquet(path,index=False)
                parts.append(frame)
                atomic_json(OUT/'progress.json',dict(status='RUNNING',month=str(start.date()),rows=sum(len(x) for x in parts)))
                print(f'{start:%Y-%m} sentiment rows={len(frame)}',flush=True)
            bars_path=OUT/'bars.parquet'
            if bars_path.exists():
                bars=pd.read_parquet(bars_path)
            else:
                bars=pd.DataFrame(query(conn,"""SELECT symbol,date,open,high,low,close,volume,is_filled,data_adjustment
                    FROM stock_bars_daily WHERE symbol IN :symbols
                    AND date BETWEEN '2024-12-30' AND '2026-10-15'""",symbols+['SPY']))
                bars.to_parquet(bars_path,index=False)
            conn.rollback()
    finally:
        engine.dispose()
    news=pd.concat(parts,ignore_index=True)
    before=len(news)
    news=news.sort_values('available_at').drop_duplicates(['symbol','dedupe_hash','published_at_utc'])
    for col in ['positive_score','negative_score']:
        news[col]=pd.to_numeric(news[col],errors='coerce')
    news=news[news.positive_score.between(0,1)&news.negative_score.between(0,1)]
    news=attach_sessions(news,[s for s in sessions if s.is_open])
    bars['day']=pd.to_datetime(bars['date'])
    for col in ['open','high','low','close','volume']:
        bars[col]=pd.to_numeric(bars[col],errors='coerce')
    valid=(bars.is_filled.eq(0)&bars.data_adjustment.eq('split')&bars.open.gt(0)&bars.close.gt(0)
        &bars.volume.gt(0)&bars.high.ge(bars[['open','close']].max(axis=1))
        &bars.low.le(bars[['open','close']].min(axis=1)))
    bars.loc[~valid,['open','close']]=np.nan
    previous=bars.pivot(index='day',columns='symbol',values='close').reindex(session_days).shift(1).stack().rename('previous_close')
    bars=bars.merge(previous.reset_index().rename(columns={'level_0':'day'}),on=['day','symbol'],how='left')
    bars['close_close_pct']=(bars.close/bars.previous_close-1)*100
    bars['gap_pct']=(bars.open/bars.previous_close-1)*100
    bars['open_close_pct']=(bars.close/bars.open-1)*100
    spy=bars[bars.symbol.eq('SPY')].set_index('day').close_close_pct
    bars['excess_spy_pct']=bars.close_close_pct-bars.day.map(spy)
    result=dict(protocol=protocol,raw_scored_rows=before,deduped_valid_rows=len(news),
        midnight_ambiguous=int(news.midnight_ambiguous.sum()),bucket_counts=news.bucket.value_counts().to_dict(),views={})
    timed=news[~news.midnight_ambiguous]
    views={'whole_day_retrospective':news[news.bucket.isin(['pre_open','regular'])],
        'pre_open_retrospective':timed[timed.bucket.eq('pre_open')],
        'regular_retrospective_not_post_news_return':timed[timed.bucket.eq('regular')],
        'pre_open_available':timed[timed.bucket.eq('pre_open')&timed.available_before_open],
        'before_close_available':timed[timed.bucket.isin(['pre_open','regular'])&timed.available_before_close]}
    after=timed[timed.bucket.isin(['post_close','non_session'])].copy()
    after['day']=after.day.map(lambda d:session_days[session_days>d][0])
    views['post_close_next_session_retrospective']=after
    for name, frame in views.items():
        grouped=aggregate(frame)
        joined=grouped.merge(bars,on=['day','symbol'],validate='one_to_one')
        joined=joined[joined.day.between('2025-01-01','2026-10-09')&joined.symbol.ne('SPY')]
        joined.to_parquet(OUT/f'{name}.parquet',index=False)
        result['views'][name]={str(year):describe(part) for year,part in joined.groupby(joined.day.dt.year)}
        result.setdefault('monthly',{})[name]={month:describe(part)
            for month,part in joined.groupby(joined.day.dt.strftime('%Y-%m'))}
    baseline=bars[bars.symbol.isin(symbols)&bars.day.between('2025-01-01','2026-10-09')].copy()
    baseline['group']='full_universe'
    result['baseline']={str(year):describe(part) for year,part in baseline.groupby(baseline.day.dt.year)}
    result['source_files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in OUT.glob('*.parquet')}
    atomic_json(OUT/'report.json',result)
    atomic_json(OUT/'progress.json',dict(status='COMPLETED',report=str(OUT/'report.json')))
    print('COMPLETED',OUT,flush=True)


if __name__=='__main__':
    run()
