"""Read-only refreshed audit of the deployed TOP20 volume/OI filter, no fitting."""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sqlalchemy import bindparam, text

from service.options_directional.config import OptionsFilterConfig, load_options_filter_config
from service.options_directional.features import build_features, select_top
from service.options_directional.runner import validate_oracle_lineage
from scripts.research.fr_p0_p1_directional_audit_20261026 import protected_excursion, compare_paths
from scripts.research.us_options_equal_mix_20261026 import digest, read, write

UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
BATCHES = {'2026-09': 'model-factory-20261014113232-bc35a7',
           '2026-10': 'model-factory-20261016180250-3b0515'}
HORIZONS = (5, 10, 15, 20)
KEY = ['signal_day', 'symbol']


def qualified_ranking(raw, symbols, models, cfg, cal):
    f = raw.copy()
    f['signal_day'] = pd.to_datetime(f.signal_day)
    f = f[f.symbol.isin(symbols) & f.signal_day.dt.strftime('%Y-%m').map(BATCHES).eq(f.batch_id)]
    if f.duplicated(KEY).any():
        raise ValueError('Duplicate Oracle score')
    f['proba_extreme'] = pd.to_numeric(f.proba_extreme, errors='raise')
    if not (np.isfinite(f.proba_extreme) & f.proba_extreme.between(0, 1)).all():
        raise ValueError('Bad Oracle score')
    rows, coverage = [], []
    sessions = list(cal.day)
    for (day, batch), g in f.groupby(['signal_day', 'batch_id'], sort=True):
        ratio = len(g) / len(symbols)
        coverage.append(dict(signal_day=day, batch_id=batch, count=len(g), ratio=ratio,
                             qualified=ratio >= cfg.min_oracle_coverage_ratio))
        if ratio < cfg.min_oracle_coverage_ratio:
            continue
        model = models[batch]
        validate_oracle_lineage(g.to_dict('records'), day.date(), model['profile_hash'], model['folds'])
        g = g.sort_values(['proba_extreme', 'symbol'], ascending=[False, True]).head(cfg.oracle_top_n).copy()
        g['oracle_rank'] = np.arange(1, len(g) + 1)
        entry = sessions[sessions.index(day) + 1]
        decision = cal.set_index('day').loc[entry, 'opened'] - pd.Timedelta(minutes=5)
        g['entry_day'], g['decision_at'] = entry, decision
        g['oracle_created_before_decision'] = (
            pd.to_datetime(g.prediction_created_at, utc=True).le(decision)
            & pd.to_datetime(g.lineage_created_at, utc=True).le(decision))
        rows.append(g)
    return pd.concat(rows, ignore_index=True), pd.DataFrame(coverage)


