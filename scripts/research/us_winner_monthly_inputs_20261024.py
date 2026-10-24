"""Bounded month-partitioned inputs for the monthly Winner experiment.

Reuse sealed local archives where their query range covers the request; otherwise
read alpha_trade in READ ONLY transactions. No provider calls or database writes.
"""
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text, bindparam

from scripts.research import us_winner_native_grid_2017_2026_20261023 as grid
from scripts.research.us_winner_grid_supervisor_repair_20261023 import read_json

ARCHIVE = Path('artifacts/research/us_winner_global_selector/20261023-v1')
SHADOW_START = date(2019, 7, 1)
START = date(2020, 1, 1)
END = date(2024, 12, 31)


def sessions(start=SHADOW_START, end=END):
    return [s for s in grid.calendar().sessions(start-timedelta(days=14), end+timedelta(days=100)) if s.is_open]


def ranked_scores():
    meta = read_json(ARCHIVE/'scores.json')
    grid.base.verify({str(ARCHIVE/'top100.parquet'): meta['sha256']})
    schedule = sessions()
    seed = max(s.session_date for s in schedule if s.session_date < SHADOW_START)
    frame = pd.read_parquet(ARCHIVE/'top100.parquet')
    frame = frame[frame.date.between(pd.Timestamp(seed), pd.Timestamp(END)) & frame['rank'].le(20)].copy()
    expected = {pd.Timestamp(s.session_date) for s in schedule if seed <= s.session_date <= END}
    if set(frame.date) != expected or frame.duplicated(['date', 'symbol']).any():
        raise ValueError('Missing/duplicate TOP20 score dates')
    if not frame.groupby('date')['rank'].apply(lambda s: sorted(s) == list(range(1, 21))).all():
        raise ValueError('Original TOP20 incomplete; no replacements after data exclusions')
    if not (pd.to_datetime(frame.model_available_date) < frame.date).all():
        raise ValueError('Noncausal Oracle model availability')
    return frame.sort_values(['date', 'rank']).reset_index(drop=True), seed


def read_sql(conn, query, params):
    conn.execute(text('SET SESSION MAX_EXECUTION_TIME=60000'))
    conn.commit()
    with conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        if conn.execute(text('SELECT DATABASE()')).scalar() != 'alpha_trade':
            raise ValueError('US database only')
        stmt = text(query)
        if 'symbols' in params:
            stmt = stmt.bindparams(bindparam('symbols', expanding=True))
        return pd.read_sql(stmt, conn, params=params)


