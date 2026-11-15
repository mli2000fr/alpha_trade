"""Resume only the authorized research replay with qualified local Yahoo prices.

No download in this runner, no SQL writes, no canonical source relabelling.
The original scores, fixed model weights and Q051 sizing rules are untouched.
"""
import argparse
from datetime import date
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from backtesting.winner_campaign_replay import atomic_json
from modelFactory.oracle_path.train import digest
from scripts.research.us_q051_same_batch_retrospective_20261114 import run,MODE


def qualify(payload, canonical):
    result=(payload['response']['chart']['result'] or [])[0]
    meta=result['meta']
    if (payload['http_status']!=200 or payload['symbol']!='TKOMY' or meta.get('symbol')!='TKOMY'
            or meta.get('currency')!='USD' or meta.get('instrumentType')!='EQUITY'
            or meta.get('exchangeTimezoneName')!='America/New_York' or result.get('events',{}).get('splits')):
        raise ValueError('Yahoo : identité/devise/base de prix non qualifiées')
    frame=pd.DataFrame(result['indicators']['quote'][0])
    frame['date']=pd.to_datetime(result['timestamp'],unit='s',utc=True).tz_convert('America/New_York').tz_localize(None).normalize()
    frame['symbol']='TKOMY'
    prices=['open','high','low','close']
    if (frame.date.duplicated().any() or not np.isfinite(frame[prices+['volume']].to_numpy(float)).all()
            or not frame[prices].gt(0).all().all() or not frame.volume.ge(0).all()
            or not frame.high.ge(frame[['open','close']].max(axis=1)).all()
            or not frame.low.le(frame[['open','close']].min(axis=1)).all()):
        raise ValueError('Yahoo : clés ou OHLCV invalides')
    anchors=canonical.loc[canonical.symbol.eq('TKOMY'),['date',*prices]].merge(frame[['date',*prices]],on='date',suffixes=('_canonical','_yahoo'))
    if len(anchors)<3:raise ValueError('Trois ancrages canoniques minimum requis')
    error=max(float(((anchors[k+'_yahoo']/anchors[k+'_canonical'])-1).abs().max()) for k in prices)
    if not np.isfinite(error) or error>.0005:raise ValueError('Yahoo : prix incompatibles avec les ancrages canoniques')
    frame['data_source']='yahoo_daily_research'
    frame['data_adjustment']='split'
    frame['is_filled']=0
    existing=set(zip(canonical.symbol,pd.to_datetime(canonical.date)))
    missing=frame[[key not in existing for key in zip(frame.symbol,frame.date)]].copy()
    from common.market_calendar import get_market_calendar
    expected={s.session_date for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(
        date(2026,10,19),date(2026,11,13)) if s.is_open}
    if set(missing.date.dt.date)!=expected:raise ValueError('Yahoo : séances de réparation incomplètes/inattendues')
    return missing,dict(anchor_sessions=len(anchors),maximum_relative_OHLC_difference=error,
        repaired_sessions=len(missing),source='yahoo_daily_research',currency='USD',splits_in_window=0,
        original_rows_overwritten=0,retrieved_at=payload['received_at'],historical_PIT_availability_claimed=False)


def resume(root):
    root=Path(root).resolve();plan=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    if plan.get('lookahead_authorized') is not True or plan.get('evaluation_mode')!=MODE:
        raise ValueError('Contrat rétrospectif autorisé requis')
    raw=root/'price_recovery/yahoo-TKOMY.json'
    canonical=pd.read_parquet(root/'daily.parquet')
    canonical=canonical[canonical.data_source.isin(['eodhd_eod','alpaca_sip'])]
    added,receipt=qualify(json.loads(raw.read_text(encoding='utf-8')),canonical)
    receipt.update(raw_payload_sha256=digest(raw),script_sha256=digest(Path(__file__)),
        provider_requests=2,alpaca_result='DailyHistoryBlocked',yahoo_http_status=200,
        scope='Missing TKOMY daily marks only; no signal/model/size changes')
    atomic_json(root/'price_recovery/qualification.json',receipt)
    added.to_parquet(root/'price_recovery/qualified-daily.parquet',index=False)
    for name in ['progress.json','isolation.json']:
        archive=root/('first-attempt-'+name)
        if (root/name).exists() and not archive.exists():shutil.copyfile(root/name,archive)
    from backtesting import winner_data
    from ihm.services import backtesting_import
    original_daily=winner_data.daily_bars
    original_import=backtesting_import.import_continuous_winner
    def daily(conn,symbols,start,end):
        frame=original_daily(conn,symbols,start,end)
        part=added[added.symbol.isin(symbols)&added.date.between(pd.Timestamp(start),pd.Timestamp(end))]
        keys=set(zip(frame.symbol,frame.date))
        part=part[[key not in keys for key in zip(part.symbol,part.date)]]
        result=pd.concat([frame,part],ignore_index=True).sort_values(['date','symbol'])
        if result.duplicated(['date','symbol']).any():raise ValueError('Réparation : clés daily dupliquées')
        return result
    def publish(source,**kwargs):
        p=Path(source)/'protocol.json';r=Path(source)/'result/report.json'
        updated=json.loads(p.read_text(encoding='utf-8'));report=json.loads(r.read_text(encoding='utf-8'))
        updated['price_recovery']=receipt;updated['reference']['price_recovery']=receipt
        updated['replay_command']=['python','-m','scripts.research.us_q051_retrospective_daily_repair_20261115','--root',str(root)]
        report['price_recovery']=receipt;report['provider_calls']=2
        report['limitations'].append('TKOMY : vingt séances OHLC Yahoo locales, USD et sept ancrages canoniques concordants ; aucun prix SIP inventé, aucune écriture SQL.')
        atomic_json(p,updated);atomic_json(r,report)
        return original_import(source,**kwargs)
    args=SimpleNamespace(allow_in_sample_lookahead=True,output_dir=str(root),batch_id=plan['batch_id'],
        artifacts_dir='artifacts/models',start=date.fromisoformat(plan['start']),end=date.fromisoformat(plan['end']),
        history_id='20261114_q051_c59bed_retrospective')
    with patch.object(winner_data,'daily_bars',daily),patch.object(backtesting_import,'import_continuous_winner',publish):
        run(args)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True)
    import logging
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    resume(parser.parse_args().root)
