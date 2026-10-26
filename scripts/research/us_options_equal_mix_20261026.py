"""Frozen US options volume/OI mix; SQL read-only then offline, no fitting."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import hashlib
import json
import re

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import bindparam, text

from scripts.research.fr_p0_p1_directional_audit_20261026 import protected_excursion, compare_paths

DEFAULT = Path('artifacts/research/us_options_equal_mix/20261026-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
DOC = Path('doc/ml/options_volume_oi_combinaison_protocole_20261026.md')
TEST = Path('tests/test_us_options_equal_mix_20261026.py')
FEATURES = ['volume_call_minus_put_log', 'oi_call_minus_put_log']
SCORES = ['volume_score', 'oi_score', 'combined_score']
KEY = ['entry_day', 'symbol']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                   allow_nan=False, default=str), encoding='utf-8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def local_day(series):
    return pd.to_datetime(series, utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()


def calendar(cutoff):
    from common.market_calendar import get_market_calendar
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    rows = [s for s in cal.sessions(date(2026, 9, 1), date(2026, 12, 15)) if s.is_open]
    return pd.DataFrame([dict(day=pd.Timestamp(s.session_date),
        opened=pd.Timestamp(s.open_at_utc), closed=pd.Timestamp(s.close_at_utc)) for s in rows])


def snapshot(output):
    output.mkdir(parents=True, exist_ok=False)
    cutoff = pd.Timestamp.now(tz='UTC')
    cal = calendar(cutoff)
    last = cal.loc[cal.closed.lt(cutoff), 'day'].max()
    symbols = sorted(set(s.upper() for s in re.split(r'[,;\s]+', UNIVERSE.read_text(encoding='utf-8-sig')) if s))
    sources = {str(p): digest(p) for p in [Path(__file__), TEST, DOC, UNIVERSE,
        Path('scripts/research/fr_p0_p1_directional_audit_20261026.py'),
        Path('scripts/research/us_prospective_directional_check.py'),
        Path('common/market_calendar.py')]}
    write(output/'protocol.json', dict(cutoff=cutoff, last_closed_session=last, sources=sources,
        universe_count=len(symbols), symbols=symbols, weights=dict(volume=.5,open_interest=.5),
        primary_horizon=20, secondary_horizons=[5,10], stop_loss_pct=.10,
        price_source='alpaca_sip', adjustment='split', training=False, weight_search=False,
        SQL='alpha_trade READ ONLY REPEATABLE READ rollback', provider_calls=0, LLM_calls=0,
        production_changes=False, target='Dominant protected excursion before side-specific SL10',
        old_window_end='2026-10-09', old_results_seen=True, independent_holdout=False))
    cal.to_parquet(output/'calendar.parquet', index=False)
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    if engine.url.database != 'alpha_trade':
        raise ValueError('US alpha_trade only')
    params = dict(symbols=symbols, start='2026-09-10', end=str((last+pd.Timedelta(days=1)).date()),
                  cutoff=cutoff.tz_localize(None).to_pydatetime())
    queries = {
        'snapshots': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,
            strike,option_type,observed_at,available_at,provider_timestamp,open_interest,payload_hash,
            provider,feed FROM stock_option_snapshots WHERE provider='alpaca' AND feed='indicative'
            AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
            AND available_at<=:cutoff AND observed_at<=:cutoff''',
        'volumes': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,
            option_type,bar_timestamp,observed_at,available_at,volume,payload_hash,provider,feed,
            provenance_status,timeframe FROM stock_option_bars_delayed WHERE provider='alpaca'
            AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
            AND bar_timestamp>=:start AND bar_timestamp<:end AND timeframe='1Day'
            AND available_at<=:cutoff AND observed_at<=:cutoff''',
        'prices': '''SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,
            data_adjustment,instrument_id,ingested_at,last_updated FROM stock_bars_daily
            WHERE symbol IN :symbols AND date>=:start AND date<:end
            AND data_source='alpaca_sip' AND data_adjustment='split' '''}
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
            conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
                raise ValueError('Wrong database')
            for name, sql in queries.items():
                print('Reading '+name, flush=True)
                stmt = text(sql).bindparams(bindparam('symbols', expanding=True))
                frame = pd.DataFrame([dict(r) for r in conn.execute(stmt,params).mappings()])
                frame.to_parquet(output/(name+'.parquet'), index=False)
                print(name+' rows='+str(len(frame)), flush=True)
            conn.rollback()
    finally:
        engine.dispose()
    files = ['protocol.json','calendar.parquet','snapshots.parquet','volumes.parquet','prices.parquet']
    write(output/'snapshot-seal.json', dict(files={n:digest(output/n) for n in files}))


def standard_rows(frame, received_day=False):
    frame = frame.copy()
    for col in ['observed_at','available_at']:
        frame[col] = pd.to_datetime(frame[col],utc=True)
    frame['received_at'] = frame[['observed_at','available_at']].max(axis=1)
    frame['day'] = local_day(frame.received_at)
    if received_day:
        bar_day = local_day(frame.bar_timestamp)
        frame = frame[frame.day.eq(bar_day)].copy()
    frame['expiration_date'] = pd.to_datetime(frame.expiration_date)
    frame['option_type'] = frame.option_type.str.upper().replace({'C':'CALL','P':'PUT'})
    root = frame.contract_symbol.str.replace(r'\d{6}[CP]\d{8}$','',regex=True)
    frame = frame[root.eq(frame.symbol.str.replace('.','',regex=False))].copy()
    frame['dte'] = (frame.expiration_date-frame.day).dt.days
    return frame[frame.dte.between(15,25)].copy()


def latest_unambiguous(frame, keys, value_columns):
    """Latest received version; conflicting simultaneous versions are unknown."""
    latest = frame.groupby(keys).received_at.transform('max')
    frame = frame[frame.received_at.eq(latest)].copy()
    conflict = frame.groupby(keys)[value_columns].transform(lambda s:s.nunique(dropna=False)).gt(1).any(axis=1)
    return frame[~conflict].drop_duplicates(keys).copy(), int(conflict.sum())


def build_features(snapshots, volumes, prices, cal):
    audit = {}
    prices = prices.copy()
    if prices.duplicated(['symbol','date']).any():
        raise ValueError('Duplicate source-specific daily bars')
    prices['day'] = pd.to_datetime(prices.date)
    prices['spot'] = pd.to_numeric(prices.close,errors='coerce')
    spots = prices[prices.spot.gt(0)&prices.is_filled.eq(0)][['day','symbol','spot']]
    oi = standard_rows(snapshots)
    oi['strike'] = pd.to_numeric(oi.strike,errors='coerce')
    oi['open_interest'] = pd.to_numeric(oi.open_interest,errors='coerce')
    oi,audit['oi_conflicting_rows'] = latest_unambiguous(oi,['day','symbol','contract_symbol'],
        ['open_interest','strike','expiration_date','option_type','payload_hash'])
    oi = oi.merge(spots,on=['day','symbol'],validate='many_to_one')
    oi['distance'] = (oi.strike/oi.spot-1).abs()
    oi = oi[oi.distance.le(.05)&oi.open_interest.ge(0)&np.isfinite(oi.open_interest)].copy()
    keys = ['day','symbol','expiration_date','strike']
    oi = oi[oi.option_type.eq('CALL')].merge(oi[oi.option_type.eq('PUT')],on=keys,
        suffixes=('_call','_put'),validate='one_to_one')
    oi['tenor_distance'] = (oi.dte_call-20).abs()
    oi = oi.sort_values(['day','symbol','tenor_distance','distance_call','expiration_date','strike'],
        kind='stable').drop_duplicates(['day','symbol'])
    oi[FEATURES[1]] = np.log1p(oi.open_interest_call)-np.log1p(oi.open_interest_put)
    oi['oi_available_at'] = oi[['received_at_call','received_at_put']].max(axis=1)
    oi = oi.rename(columns={'expiration_date':'oi_expiry'})
    flow = standard_rows(volumes,received_day=True)
    flow['volume'] = pd.to_numeric(flow.volume,errors='coerce')
    flow,audit['volume_conflicting_rows'] = latest_unambiguous(flow,
        ['symbol','contract_symbol','bar_timestamp'],['volume','payload_hash','option_type','expiration_date'])
    flow['bad_volume'] = ~np.isfinite(flow.volume)|flow.volume.lt(0)
    group = ['day','symbol','expiration_date','option_type']
    flow = flow.groupby(group,as_index=False).agg(volume=('volume','sum'),bad=('bad_volume','any'),
        received_at=('received_at','max'),dte=('dte','first'))
    flow = flow[~flow.bad].copy()
    flow = flow[flow.option_type.eq('CALL')].merge(flow[flow.option_type.eq('PUT')],
        on=['day','symbol','expiration_date'],suffixes=('_call','_put'),validate='one_to_one')
    flow['tenor_distance'] = (flow.dte_call-20).abs()
    flow = flow.sort_values(['day','symbol','tenor_distance','expiration_date'],kind='stable').drop_duplicates(['day','symbol'])
    flow[FEATURES[0]] = np.log1p(flow.volume_call)-np.log1p(flow.volume_put)
    flow['volume_available_at'] = flow[['received_at_call','received_at_put']].max(axis=1)
    flow = flow.rename(columns={'expiration_date':'volume_expiry'})
    audit.update(oi_candidates=len(oi),volume_candidates=len(flow))
    common = flow[['day','symbol',FEATURES[0],'volume_available_at','volume_expiry']].merge(
        oi[['day','symbol',FEATURES[1],'oi_available_at','oi_expiry']],on=['day','symbol'],validate='one_to_one')
    common['entry_day'] = common.day.map(lambda d: cal.loc[cal.day.gt(d),'day'].iloc[0])
    bounds = cal.set_index('day').opened
    common['entry_at'] = common.entry_day.map(bounds)
    common['decision_at'] = common.entry_at-pd.Timedelta(minutes=5)
    common['feature_available_at'] = common[['volume_available_at','oi_available_at']].max(axis=1)
    audit['after_decision_rejected'] = int((~common.feature_available_at.lt(common.decision_at)).sum())
    common = common[common.feature_available_at.lt(common.decision_at)].copy()
    common['entry_day'] = common.entry_day.dt.strftime('%Y-%m-%d')
    audit['common_candidates'] = len(common)
    audit['same_expiry_candidates'] = int(common.volume_expiry.eq(common.oi_expiry).sum())
    return common,audit


def score_candidates(features):
    columns = KEY+FEATURES+['entry_at','decision_at','feature_available_at']
    frame = features[columns].copy()
    if frame.duplicated(KEY).any():
        raise ValueError('Duplicate as-of candidate')
    if not pd.to_datetime(frame.feature_available_at,utc=True).lt(pd.to_datetime(frame.decision_at,utc=True)).all():
        raise ValueError('Future feature')
    frame = frame[np.isfinite(frame[FEATURES].to_numpy(float)).all(axis=1)].copy()
    for feature,score in zip(FEATURES,SCORES):
        frame[score] = frame.groupby('entry_day')[feature].transform(lambda s:(s.rank(method='average')-.5)/len(s))
    frame['combined_score'] = .5*frame.volume_score+.5*frame.oi_score
    return frame


def make_labels(scored, prices, cal, cutoff):
    prices = prices.copy()
    if prices.duplicated(['symbol','date']).any():
        raise ValueError('Duplicate outcome bar')
    prices['date'] = pd.to_datetime(prices.date)
    for col in ['open','high','low','close','volume']:
        prices[col] = pd.to_numeric(prices[col],errors='coerce')
    prices['valid'] = (np.isfinite(prices[['open','high','low','close','volume']].to_numpy(float)).all(axis=1)
        & prices[['open','high','low','close','volume']].gt(0).all(axis=1)&prices.is_filled.eq(0)
        & prices.high.ge(prices[['open','close']].max(axis=1))&prices.low.le(prices[['open','close']].min(axis=1))
        & prices.instrument_id.notna()&prices.data_source.eq('alpaca_sip')&prices.data_adjustment.eq('split'))
    groups = {s:g.set_index('date') for s,g in prices.groupby('symbol')}
    dates = list(cal.day); rows=[]
    for r in scored.to_dict('records'):
        start = dates.index(pd.Timestamp(r['entry_day']))
        for h in [5,10,20]:
            record = {**r,'horizon':h}
            window = cal.iloc[start:start+h]
            if len(window)<h or not window.closed.lt(cutoff).all():
                rows.append({**record,'status':'NOT_MATURE'});continue
            path = groups.get(r['symbol'])
            if path is None:
                rows.append({**record,'status':'MISSING_PRICES'});continue
            path = path.reindex(window.day)
            if not path.valid.eq(True).all() or path.instrument_id.nunique()!=1:
                rows.append({**record,'status':'INVALID_OR_INCOMPLETE_PRICE_IDENTITY'});continue
            bars=[dict(date=str(d.date()),open=p.open,high=p.high,low=p.low,close=p.close) for d,p in path.iterrows()]
            long,short=protected_excursion(bars,'LONG'),protected_excursion(bars,'SHORT')
            direction,first=compare_paths(long,short)
            record.update(status='LABEL' if direction!='AMBIGUOUS_OR_TIE' else 'AMBIGUOUS_PATH',
                          dominant_direction=direction,first_peak=first)
            record.update({'long_'+k:v for k,v in long.items()})
            record.update({'short_'+k:v for k,v in short.items()})
            rows.append(record)
    return pd.DataFrame(rows)


def metrics(frame):
    result=dict(n=len(frame),symbols=int(frame.symbol.nunique()),dates=int(frame.entry_day.nunique()),
                scores={},daily=[])
    valid=frame[frame.status.eq('LABEL')]
    result.update(valid_n=len(valid),long_n=int(valid.dominant_direction.eq('LONG').sum()) if len(valid) else 0,
                  status_counts=frame.status.value_counts().to_dict())
    for day,g in valid.groupby('entry_day'):
        if g.dominant_direction.nunique()!=2:continue
        y=g.dominant_direction.eq('LONG')
        vals={s:float(roc_auc_score(y,g[s])) for s in SCORES}
        result['daily'].append(dict(day=day,n=len(g),**vals,
            delta_vs_volume=vals['combined_score']-vals['volume_score'],
            delta_vs_oi=vals['combined_score']-vals['oi_score']))
    for s in SCORES:
        daily=[r[s] for r in result['daily']]
        result['scores'][s]=dict(mean_daily_auc=float(np.mean(daily)) if daily else None,
            informative_dates=len(daily),pooled_auc=float(roc_auc_score(valid.dominant_direction.eq('LONG'),valid[s]))
            if len(valid) and valid.dominant_direction.nunique()==2 else None)
    result['rank_correlation'] = float(frame.volume_score.corr(frame.oi_score)) if len(frame)>1 and frame.volume_score.nunique()>1 and frame.oi_score.nunique()>1 else None
    return result


def spaced_dates(days,h,cal):
    positions={str(d.date()):i for i,d in enumerate(cal.day)}; selected=[];last=None
    for d in sorted(set(days)):
        if last is None or positions[d]-last>=h:selected.append(d);last=positions[d]
    return selected


def analyze(output):
    if (output/'report.json').exists():raise FileExistsError('Immutable completed study')
    seal=read(output/'snapshot-seal.json')
    for n,sha in seal['files'].items():
        if Path(n).name!=n or digest(output/n)!=sha:raise ValueError('Snapshot hash mismatch')
    protocol=read(output/'protocol.json')
    for p,sha in protocol['sources'].items():
        if digest(p)!=sha:raise ValueError('Frozen source changed: '+p)
    cal=pd.read_parquet(output/'calendar.parquet')
    inputs={n:pd.read_parquet(output/(n+'.parquet')) for n in ['snapshots','volumes','prices']}
    features,audit=build_features(inputs['snapshots'],inputs['volumes'],inputs['prices'],cal)
    features.to_parquet(output/'features.parquet',index=False)
    scored=score_candidates(features)
    scored.to_parquet(output/'asof-scores.parquet',index=False)
    labels=make_labels(scored,inputs['prices'],cal,pd.Timestamp(protocol['cutoff']))
    labels.to_parquet(output/'protected-paths.parquet',index=False)
    report=dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',feature_audit=audit,source_rows={k:len(v) for k,v in inputs.items()},
        scores=len(scored),symbols=int(scored.symbol.nunique()),horizons={},
        limitations=['Not an economic backtest or probability calibration','Current tradable universe, not historical survivorship free',
        'Indicative OI; OPRA volume provenance not certified; not signed order flow',
        'Current split prices, no independent corporate-action/vintage qualification',
        'No sector/size neutralization; overlapping paths and repeated securities',
        'Not conditional on Oracle TOP10; old/new windows are not independent holdouts'])
    for h in [5,10,20]:
        f=labels[labels.horizon.eq(h)]
        selected=spaced_dates(scored.entry_day,h,cal)
        first=scored.sort_values(KEY).drop_duplicates('symbol')[KEY]
        days=sorted(scored.entry_day.unique());middle=len(days)//2
        daily=metrics(f)['daily']
        report['horizons'][str(h)]=dict(all=metrics(f),nonoverlap_entry_dates=selected,
            nonoverlap=metrics(f[f.entry_day.isin(selected)]),
            first_per_symbol=metrics(f.merge(first,on=KEY,validate='one_to_one')),
            original_window=metrics(f[f.entry_day.le('2026-10-09')]),
            extension_window=metrics(f[f.entry_day.gt('2026-10-09')]),
            first_half=metrics(f[f.entry_day.isin(days[:middle])]),second_half=metrics(f[f.entry_day.isin(days[middle:])]),
            leave_one_date_out=[dict(excluded=r['day'],delta_vs_volume=float(np.mean([
                x['delta_vs_volume'] for x in daily if x['day']!=r['day']]))) for r in daily] if len(daily)>1 else [])
    write(output/'report.json',report)
    files=[p for p in output.iterdir() if p.is_file() and p.name!='seal.json']
    write(output/'seal.json',dict(files={p.name:digest(p) for p in files},sources=protocol['sources']))
    print(json.dumps(dict(status=report['status'],scores=len(scored),horizons={h:v['all']['scores'] for h,v in report['horizons'].items()})),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['snapshot','analyze'],required=True)
    parser.add_argument('--output',type=Path,default=DEFAULT)
    args=parser.parse_args()
    (snapshot if args.phase=='snapshot' else analyze)(args.output)
