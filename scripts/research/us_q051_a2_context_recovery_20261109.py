"""Qualify missing pre-signal context from existing SQL, never change rules.

Preserves all v1 results and original archived prints; fills only missing
timestamps from the same raw SIP dataset. No provider requests or SQL writes.
"""
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts.research import us_q051_range_support_a2_20261109 as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

RECOVERY=Path('artifacts/research/us_q051_range_support_a2_context/20261109-v1')
ROOT=Path('artifacts/research/us_q051_range_support_a2/20261109-v2')
OLD_DAY=pilot.frozen_day


def recover():
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.winner_campaign_replay import SqlIntradaySource
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    from database.connection import get_sqlalchemy_engine
    RECOVERY.mkdir(parents=True,exist_ok=False);tapes=RECOVERY/'intraday';tapes.mkdir()
    audit=pd.read_csv(pilot.ROOT/'inputs/coverage-and-motifs.csv')
    rows=audit[~audit.context_qualified];requests=defaultdict(set)
    with replay_market_registry(pilot.shared.restore_registry(pilot.BASE)):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        for row in rows.itertuples():
            day=pd.Timestamp(row.signal_date).date()
            sessions=[s for s in calendar.sessions(day-pd.Timedelta(days=10),day) if s.is_open][-4:]
            for session in sessions:requests[session.session_date].add(row.symbol)
    old=pilot.shared.FrozenPrices(pilot.BASE);receipts=[]
    atomic_json(RECOVERY/'request.json',dict(original=str(pilot.ROOT),original_request_sha256=digest(pilot.ROOT/'request.json'),
        source_code_sha256=digest(Path(__file__)),missing_candidates=len(rows),rules_changed=False,
        purpose='Only fill observed missing pre-signal context, not select by PnL, pattern or future price path',
        provider_calls=0,SQL_writes=0,orders=0))
    with ReadOnlyReplay(RECOVERY).install(),replay_market_registry(pilot.shared.restore_registry(pilot.BASE)):
        engine=get_sqlalchemy_engine(db_name='alpha_trade')
        try:
            with engine.connect() as conn,conn.begin():
                from sqlalchemy import text
                conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
                source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
                for i,(day,names) in enumerate(sorted(requests.items())):
                    from common.winner_pyramiding import regular_bounds
                    opening,closing=regular_bounds(day);expected=pd.date_range(opening,closing,freq='5min',inclusive='left')
                    groups=OLD_DAY(old,day);wanted=[]
                    for name in sorted(names):
                        g=groups.get(name)
                        stamps=pd.DatetimeIndex(pd.to_datetime(g.timestamp,utc=True)) if g is not None else pd.DatetimeIndex([])
                        if not stamps.equals(expected):wanted.append(name)
                    frame=source(day,wanted) if wanted else pd.DataFrame()
                    parts=[]
                    for name,g in frame.groupby('symbol') if not frame.empty else []:
                        prior=groups.get(name)
                        known=set(pd.to_datetime(prior.timestamp,utc=True)) if prior is not None else set()
                        parts.append(g.loc[~pd.to_datetime(g.timestamp,utc=True).isin(known)])
                    extra=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
                    extra.to_parquet(tapes/f'{day}.parquet',index=False)
                    receipts.append(dict(day=str(day),symbols=wanted,queried_rows=len(frame),added_rows=len(extra)))
                    atomic_json(RECOVERY/'progress.json',dict(status='FREEZING_MISSING_PRE_SIGNAL_CONTEXT_READ_ONLY',
                        completed=i+1,total=len(requests),last_date=str(day),added_rows=sum(r['added_rows'] for r in receipts)))
        finally:engine.dispose()
    atomic_json(RECOVERY/'manifest.json',dict(files={str(p.relative_to(RECOVERY)):digest(p) for p in tapes.glob('*.parquet')},
        receipts=receipts,provider_calls=0,SQL_writes=0,orders=0,original_rows_overwritten=0,
        frozen_at_utc=datetime.now(timezone.utc).isoformat()))
    atomic_json(RECOVERY/'progress.json',dict(status='FROZEN_CONTEXT_READY',added_rows=sum(r['added_rows'] for r in receipts)))


def extended_day(source,day):
    groups=dict(OLD_DAY(source,day));path=RECOVERY/'intraday'/f'{day}.parquet'
    if not path.exists():return groups
    extra=pd.read_parquet(path)
    for name,g in extra.groupby('symbol') if not extra.empty else []:
        prior=groups.get(name)
        if prior is not None:
            if set(pd.to_datetime(prior.timestamp,utc=True))&set(pd.to_datetime(g.timestamp,utc=True)):
                raise ValueError('Context recovery would overwrite an archived price')
            g=pd.concat([prior,g],ignore_index=True)
        groups[name]=g.sort_values('timestamp')
    return groups


def run():
    if not (RECOVERY/'manifest.json').exists():recover()
    manifest=pilot.read(RECOVERY/'manifest.json')
    for name,sha in manifest['files'].items():
        if digest(RECOVERY/name)!=sha:raise ValueError('Changed supplemental context')
    if not ROOT.exists():
        with patch.object(pilot,'frozen_day',extended_day):pilot.prepare(ROOT)
        atomic_json(ROOT/'context-extension.json',dict(previous=str(pilot.ROOT),recovery=str(RECOVERY),
            manifest_sha256=digest(RECOVERY/'manifest.json'),source_code_sha256=digest(Path(__file__)),
            same_rules=True,same_frequency_thresholds=True,no_PnL_used=True,provider_calls=0,SQL_writes=0))


if __name__=='__main__':
    try:run()
    except Exception as exc:
        RECOVERY.mkdir(parents=True,exist_ok=True)
        atomic_json(RECOVERY/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