def prepare(root):
    folder = root/'inputs'; folder.mkdir(parents=True, exist_ok=True)
    marker = folder/'manifest.json'
    if marker.exists():
        m = read_json(marker)
        grid.base.verify({str(folder/n): sha for n, sha in m['files'].items()})
        return m
    scores, seed = ranked_scores()
    if not (folder/'scores.parquet').exists():
        scores.to_parquet(folder/'scores.parquet', index=False)
    else:
        pd.testing.assert_frame_equal(pd.read_parquet(folder/'scores.parquet'), scores, check_exact=True)
    symbols = sorted(set(scores.symbol) | {'SPY'})
    schedule = {s.session_date: s for s in sessions()}
    daily_start = SHADOW_START-timedelta(days=650)
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    files, receipts, quality_parts = {}, [], []
    try:
        with engine.connect() as conn:
            for i, symbol in enumerate(symbols):
                grid.atomic_json(root/'progress.json', dict(status='INPUT_SNAPSHOT_READ_ONLY', symbol=symbol,
                    completed_symbols=i, total_symbols=len(symbols), completed_runs=0, total_runs=10))
                target = folder/'symbols'/symbol; target.mkdir(parents=True, exist_ok=True)
                receipt_file = target/'snapshot.json'
                if receipt_file.exists():
                    receipt = read_json(receipt_file)
                    grid.base.verify({str(target/n): h for n, h in receipt['files'].items()})
                else:
                    cached = ARCHIVE/'symbols'/symbol
                    cached_meta = read_json(cached/'snapshot.json') if (cached/'snapshot.json').exists() else None
                    raw_reused = bool(cached_meta and pd.Timestamp(cached_meta['first']).date() <= seed
                                      and pd.Timestamp(cached_meta['last']).date() >= END)
                    if raw_reused:
                        grid.base.verify({str(cached/'bars.parquet'): cached_meta['files']['bars.parquet']})
                        raw = pd.read_parquet(cached/'bars.parquet')
                        raw = raw[pd.to_datetime(raw.trade_date).between(pd.Timestamp(seed), pd.Timestamp(END))].copy()
                    else:
                        raw = read_sql(conn, "SELECT symbol,trade_date,bar_timestamp,bar_end_timestamp,open,high,low,close,volume,payload_hash "
                            "FROM stock_bars_intraday FORCE INDEX(PRIMARY) WHERE symbol=:symbol AND bar_timestamp>=:start AND bar_timestamp<:end "
                            "AND provider='alpaca' AND data_source='alpaca_sip' AND interval_code='5m' AND market_code='US_EQ' "
                            "AND session_tag='regular' AND data_adjustment='raw' AND is_filled=0 ORDER BY bar_timestamp",
                            dict(symbol=symbol, start=str(seed), end=str(END+timedelta(days=1))))
                    raw['trade_date'] = pd.to_datetime(raw.trade_date)
                    for col in ['bar_timestamp', 'bar_end_timestamp']:
                        raw[col] = pd.to_datetime(raw[col], utc=True)
                    valid_parts, quality = [], []
                    for stamp, part in raw.groupby('trade_date', sort=True):
                        day = pd.Timestamp(stamp).date()
                        good = day in schedule and grid.base.qualify_session(part, schedule[day])
                        quality.append(dict(symbol=symbol, date=day, qualified=bool(good), rows=len(part)))
                        if good:
                            valid_parts.append(part)
                    qualified = pd.concat(valid_parts, ignore_index=True) if valid_parts else raw.iloc[:0]
                    q = pd.DataFrame(quality, columns=['symbol', 'date', 'qualified', 'rows'])
                    q.to_parquet(target/'quality.parquet', index=False)
                    names = ['quality.parquet']
                    for month, part in qualified.groupby(qualified.trade_date.dt.strftime('%Y-%m'), sort=True):
                        name = f'sip-{month}.parquet'; part.to_parquet(target/name, index=False); names.append(name)
                    daily = read_sql(conn, 'SELECT symbol,date,open,high,low,close,volume,data_source,data_adjustment,is_filled '
                        'FROM stock_bars_daily FORCE INDEX(PRIMARY) WHERE symbol=:symbol AND date BETWEEN :start AND :end ORDER BY date',
                        dict(symbol=symbol, start=str(daily_start), end=str(END)))
                    daily.to_parquet(target/'daily.parquet', index=False); names.append('daily.parquet')
                    receipt = dict(symbol=symbol, raw_local_archive_reused=raw_reused, SQL_reads_only=True,
                        observed_at_utc=datetime.now(timezone.utc).isoformat(),
                        reused_raw_sha256=cached_meta['files']['bars.parquet'] if raw_reused else None,
                        files={n: grid.base.digest(target/n) for n in names})
                    grid.base.save_new(receipt_file, receipt)
                receipts.append(dict(symbol=symbol, snapshot_sha256=grid.base.digest(receipt_file)))
                quality_parts.append(pd.read_parquet(target/'quality.parquet'))
                for name, sha in receipt['files'].items():
                    files[str((target/name).relative_to(folder))] = sha
                files[str(receipt_file.relative_to(folder))] = grid.base.digest(receipt_file)
                grid.atomic_json(root/'progress.json', dict(status='INPUT_SNAPSHOT_READ_ONLY', symbol=symbol,
                    completed_symbols=i+1, total_symbols=len(symbols), completed_runs=0, total_runs=10))
            for name, query in [
                ('sectors.parquet', 'SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols'),
                ('actions.parquet', 'SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events '
                 'WHERE symbol IN :symbols AND ex_date BETWEEN :start AND :end')]:
                if not (folder/name).exists():
                    params = dict(symbols=symbols)
                    if name == 'actions.parquet':
                        params.update(start=str(seed), end=str(END))
                    read_sql(conn, query, params).to_parquet(folder/name, index=False)
                files[name] = grid.base.digest(folder/name)
    finally:
        engine.dispose()
    quality = pd.concat(quality_parts, ignore_index=True)
    quality.to_parquet(folder/'quality.parquet', index=False)
    sectors = {str(r.symbol): str(r.sector) for r in pd.read_parquet(folder/'sectors.parquet').dropna().itertuples()}
    actions = pd.read_parquet(folder/'actions.parquet'); actions['ex_date'] = pd.to_datetime(actions.ex_date)
    good = {(str(r.symbol), pd.Timestamp(r.date).date()): True for r in quality[quality.qualified].itertuples()}
    days = [day for day in schedule if day <= END]
    cohort = grid.qualify_cohort(scores, good, actions, sectors, days)
    cohort.to_parquet(folder/'cohort.parquet', index=False)
    for name in ['scores.parquet', 'quality.parquet', 'cohort.parquet']:
        files[name] = grid.base.digest(folder/name)
    result = dict(files=files, receipts=receipts, scores_rows=len(scores), eligible_signals=int(cohort.selected.sum()),
        start=str(SHADOW_START), end=str(END), strict_common_future_window=40,
        future_coverage_selection_bias=True, current_sectors_non_PIT=True, SQL_writes=False, provider_calls=0)
    grid.base.save_new(marker, result)
    return result