def batch_evidence():
    plans = sorted(Path('artifacts/operations/us_pipeline').glob('*/plan.json'),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    p = plans[0]
    plan = read(p)
    step = next(s for s in plan['steps'] if str(s['number']) == '10')
    run_id = plan['options']['options_filter_run_id']
    report_path = Path('artifacts/options_directional') / run_id / 'report.json'
    report = read(report_path)
    return dict(plan_path=str(p), plan_sha256=digest(p), step10=step,
        report_path=str(report_path), report_sha256=digest(report_path),
        report={k: report[k] for k in ('run_id', 'trade_date', 'status', 'config', 'covered', 'selected', 'cutoff_utc')})


def snapshot(output):
    output.mkdir(parents=True, exist_ok=False)
    cfg = load_options_filter_config()
    if cfg.oracle_top_n != 20:
        raise ValueError('This frozen audit requests the configured TOP20')
    cutoff = pd.Timestamp.now(tz='UTC')
    from common.market_calendar import get_market_calendar
    from modelFactory.oracle_path.predict import load_contract
    from database.connection import get_sqlalchemy_engine
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    cal = pd.DataFrame([dict(day=pd.Timestamp(s.session_date), opened=pd.Timestamp(s.open_at_utc),
        closed=pd.Timestamp(s.close_at_utc)) for s in cal.sessions(date(2026, 9, 1), date(2026, 12, 15)) if s.is_open])
    last = cal.loc[cal.closed.lt(cutoff), 'day'].max()
    symbols = sorted(set(s.upper() for s in re.split(r'[,;\s]+', UNIVERSE.read_text(encoding='utf-8-sig')) if s))
    sources = [Path(__file__), UNIVERSE, Path('config.yaml'),
        Path('service/options_directional/features.py'), Path('service/options_directional/runner.py'),
        Path('service/options_directional/config.py'), Path('common/daily_bar_sources.py'),
        Path('scripts/research/fr_p0_p1_directional_audit_20261026.py')]
    models = {}
    for batch in BATCHES.values():
        root, _, _, folds = load_contract('artifacts/models', batch)
        models[batch] = dict(profile_hash=digest(root/'feature_profile.json'), folds=folds)
        sources.extend(root/n for n in ('protocol.json', 'feature_profile.json', 'report.json'))
        sources.extend(Path(v['model_file']) for v in folds.values())
    protocol = dict(cutoff=cutoff, last_closed_session=last, symbols=symbols, config=cfg.snapshot(),
        models=models, model_policy=BATCHES, horizons=HORIZONS, signal_start='2026-09-14',
        decision='5 minutes before next official session opening; capped at snapshot clock',
        volume_timeframe='30Min', stop_loss_pct=.10,
        target='dominant protected excursion during full H sessions, before side-specific SL10',
        prices='current SQL split-adjusted bars, configured whole-row source preference',
        SQL='alpha_trade READ ONLY REPEATABLE READ UTC; rollback', provider_calls=0, LLM_calls=0,
        new_inference=False, training=False, threshold_search=False, independent_holdout=False,
        batch_evidence=batch_evidence(), sources={str(p):digest(p) for p in sources})
    write(output/'protocol.json', protocol)
    cal.to_parquet(output/'calendar.parquet', index=False)
    eng = get_sqlalchemy_engine()
    if eng.url.database != 'alpha_trade':
        raise ValueError('US only')
    try:
        with eng.connect() as c:
            c.execute(text("SET SESSION time_zone='+00:00'"))
            c.execute(text('SET SESSION MAX_EXECUTION_TIME=180000'))
            c.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            c.execute(text('SET SESSION TRANSACTION READ ONLY'))
            params = dict(batches=list(BATCHES.values()), start='2026-09-14', end=str(last.date()),
                          cutoff=cutoff.tz_localize(None).to_pydatetime())
            sql = '''SELECT p.prediction_date signal_day,p.symbol,p.proba_extreme,p.fold_start,p.batch_id,
                p.created_at prediction_created_at,l.created_at lineage_created_at,
                l.fold_start lineage_fold_start,l.model_available_date,l.target_name,l.target_horizon,
                l.model_sha256,l.feature_profile_sha256 FROM oracle_extreme_predictions p
                LEFT JOIN oracle_path_prediction_lineage l ON l.prediction_date=p.prediction_date
                AND l.symbol=p.symbol AND l.batch_id=p.batch_id
                WHERE p.batch_id IN :batches AND p.prediction_date BETWEEN :start AND :end
                AND p.created_at<=:cutoff AND l.created_at<=:cutoff'''
            raw = pd.DataFrame([dict(r) for r in c.execute(text(sql).bindparams(
                bindparam('batches', expanding=True)), params).mappings()])
            raw.to_parquet(output/'oracle-raw.parquet', index=False)
            ranked, coverage = qualified_ranking(raw, symbols, models, cfg, cal)
            ranked.to_parquet(output/'oracle-top20.parquet', index=False)
            coverage.to_csv(output/'oracle-coverage.csv', index=False)
            print(f'Oracle: {len(ranked)} TOP20 candidates, {ranked.signal_day.nunique()} sessions', flush=True)
            params.update(symbols=sorted(ranked.symbol.unique()), end=str((last+pd.Timedelta(days=1)).date()))
            queries = {
                'snapshots': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,
                    option_type,observed_at,available_at,provider_timestamp,open_interest,payload_hash,provider,feed
                    FROM stock_option_snapshots WHERE provider='alpaca' AND feed='indicative'
                    AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
                    AND available_at<=:cutoff AND observed_at<=:cutoff''',
                'volumes': '''SELECT id,underlying_symbol symbol,contract_symbol,expiration_date,strike,option_type,
                    bar_timestamp,observed_at,available_at,volume,payload_hash,provider,feed,provenance_status,timeframe
                    FROM stock_option_bars_delayed WHERE provider='alpaca' AND timeframe='30Min'
                    AND underlying_symbol IN :symbols AND available_at>=:start AND available_at<:end
                    AND bar_timestamp>=:start AND bar_timestamp<:end AND available_at<=:cutoff AND observed_at<=:cutoff''',
                'prices': '''SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,data_adjustment,
                    instrument_id,ingested_at,last_updated FROM stock_bars_daily WHERE symbol IN :symbols
                    AND date>=:start AND date<:end AND data_source IN ('eodhd_eod','alpaca_sip')'''}
            for name, sql in queries.items():
                f = pd.DataFrame([dict(r) for r in c.execute(text(sql).bindparams(
                    bindparam('symbols', expanding=True)), params).mappings()])
                f.to_parquet(output/(name+'.parquet'), index=False)
                print(name+' rows='+str(len(f)), flush=True)
            c.rollback()
    finally:
        eng.dispose()
    write(output/'snapshot-seal.json', dict(files={p.name:digest(p) for p in output.iterdir() if p.is_file()}))


def labels_for_path(path, window):
    """No filling of missing sessions or invented intraday high/low ordering."""
    g = path.reindex(window.day)
    numeric = g[['open','high','low','close','volume']].apply(pd.to_numeric, errors='coerce')
    ok = (np.isfinite(numeric.to_numpy(float)).all(axis=1) & numeric.gt(0).all(axis=1)
          & g.is_filled.eq(0) & g.instrument_id.notna() & g.data_adjustment.eq('split')
          & numeric.high.ge(numeric[['open','close']].max(axis=1))
          & numeric.low.le(numeric[['open','close']].min(axis=1)))
    if not ok.all() or g.instrument_id.nunique()!=1:
        return dict(status='INVALID_OR_MISSING_PRICE_IDENTITY')
    bars = [dict(date=str(d.date()), **r) for d,r in numeric[['open','high','low','close']].to_dict('index').items()]
    long, short = protected_excursion(bars,'LONG',sl=.10), protected_excursion(bars,'SHORT',sl=.10)
    direction, first = compare_paths(long, short)
    entry = bars[0]['open']
    up, down = 100*(numeric.high.max()/entry-1), 100*(1-numeric.low.min()/entry)
    return dict(status='LABEL' if direction!='AMBIGUOUS_OR_TIE' else 'AMBIGUOUS_PATH',
        dominant_direction=direction, first_protected_peak=first, max_up_pct=float(max(0,up)),
        max_down_pct=float(max(0,down)), dominant_unprotected='LONG' if up>down else 'SHORT' if down>up else 'TIE',
        terminal_return_pct=100*(bars[-1]['close']/entry-1),
        **{'long_'+k:v for k,v in long.items()}, **{'short_'+k:v for k,v in short.items()})


def describe(f):
    valid = f[f.status.eq('LABEL')]
    return dict(n=len(f), valid_n=len(valid), symbols=int(valid.symbol.nunique()),
        dates=int(valid.signal_day.nunique()), status_counts=f.status.value_counts().to_dict(),
        long_n=int(valid.dominant_direction.eq('LONG').sum()),
        long_share=float(valid.dominant_direction.eq('LONG').mean()) if len(valid) else None,
        mean_protected_up_pct=float(valid.long_lower_pct.mean()) if len(valid) else None,
        mean_protected_down_pct=float(valid.short_lower_pct.mean()) if len(valid) else None,
        unprotected_long_share=float(f.loc[f.status.isin(['LABEL','AMBIGUOUS_PATH']),
            'dominant_unprotected'].eq('LONG').mean()) if f.status.isin(['LABEL','AMBIGUOUS_PATH']).any() else None)


def auc_metrics(f):
    f = f[f.status.eq('LABEL') & f.combined_score.notna()]
    daily=[]
    for day,g in f.groupby('signal_day'):
        if g.dominant_direction.nunique()!=2:
            continue
        daily.append(dict(signal_day=str(day.date()), n=len(g), **{s:float(roc_auc_score(
            g.dominant_direction.eq('LONG'),g[s])) for s in ('volume_score','oi_score','combined_score')}))
    result=dict(n=len(f), dates=int(f.signal_day.nunique()), informative_dates=len(daily), daily=daily)
    for score in ('volume_score','oi_score','combined_score'):
        values=np.array([d[score] for d in daily])
        ci=None
        if len(values)>=2:
            rng=np.random.default_rng(20261030)
            samples=rng.choice(values,size=(3000,len(values)),replace=True).mean(axis=1)
            ci=[float(x) for x in np.quantile(samples,[.025,.975])]
        result[score]=dict(mean_daily_auc=float(values.mean()) if len(values) else None,
            pooled_auc=float(roc_auc_score(f.dominant_direction.eq('LONG'),f[score]))
                if len(f) and f.dominant_direction.nunique()==2 else None,
            exploratory_date_bootstrap_ci95=ci)
    return result


def summarize(f, cal, horizon):
    covered=f[f.combined_score.notna()]
    selected=f[f.selected]
    active_days=selected.signal_day.unique()
    positions={d:i for i,d in enumerate(cal.day)}
    spaced=[]
    for day in sorted(covered.loc[covered.status.isin(['LABEL','AMBIGUOUS_PATH']),'signal_day'].unique()):
        if not spaced or positions[day]-positions[spaced[-1]]>=horizon:
            spaced.append(day)
    first=covered.sort_values(KEY).drop_duplicates('symbol')[KEY]
    unprotected=covered[covered.status.isin(['LABEL','AMBIGUOUS_PATH'])].copy()
    unprotected['dominant_direction']=unprotected.dominant_unprotected
    unprotected['status']=np.where(unprotected.dominant_direction.eq('TIE'),'AMBIGUOUS_PATH','LABEL')
    return dict(all_top20=describe(f), scored_covered=describe(covered), retained_LONG=describe(selected),
        covered_on_selection_dates=describe(covered[covered.signal_day.isin(active_days)]),
        rejected_scored=describe(covered[~covered.selected]), auc=auc_metrics(covered),
        unprotected_auc=auc_metrics(unprotected),
        oracle_created_before_decision=dict(covered=describe(covered[covered.oracle_created_before_decision]),
            selected=describe(selected[selected.oracle_created_before_decision]),
            auc=auc_metrics(covered[covered.oracle_created_before_decision])),
        nonoverlap_dates=[str(pd.Timestamp(d).date()) for d in spaced],
        nonoverlap_auc=auc_metrics(covered[covered.signal_day.isin(spaced)]),
        first_symbol_auc=auc_metrics(covered.merge(first,on=KEY,validate='one_to_one')))


def analyze(output):
    if (output/'report.json').exists():
        raise FileExistsError('Immutable report')
    for n,sha in read(output/'snapshot-seal.json')['files'].items():
        if digest(output/n)!=sha: raise ValueError('Snapshot changed '+n)
    p=read(output/'protocol.json')
    for n,sha in p['sources'].items():
        if digest(n)!=sha: raise ValueError('Source changed '+n)
    from common.daily_bar_sources import select_daily_bars
    import yaml
    frozen_config=yaml.safe_load(Path('config.yaml').read_text(encoding='utf-8'))
    cfg=OptionsFilterConfig(**p['config']);cutoff=pd.Timestamp(p['cutoff'])
    cal=pd.read_parquet(output/'calendar.parquet')
    top=pd.read_parquet(output/'oracle-top20.parquet')
    snaps=pd.read_parquet(output/'snapshots.parquet');vol=pd.read_parquet(output/'volumes.parquet')
    prices=select_daily_bars(pd.read_parquet(output/'prices.parquet'),config=frozen_config)
    prices['date']=pd.to_datetime(prices.date)
    for frame in (snaps,vol):
        frame['receipt_day']=pd.to_datetime(frame.available_at,utc=True).dt.tz_convert('America/New_York').dt.date
    rows=[];daily=[]
    for day,g in top.groupby('signal_day',sort=True):
        decision=min(g.decision_at.iloc[0],cutoff)
        spot=prices[prices.date.eq(day)&prices.is_filled.eq(0)]
        spots={r.symbol:float(r.close) for r in spot.itertuples() if pd.notna(r.close) and r.close>0}
        features=build_features(snaps[snaps.receipt_day.eq(day.date())].copy(),
            vol[vol.receipt_day.eq(day.date())].copy(),spots,day.date(),decision)
        selected=select_top(g.to_dict('records'),features,cfg)
        meta=g.set_index('symbol').to_dict('index')
        for r in selected:
            rows.append({**meta[r['symbol']],**r})
        daily.append(dict(signal_day=str(day.date()),requested=len(g),covered=sum(r['symbol'] in features for r in selected),
            selected=sum(r['selected'] for r in selected), selected_symbols=[r['symbol'] for r in selected if r['selected']],
            reasons=pd.Series([r['reason'] for r in selected]).value_counts().to_dict()))
    scored=pd.DataFrame(rows)
    # Keep columns present even if every historical cohort is below min_covered.
    for col in ('volume_score','oi_score','combined_score'):
        if col not in scored: scored[col]=np.nan
    scored.to_csv(output/'top20-filter-decisions.csv',index=False)
    groups={s:g.set_index('date') for s,g in prices.groupby('symbol')}
    sessions=list(cal.day);paths=[]
    for r in scored.to_dict('records'):
        offset=sessions.index(r['entry_day'])
        for h in HORIZONS:
            window=cal.iloc[offset:offset+h]
            if len(window)<h or not window.closed.lt(cutoff).all():
                label=dict(status='NOT_MATURE')
            elif r['symbol'] not in groups:
                label=dict(status='MISSING_PRICES')
            else:
                label=labels_for_path(groups[r['symbol']],window)
            paths.append({**r,'horizon':h,**label})
    panel=pd.DataFrame(paths)
    panel.to_parquet(output/'paths.parquet',index=False)
    panel.to_csv(output/'paths.csv',index=False)
    write(output/'coverage-daily.json',daily)
    report=dict(status='COMPLETED_EXPLORATORY_NO_PROMOTION',cutoff=p['cutoff'],
        signal_first=str(top.signal_day.min().date()),signal_last=str(top.signal_day.max().date()),
        oracle_dates=int(top.signal_day.nunique()),oracle_candidates=len(top),
        option_covered=sum(d['covered'] for d in daily),scored=int(scored.combined_score.notna().sum()),
        selected=int(scored.selected.sum()),selected_symbols=int(scored.loc[scored.selected,'symbol'].nunique()),
        config=p['config'],batch_evidence=p['batch_evidence'],
        input_rows=dict(snapshots=len(snaps),volumes=len(vol),canonical_daily_bars=len(prices)),
        horizons={str(h):summarize(panel[panel.horizon.eq(h)],cal,h) for h in HORIZONS},
        limitations=['Exploratory replay, not independent holdout; current universe survivorship',
            'September Oracle reconstructed in October; report physical score availability separately',
            'Current daily bar vintages, no historical receipt certification of reference closes',
            'Indicative OI and unsigned options volume, not certified OPRA or trading intent',
            'Overlapping outcomes and repeated symbols; date bootstrap does not remove serial dependence',
            'Daily stop-bar high/low ordering unknown: bounds, ambiguous outcomes not forced',
            'Directional discrimination, not portfolio returns; no sale at future maximum assumed',
            'Missing whole TOP20 coverage not substituted; no stale OI carry-forward',
            '30Min production data differs from prior 1Day-volume audits; not directly comparable'])
    write(output/'report.json',report)
    write(output/'seal.json',dict(files={f.name:digest(f) for f in output.iterdir() if f.is_file()},sources=p['sources']))
    print('COMPLETED '+str(output),flush=True)
    print({h:dict(selected=v['retained_LONG'],auc=v['auc']['combined_score']) for h,v in report['horizons'].items()},flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['snapshot','analyze'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    (snapshot if args.phase=='snapshot' else analyze)(args.output)
