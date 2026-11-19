"""Current batch SHORT-only 2025/2026, local research outputs, no training/SQL/HTTP."""
import argparse
from dataclasses import replace
from datetime import date, datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research.us_q051_b_short_20261118 import rank_short, read
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

BATCH = 'model-factory-20261118172104-2f6a31'
MODEL = Path('artifacts/models')/BATCH/'oracle_path'
ROOT = Path('artifacts/research/us_b_short_current_batch/20261118-v1')
TAPE = Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1/inputs')
FIRST, LAST = pd.Timestamp('2024-12-31'), pd.Timestamp('2026-09-30')


def update(**values):
    atomic_json(ROOT/'progress.json', dict(updated_at_utc=datetime.now(timezone.utc).isoformat(), **values))


def prepare():
    from modelFactory.oracle_path.predict import load_contract, select_fold
    from modelFactory.oracle_path.train import restore_ranks, model_probabilities
    if (ROOT/'protocol.json').exists():
        return read(ROOT/'protocol.json')
    ROOT.mkdir(parents=True, exist_ok=True)
    update(status='CHECKING_CURRENT_BATCH')
    _, protocol, profile, folds = load_contract('artifacts/models', BATCH)
    manifest = read(MODEL/'directional/manifest.json')
    if len(protocol['universe']) != 1790 or manifest['contract']['feature_mode'] != 'compact_volatility':
        raise ValueError('Expected current B29/H10/1790 batch')
    sources = {};parts = [];jobs = []
    for folder in sorted((MODEL/'chunks').iterdir()):
        marker = read(folder/'done.json')
        for name in ['features.parquet', 'bars.parquet']:
            checksum = digest(folder/name)
            if checksum != marker['files'][name]:raise ValueError('Changed current-batch chunk')
            sources[str(folder/name)] = checksum
        frame = pd.read_parquet(folder/'features.parquet', filters=[('date','>=',FIRST),('date','<=',LAST)])
        parts.append(frame)
        jobs.append(folder.name)
    frame = restore_ranks(pd.concat(parts, ignore_index=True), protocol['generator_options'])
    if frame.duplicated(['date','symbol']).any():raise ValueError('Duplicate current Oracle keys')
    columns = profile['feature_columns']
    frame[columns] = frame[columns].replace([np.inf,-np.inf],np.nan).astype(np.float32)
    if frame[columns].isna().all(axis=1).any():raise ValueError('Empty Oracle feature row')
    scores = frame[['date','symbol']].copy()
    scores['fold_start'] = scores.date.map(lambda day: select_fold(day, folds))
    for name, group in scores.groupby('fold_start'):
        update(status='SCORING_CURRENT_ORACLE', fold=name)
        fold = folds[name]
        if fold['backend'] == 'catboost':
            from catboost import CatBoostClassifier
            model = CatBoostClassifier().load_model(fold['model_file']);names = model.feature_names_
        else:
            from lightgbm import Booster
            model = Booster(model_file=fold['model_file']);names = model.feature_name()
        if names != columns:raise ValueError('Oracle input order changed')
        scores.loc[group.index,'proba_extreme'] = model_probabilities(model,fold['backend'],frame.loc[group.index,columns])
        metrics = fold['metrics']
        available = max(pd.Timestamp(metrics[k]) for k in ['train_available_max','val_available_max'])
        if not group.date.gt(available).all():raise ValueError('Future Oracle fold')
        scores.loc[group.index,'model_available_date'] = str(available.date())
        scores.loc[group.index,'model_sha256'] = fold['model_sha256']
    scores.to_parquet(ROOT/'oracle.parquet', index=False)
    pool = scores.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).groupby('date').head(179)
    pool.to_parquet(ROOT/'pool.parquet',index=False)
    coverage = scores.groupby('date').size().rename('observed').to_frame()
    coverage['model_universe'] = len(protocol['universe']);coverage['coverage_pct'] = coverage.observed/1790*100
    coverage.to_csv(ROOT/'oracle-coverage.csv')
    sources.update({str(MODEL/n):digest(MODEL/n) for n in ['protocol.json','feature_profile.json','report.json','directional/manifest.json','directional/benchmark.parquet']})
    plan = dict(batch_id=BATCH, initial_equity=4000., start='2025-01-01', end='2026-10-01',
        selection='Current causal Oracle TOP179 -> native SHORT-year head TOP10 -> p>.50 / calibration AUC>=.50, no refill',
        training=False, anti_sl=False, jobs=jobs, sources=sources, folds=folds,
        source_sha256=digest(Path(__file__)), oracle_sha256=digest(ROOT/'oracle.parquet'), pool_sha256=digest(ROOT/'pool.parquet'),
        replay='Same isolated daily SHORT SL5/open11 full-position coordinator as preceding test; borrow assumed3%/year; fee8bps/leg',
        live_changes=False, SQL_writes=0, broker_orders=0, provider_calls=0,
        historical_limitations='Revised data, contemporary universe, no independent holdout; locates/dividends not exhaustively certified',
        coverage_min_pct=float(coverage.coverage_pct.min()),
        missing_previous_year_head='No2024 own-stock heads; Dec31 signal cannot create Jan2 entry',
        created_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    return plan


def worker(key):
    import joblib
    from modelFactory.oracle_path.directional import panels
    from modelFactory.oracle_path.directional_metrics import predict
    from modelFactory.oracle.build_labels import nyse_sessions
    from common.config_loader import replay_market_registry
    from scripts.research.us_q051_feature_groups_20261116 import shared, no_http
    plan = read(ROOT/'protocol.json');folder = MODEL/'chunks'/key
    if digest(Path(__file__)) != plan['source_sha256']:raise ValueError('Research source changed')
    out = ROOT/'jobs'/key;out.mkdir(parents=True,exist_ok=True)
    if (out/'done.json').exists():return
    if digest(folder/'bars.parquet') != plan['sources'][str(folder/'bars.parquet')]:raise ValueError('Changed source bars')
    manifest = read(MODEL/'directional/manifest.json')
    records = {(r['symbol'],r['year']):r for r in manifest['models'] if r['side']=='short'}
    pool = pd.read_parquet(ROOT/'pool.parquet');bars = pd.read_parquet(folder/'bars.parquet')
    benchmark = pd.read_parquet(MODEL/'directional/benchmark.parquet')
    protocol = read(MODEL/'protocol.json');pieces = [];used = [];missing = []
    with replay_market_registry(shared.restore_registry(shared.ROOT)), patch.object(requests.Session,'request',no_http):
        calendar = nyse_sessions(date.fromisoformat(protocol['training_config']['data']['training_start_date']),LAST.date())
        for symbol, group in bars.groupby('symbol'):
            wanted = pool[pool.symbol.eq(symbol)][['date','symbol']]
            if wanted.empty:continue
            atomic_json(out/'progress.json',dict(status='SCORING_SHORT',symbol=symbol))
            f = panels(group[group.date.le(LAST)],benchmark,calendar,feature_mode='compact_volatility')
            wanted = wanted.merge(f,on=['date','symbol'],validate='one_to_one')
            for year, sample in wanted.groupby(wanted.date.dt.year):
                record = records.get((symbol,year))
                if record is None:
                    missing.append(dict(symbol=symbol,year=int(year),reason='NO_CURRENT_BATCH_HEAD'));continue
                file = MODEL/record['file']
                if digest(file) != record['sha256'] or not sample.date.gt(pd.Timestamp(record['available'])).all():
                    raise ValueError('Changed/future own-stock SHORT head')
                weights = joblib.load(file)
                if weights.get('features') != manifest['features']:raise ValueError('Changed native B29 columns')
                p = sample[['date','symbol']].copy();p['short_probability'] = predict(weights,sample)
                p['short_auc'] = record['metrics']['calibration']['auc'];p['short_available'] = pd.Timestamp(record['available'])
                p['short_model_sha256'] = record['sha256'];pieces.append(p);used.append(record)
    empty = pd.DataFrame(columns=['date','symbol','short_probability','short_auc','short_available','short_model_sha256'])
    (pd.concat(pieces,ignore_index=True) if pieces else empty).to_parquet(out/'probabilities.parquet',index=False)
    atomic_json(out/'models.json',dict(models=used,missing=missing))
    atomic_json(out/'done.json',dict(status='COMPLETED',outputs={n:digest(out/n) for n in ['probabilities.parquet','models.json']}))


def assemble():
    plan = read(ROOT/'protocol.json');parts = []
    for key in plan['jobs']:
        out = ROOT/'jobs'/key
        for name,checksum in read(out/'done.json')['outputs'].items():
            if digest(out/name) != checksum:raise ValueError('Changed SHORT scores')
        parts.append(pd.read_parquet(out/'probabilities.parquet'))
    probabilities = pd.concat([p for p in parts if not p.empty],ignore_index=True)
    ranked = rank_short(pd.read_parquet(ROOT/'oracle.parquet'),probabilities)
    ranked.to_parquet(ROOT/'rankings.parquet',index=False)
    ranked[ranked.selected].to_parquet(ROOT/'signals.parquet',index=False)


def replay():
    from scripts.research.us_q051_b_short_replay_20261118 import DailyShortReplay,config
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    from scripts.research.us_q051_feature_groups_20261116 import shared,no_http
    pivots = {c:pd.read_parquet(TAPE/(c+'.parquet')) for c in ['open','high','low','close','volume']}
    # Local evidence overlay only: never write canonical prices or model inputs.
    if (ROOT/'volume-recovery.json').exists():
        for item in read(ROOT/'volume-recovery.json')['records']:
            if item['field']!='volume' or item['price_change'] is not False:
                raise ValueError('Only independently corroborated zero-volume recovery is allowed')
            evidence=Path(item['evidence_file'])
            if digest(evidence)!=item['evidence_sha256']:raise ValueError('Changed recovery evidence')
            f=pd.read_parquet(evidence)
            f=f[f.provider.eq('alpaca')&f.data_source.eq('alpaca_sip')&f.session_tag.eq('regular')
                &f.data_adjustment.eq('raw')&f.is_filled.eq(0)].sort_values('bar_timestamp')
            if (len(f)!=78 or not f.symbol.eq(item['symbol']).all()
                or not pd.to_datetime(f.trade_date).eq(pd.Timestamp(item['date'])).all()
                or not f.bar_timestamp.diff().dropna().eq(pd.Timedelta(minutes=5)).all()
                or f.volume.sum()!=item['new_value'] or item['new_value']<=0):
                raise ValueError('Incomplete recovery SIP evidence')
            prices=dict(open=float(f.open.iloc[0]),high=float(f.high.max()),low=float(f.low.min()),close=float(f.close.iloc[-1]))
            day=pd.Timestamp(item['date']);symbol=item['symbol']
            for field,value in prices.items():
                original=float(pivots[field].at[day,symbol])
                if abs(value/original-1)>.0005 or original!=item['ohlc_reference'][field]:
                    raise ValueError('SIP evidence does not corroborate held-day OHLC')
            if pivots['volume'].at[day,symbol]!=item['old_value'] or item['old_value']!=0:
                raise ValueError('Unexpected original held-day volume')
            pivots['volume'].at[day,symbol]=item['new_value']
    if (ROOT/'price-recovery.json').exists():
        for item in read(ROOT/'price-recovery.json')['records']:
            evidence=Path(item['evidence_file'])
            if digest(evidence)!=item['evidence_sha256']:raise ValueError('Changed SIP price recovery evidence')
            f=pd.read_parquet(evidence)
            f=f[f.provider.eq('alpaca')&f.data_source.eq('alpaca_sip')&f.session_tag.eq('regular')
                &f.data_adjustment.eq('raw')&f.is_filled.eq(0)&f.symbol.eq(item['symbol'])
                &pd.to_datetime(f.trade_date).eq(item['date'])].sort_values('bar_timestamp')
            day=pd.Timestamp(item['date']);symbol=item['symbol']
            if len(f)!=78 or not f.bar_timestamp.diff().dropna().eq(pd.Timedelta(minutes=5)).all():
                raise ValueError('Incomplete SIP price recovery')
            observed=dict(open=float(f.open.iloc[0]),high=float(f.high.max()),low=float(f.low.min()),close=float(f.close.iloc[-1]),volume=int(f.volume.sum()))
            if observed!=item['new_values'] or pivots['volume'].at[day,symbol]!=0:
                raise ValueError('Unexpected price recovery values')
            for field,value in observed.items():
                if pivots[field].at[day,symbol]!=item['old_values'][field]:raise ValueError('Unexpected old price')
                pivots[field].at[day,symbol]=value
    sectors = pd.read_parquet(TAPE/'sectors.parquet').set_index('symbol').sector.to_dict()
    actions = pd.read_parquet(TAPE/'actions.parquet');signals = pd.read_parquet(ROOT/'signals.parquet')
    cfg = replace(config(),start_date=date(2025,1,1),end_date=date(2026,10,1))
    with replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
        sessions = [s for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(date(2024,12,20),cfg.end_date) if s.is_open]
        book = DailyShortReplay(pivots,sectors,actions,signals,sessions,cfg,borrow=.03).run(
            lambda done,total,day:update(status='REPLAYING',completed=done,total=total,day=day))
    curve = pd.DataFrame(book.curve);trades = pd.DataFrame(book.book.trades);entries = pd.DataFrame(book.entries)
    curve.to_csv(ROOT/'equity-daily.csv',index=False);trades.to_csv(ROOT/'trades.csv',index=False)
    entries.to_csv(ROOT/'entries.csv',index=False);pd.DataFrame(book.refusals).to_csv(ROOT/'refusals.csv',index=False)
    pd.DataFrame(book.book.events).to_parquet(ROOT/'events.parquet',index=False)
    from scripts.research.us_q051_b_short_report_20261118 import curve_metrics
    result = dict(batch_id=BATCH,**curve_metrics(curve.equity),closed_trades=len(trades),
        win_pct=float(100*trades.pnl.gt(0).mean()),winning_trades=int(trades.pnl.gt(0).sum()),losing_trades=int(trades.pnl.lt(0).sum()),
        average_win=float(trades.loc[trades.pnl.gt(0),'pnl'].mean()),average_loss=float(trades.loc[trades.pnl.lt(0),'pnl'].mean()),
        average_win_return_pct=float(100*trades.loc[trades.pnl.gt(0),'return_pct'].mean()),
        average_loss_return_pct=float(100*trades.loc[trades.pnl.lt(0),'return_pct'].mean()),
        average_gross_capital=float(curve.gross.mean()),average_gross_equity_pct=float(100*(curve.gross/curve.equity).mean()),
        fees=book.book.fees,borrow_cost=book.book.borrow_fees,open_positions=len(book.book.positions()),
        signal_count=len(signals),independent_holdout=False,borrow_locates_not_certified=True,SQL_writes=0,broker_orders=0,provider_calls=0)
    atomic_json(ROOT/'report.json',result);update(status='REPLAY_COMPLETE_AUDIT_PENDING',result=result)


def run():
    plan = prepare();active = [];waiting = [k for k in plan['jobs'] if not (ROOT/'jobs'/k/'done.json').exists()]
    try:
        while waiting or active:
            while waiting and len(active)<6:
                key=waiting.pop(0);folder=ROOT/'logs';folder.mkdir(exist_ok=True)
                out=(folder/(key+'.out.log')).open('ab');err=(folder/(key+'.err.log')).open('ab')
                p=subprocess.Popen([sys.executable,'-X','utf8','-u','-m',__spec__.name,'--phase','worker','--key',key],
                    stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                active.append((key,p,out,err))
            for item in active[:]:
                key,p,out,err=item
                if p.poll() is None:continue
                out.close();err.close();active.remove(item)
                if p.returncode:raise RuntimeError('Current-batch SHORT worker failed: '+key)
            update(status='SCORING_NATIVE_SHORT_HEADS',completed=len(plan['jobs'])-len(waiting)-len(active),total=len(plan['jobs']),active=[x[0] for x in active])
            if active:time.sleep(1)
        assemble();replay()
    except BaseException as exc:
        update(status='FAILED',error=repr(exc));raise
    finally:
        for key,p,out,err in active:
            if p.poll() is None:p.terminate();p.wait()
            out.close();err.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['all','worker','assemble','replay'],default='all');parser.add_argument('--key')
    args=parser.parse_args()
    if args.phase=='worker':worker(args.key)
    elif args.phase=='assemble':assemble()
    elif args.phase=='replay':replay()
    else:run()