class Tape:
    def __init__(self, root):
        self.folder = root/'inputs'
        self.manifest = read_json(self.folder/'manifest.json')
        grid.base.verify({str(self.folder/n): h for n, h in self.manifest['files'].items()})
        self.schedule = {s.session_date: s for s in sessions()}
        self.cohort = pd.read_parquet(self.folder/'cohort.parquet')
        self.sectors = {str(r.symbol): str(r.sector) for r in pd.read_parquet(self.folder/'sectors.parquet').dropna().itertuples()}
        self.actions = pd.read_parquet(self.folder/'actions.parquet')
        self.actions['ex_date'] = pd.to_datetime(self.actions.ex_date)
        self.actions['payable_date'] = pd.to_datetime(self.actions.payable_date).dt.date
        daily = pd.concat([pd.read_parquet(self.folder/'symbols'/r['symbol']/'daily.parquet') for r in self.manifest['receipts']], ignore_index=True)
        daily['date'] = pd.to_datetime(daily.date)
        if daily.duplicated(['symbol', 'date']).any():
            raise ValueError('Ambiguous daily rows')
        fields = ['open', 'high', 'low', 'close', 'volume']; values = daily[fields].to_numpy(float)
        valid = (np.isfinite(values).all(axis=1) & (values > 0).all(axis=1) & daily.is_filled.eq(0)
                 & daily.data_adjustment.eq('split') & ~daily.data_source.str.contains('iex', case=False, na=True))
        daily.loc[~valid, fields] = np.nan
        self.pivots = {k: daily.pivot(index='date', columns='symbol', values=k).astype(float) for k in fields}

    @lru_cache(maxsize=96)
    def month(self, symbol, month):
        path = self.folder/'symbols'/symbol/f'sip-{month}.parquet'
        if not path.exists():
            return pd.DataFrame(columns=['trade_date', 'bar_timestamp', 'bar_end_timestamp', 'open', 'high', 'low', 'close', 'volume'])
        f = pd.read_parquet(path)
        f['session_close'] = f.trade_date.map({pd.Timestamp(d): s.close_at_utc for d, s in self.schedule.items()})
        return f

    def day(self, symbol, day):
        f = self.month(symbol, day.strftime('%Y-%m'))
        return f[f.trade_date.eq(pd.Timestamp(day))].copy()

    def __call__(self, day, symbols):
        parts = [self.day(s, day).rename(columns={'bar_timestamp': 'timestamp'}) for s in symbols]
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    def path(self, symbol, start, end):
        parts = [self.month(symbol, str(m)) for m in pd.period_range(start.date(), end.date(), freq='M')]
        f = pd.concat(parts, ignore_index=True)
        return f[f.bar_timestamp.ge(start) & f.bar_timestamp.le(end)].copy()
