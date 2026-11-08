"""Annual causal per-symbol LONG selection inside Oracle TOP20, native Winner replay.

Research files only. No promotion, production predictions, broker or provider API.
Direction models fit on each stock's own daily history, never Oracle rank as LONG probability.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

LOG = logging.getLogger(__name__)
ROOT = Path('artifacts/research/us_winner_per_symbol_long/20261103-v2')
BATCH = 'model-factory-20261030213826-eda503'
MODEL = Path('artifacts/models')/BATCH/'oracle_path'
ARCHIVE = Path('artifacts/ihm_backtesting_runs/run/20261031_230707_7412d5ad/artifacts')
YEARS = (2024, 2025, 2026)
ENDS = {2024: '2024-12-31', 2025: '2025-12-31', 2026: '2026-10-29'}
ARMS = ('ORACLE_TOP20', 'ORACLE_TOP10', 'PER_SYMBOL_TOP10')
FEATURES = ['return_5d', 'return_10d', 'return_20d', 'momentum_60',
    'rsi_14', 'adx_14', 'atr20_pct', 'ema20_slope_10', 'ema50_slope_20',
    'distance_ema20', 'distance_ema50', 'range_position_20', 'range_position_50',
    'vol_ratio_20_60', 'rolling_volatility_20', 'relative_strength_20',
    'relative_strength_60', 'benchmark_return_5', 'benchmark_return_20',
    'market_volatility_20', 'market_trend_strength_50']
DELTAS = ('return_5d', 'rsi_14', 'vol_ratio_20_60')
INPUTS = FEATURES + [c+'_delta5' for c in DELTAS]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_new(path, value):
    if Path(path).exists():
        raise FileExistsError(path)
    atomic_json(Path(path), value)


def long_labels(bars, calendar, *, horizon, stop, fee, breaks=()):
    """Daily LONG profitability proxy, next open -> SL or open after N holdings.

    No take profit. Stop gaps fill at the worse open. All future windows must
    be complete; availability is conservatively the horizon exit session even
    when a stop occurred earlier. This is NOT a Winner confirmation label.
    """
    a = bars.set_index('date').reindex(calendar).copy()
    if a.index.duplicated().any():
        raise ValueError('Duplicate daily label bars')
    factor = pd.to_numeric(a.adj_close, errors='coerce').fillna(a.close)/a.close
    p = a[['open', 'high', 'low', 'close']].multiply(factor, axis=0)
    good = (np.isfinite(p).all(axis=1) & p.gt(0).all(axis=1)
        & p.high.ge(p[['open','close']].max(axis=1))
        & p.low.le(p[['open','close']].min(axis=1))
        & a.is_filled.eq(0) & a.volume.gt(0))
    o, lo = p.open.to_numpy(float), p.low.to_numpy(float)
    output = []
    for i in range(len(calendar)-horizon-1):
        end = i+horizon+1
        if not good.iloc[i:end+1].all():
            continue
        if a.instrument_id.iloc[i:end+1].dropna().nunique() != 1:
            continue
        if a.data_source.iloc[i:end+1].isna().any() or a.data_source.iloc[i:end+1].nunique() != 1:
            continue
        if any(event.crosses(calendar[i],calendar[end]) for event in breaks):
            continue
        entry = o[i+1]
        floor = entry*(1-stop)
        exit_price = o[end]
        reason = 'TIME_OPEN'
        for j in range(i+1,end):
            if o[j] <= floor:
                exit_price, reason = o[j], 'SL_GAP'
                break
            if lo[j] <= floor:
                exit_price, reason = floor, 'SL'
                break
        net = exit_price*(1-fee)/(entry*(1+fee))-1
        output.append(dict(date=calendar[i], label=float(net>0), label_net_return=net,
                           label_available_date=calendar[end], label_exit=reason))
    return pd.DataFrame(output, columns=['date','label','label_net_return','label_available_date','label_exit'])


def splits(panel, *, year, cutoff):
    """Purge both fit/calibration boundary and annual decision boundary."""
    calibration_start = pd.Timestamp(f'{year-1}-01-01')
    fit = panel.loc[panel.date.lt(calibration_start) & panel.label_available_date.lt(calibration_start)
                    & panel.label.notna()]
    cal = panel.loc[panel.date.ge(calibration_start) & panel.date.lt(cutoff)
                    & panel.label_available_date.lt(cutoff) & panel.label.notna()]
    return fit, cal


def choose(frame, arm):
    allowed = ['trade_date','symbol','rank','proba_extreme','long_probability','model_year','model_available_before']
    a = frame[[c for c in allowed if c in frame]].copy()
    if a.duplicated(['trade_date','symbol']).any():
        raise ValueError('Duplicate candidate')
    if arm == 'ORACLE_TOP20':
        return a
    if arm == 'ORACLE_TOP10':
        return a.loc[a['rank'].le(10)].copy()
    if arm != 'PER_SYMBOL_TOP10':
        raise ValueError('Unknown arm')
    a = a.loc[np.isfinite(a.long_probability)].copy()
    if not a.long_probability.between(0,1).all():
        raise ValueError('Invalid LONG probability')
    a = a.sort_values(['trade_date','long_probability','rank','symbol'], ascending=[True,False,True,True])
    a['directional_rank'] = a.groupby('trade_date').cumcount()+1
    return a.loc[a.directional_rank.le(10)].copy()


def prepare(root=ROOT):
    from common.winner_pyramiding import load_winner_pyramiding_config
    from common.market_calendar import get_market_calendar
    from common.trading_costs import TradingCostModel
    from modelFactory.oracle.security_continuity import load_security_discontinuities
    from modelFactory.oracle_path.predict import load_contract
    from backtesting.winner_campaign_replay import validate_scores
    from execution_engine.config import load_leverage_config_from_yaml
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    policy = load_winner_pyramiding_config()
    if not policy.enabled or policy.take_profit_pct is not None or policy.trailing_stop_pct is not None:
        raise ValueError('This frozen experiment expects current SL/time-only Winner defaults')
    modelroot, contract, _, folds = load_contract('artifacts/models', BATCH)
    if contract['horizon'] != 10:
        raise ValueError('User chose OracleH10')
    source_protocol = read(ARCHIVE/'protocol.json')
    if source_protocol['arguments']['oracle_batch_id'] != BATCH:
        raise ValueError('Wrong archived Oracle model')
    if digest(ARCHIVE/'signals.csv') != source_protocol['signals_sha256']:
        raise ValueError('Archived TOP20 changed')
    signals = pd.read_csv(ARCHIVE/'signals.csv', parse_dates=['trade_date'],float_precision='round_trip')
    removed = pd.read_csv(ARCHIVE/'excluded-signals.csv', parse_dates=['trade_date'],float_precision='round_trip')
    # Restore ALL original Oracle rows. Old whole-symbol future-data exclusions
    # must not determine this experiment's membership or reuse its +122% result.
    signals = pd.concat([signals,removed[list(signals.columns)]],ignore_index=True)
    if not signals.groupby('trade_date').size().eq(20).all():
        raise ValueError('Archived original TOP20 incomplete')
    signals = validate_scores(signals, profile_hash=digest(modelroot/'feature_profile.json'), folds=folds,
        expected_days=pd.to_datetime(signals.trade_date).dt.date.unique().tolist(), top_n=20,
        horizon=10, universe_size=20, min_coverage=1.)
    calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    cohorts = []
    for year in YEARS:
        days = calendar.session_dates(date(year,1,1), date.fromisoformat(ENDS[year]))
        seed = calendar.previous_session(days[0])
        expected = [seed]+days[:-1]
        frame = signals.loc[pd.to_datetime(signals.trade_date).dt.date.isin(expected)].copy()
        if len(frame) != len(expected)*20:
            raise ValueError(f'Incomplete Oracle cohort {year}')
        frame['year'] = year
        cohorts.append(frame)
    cohort = pd.concat(cohorts, ignore_index=True)
    cohort.to_parquet(root/'cohort.parquet',index=False)
    symbols = sorted(cohort.symbol.unique())
    sources = {str(p):digest(p) for p in [Path(__file__),Path('config.yaml'),ARCHIVE/'report.json',
        ARCHIVE/'protocol.json',ARCHIVE/'signals.csv',ARCHIVE/'excluded-signals.csv',modelroot/'protocol.json',modelroot/'feature_profile.json',
        Path('config/data_quality/security_discontinuities.json')]}
    protocol = dict(status='FROZEN_BEFORE_DIRECTIONAL_FIT',created_at_utc=datetime.now(timezone.utc).isoformat(),
        oracle_batch_id=BATCH,oracle_horizon=10,years=YEARS,ends=ENDS,arms=ARMS,
        winner_policy=asdict(policy),leverage=asdict(load_leverage_config_from_yaml()),
        initial_equity=4000.,annual_reset=True,account_type='margin',margin_interest_annual=.065,
        oracle_population='Original TOP20 archived after complete native coverage/lineage qualification; no outcome reselection',
        restored_pre_exclusion_signals=len(removed),old_whole_symbol_exclusions_not_applied=True,
        features=INPUTS,model='INDEPENDENT_LIGHTGBM_PER_SYMBOL_PER_YEAR_WITH_OWN_PLATT_CALIBRATION',
        fit=dict(n_estimators=120,max_depth=3,num_leaves=7,learning_rate=.03,min_child_samples=60,
                 reg_alpha=1.,reg_lambda=10.,verbosity=-1,n_jobs=1,random_state=20261103),
        min_fit_rows=504,min_fit_each_class=40,min_calibration_rows=100,min_calibration_each_class=15,
        label='NET_LONG_NEXT_OPEN_SL_DEFAULT_HOLDING_N_EXIT_NEXT_OPEN_POSITIVE',
        label_is_proxy='Daily bar entry, no confirmation; final economic test uses actual native Winner5m confirmation/delay.',
        label_horizon=policy.horizon_sessions,label_fee_per_leg=TradingCostModel().per_leg_cost_pct,
        cutoff='Before first annual signal date; mature labels strictly before boundary; annual refit using preceding years.',
        calibration='Previous calendar year, own stock only; no test labels or threshold optimization.',
        uncovered='No shared model, neutral score, Oracle N+1 or synthesized probability fallback. Fewer than10 allowed and counted.',
        ranking='Top10 calibrated LONG probability, then Oracle rank; retain original Oracle priority inside Winner.',
        scope='Models fitted on own full daily history; selection applied only inside original OracleTOP20.',
        historical_size_factor=False,size_factor_reason='Same default as IHM research replay; no dated capitalization substitution.',
        intraday_missing='Same local per-entry POST_HOC availability gate; no downloads, interpolation or whole-symbol exclusion.',
        data_limitations=['Current survivorship universe','Historical features/prices reconstituted, not prospective PIT receipts',
            'Existing Oracle folds/2024-26 periods already examined; not virgin holdouts','Current sectors, historical OHLC assumptions'],
        production_model_changes=False,sql_writes=False,provider_calls=0,llm_calls=0,broker_calls=0,sources=sources)
    save_new(root/'protocol.json',protocol)
    paneldir = root/'panel';paneldir.mkdir()
    schedule = pd.DatetimeIndex(calendar.session_dates(date(2019,1,1),date(2026,10,29)))
    registry = load_security_discontinuities()
    feature_files = []
    folders = sorted((MODEL/'chunks').iterdir())
    for i, folder in enumerate(folders):
        featpath, barpath = folder/'features.parquet',folder/'bars.parquet'
        # The archive was generated as chronological features. No target columns are loaded here.
        f = pd.read_parquet(featpath,columns=['symbol','date',*FEATURES])
        f = f.loc[f.symbol.isin(symbols)].copy()
        if not f.empty:
            bars = pd.read_parquet(barpath)
            for symbol, group in f.groupby('symbol',sort=True):
                if group.date.duplicated().any():
                    raise ValueError('Duplicate causal features')
                g = group.set_index('date').reindex(schedule)
                for column in DELTAS:
                    g[column+'_delta5'] = (g[column]-g[column].shift(5)).where(
                        g[column].notna().rolling(6).sum().eq(6))
                g['symbol'] = symbol
                g = g.rename_axis('date').reset_index()
                labels = long_labels(bars.loc[bars.symbol.eq(symbol)].copy(),schedule,
                    horizon=policy.horizon_sessions,stop=policy.stop_loss_pct,
                    fee=protocol['label_fee_per_leg'],breaks=registry.get(symbol,()))
                g = g.merge(labels,on='date',how='left',validate='one_to_one')
                path = paneldir/(symbol+'.parquet')
                if path.exists():raise ValueError('Symbol occurs in multiple input chunks')
                g.to_parquet(path,index=False)
        feature_files.append(dict(features=str(featpath),features_sha256=digest(featpath),
                                  bars=str(barpath),bars_sha256=digest(barpath)))
        atomic_json(root/'progress.json',dict(status='PREPARING_DAILY_LABELS',completed=i+1,total=len(folders)))
        LOG.info('Features and labels chunk %d/%d',i+1,len(folders))
    missing = sorted(set(symbols)-{p.stem for p in paneldir.glob('*.parquet')})
    save_new(root/'inputs-ready.json',dict(panel_symbols=len(symbols)-len(missing),missing=missing,
        cohort_sha256=digest(root/'cohort.parquet'),source_chunks=feature_files,
        files={p.name:digest(p) for p in paneldir.glob('*.parquet')}))
    atomic_json(root/'progress.json',dict(status='PREPARED',symbols=len(symbols),missing=missing))
    return protocol


def train(root=ROOT):
    from lightgbm import LGBMClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    root = Path(root);p = read(root/'protocol.json');ready = read(root/'inputs-ready.json')
    if digest('config.yaml') != p['sources']['config.yaml']:
        raise ValueError('Production defaults changed after freeze')
    if digest(root/'cohort.parquet') != ready['cohort_sha256']:
        raise ValueError('Candidate cohort changed')
    if (root/'predictions.parquet').exists():raise FileExistsError('Do not overwrite scored predictions')
    cohort = pd.read_parquet(root/'cohort.parquet')
    cohort['trade_date'] = pd.to_datetime(cohort.trade_date)
    predictions=[];evidence=[];started=time.monotonic()
    for year in YEARS:
        annual = cohort.loc[cohort.year.eq(year)].copy()
        cutoff = pd.to_datetime(annual.trade_date).min().normalize()
        models = root/'models'/str(year);models.mkdir(parents=True,exist_ok=True)
        for n,(symbol, candidates) in enumerate(annual.groupby('symbol',sort=True)):
            path = root/'panel'/(symbol+'.parquet')
            record=dict(year=year,symbol=symbol,cutoff_before=str(cutoff.date()),status='UNQUALIFIED')
            scores = candidates.copy();scores['long_probability']=np.nan
            if path.exists():
                if digest(path) != ready['files'][path.name]:raise ValueError('Training panel changed')
                panel=pd.read_parquet(path);panel=panel.loc[panel[INPUTS].notna().mean(axis=1).ge(.8)].copy()
                fit, cal = splits(panel,year=year,cutoff=cutoff)
                record.update(fit_rows=len(fit),calibration_rows=len(cal),
                    fit_positive=int(fit.label.sum()),calibration_positive=int(cal.label.sum()))
                enough=(len(fit)>=p['min_fit_rows'] and len(cal)>=p['min_calibration_rows']
                    and fit.label.value_counts().reindex([0.,1.],fill_value=0).min()>=p['min_fit_each_class']
                    and cal.label.value_counts().reindex([0.,1.],fill_value=0).min()>=p['min_calibration_each_class'])
                if enough:
                    lo,hi=fit[INPUTS].quantile(.01),fit[INPUTS].quantile(.99)
                    x=fit[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
                    z=cal[INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
                    model=make_pipeline(SimpleImputer(strategy='median'),LGBMClassifier(**p['fit']))
                    model.fit(x,fit.label.astype(int))
                    v=np.clip(model.predict_proba(z)[:,1],1e-6,1-1e-6)
                    if np.std(v)>1e-6:
                        calibrator=LogisticRegression(C=1.,random_state=20261103)
                        calibrator.fit(np.log(v/(1-v)).reshape(-1,1),cal.label.astype(int))
                        merged=candidates.merge(panel[['date',*INPUTS]],left_on='trade_date',right_on='date',how='left',validate='one_to_one')
                        valid=merged[INPUTS].notna().mean(axis=1).ge(.8)
                        if valid.any():
                            obs=merged.loc[valid,INPUTS].replace([np.inf,-np.inf],np.nan).clip(lo,hi,axis=1)
                            prob=np.clip(model.predict_proba(obs)[:,1],1e-6,1-1e-6)
                            scores.loc[valid.to_numpy(),'long_probability']=calibrator.predict_proba(np.log(prob/(1-prob)).reshape(-1,1))[:,1]
                        modelpath=models/(symbol+'.joblib')
                        joblib.dump(dict(model=model,calibrator=calibrator,lo=lo,hi=hi,features=INPUTS),modelpath)
                        record.update(status='FITTED',model_sha256=digest(modelpath),
                            calibration_slope=float(calibrator.coef_[0,0]),fit_label_available_max=str(fit.label_available_date.max()),
                            calibration_label_available_max=str(cal.label_available_date.max()))
            scores['model_year']=year;scores['model_available_before']=cutoff
            predictions.append(scores);evidence.append(record)
            if n%20==0:
                atomic_json(root/'progress.json',dict(status='FITTING_PER_SYMBOL',year=year,completed=n+1,
                    total=annual.symbol.nunique(),elapsed_seconds=time.monotonic()-started))
                LOG.info('Year%s models %s/%s',year,n+1,annual.symbol.nunique())
        atomic_json(root/f'model-evidence-{year}.json',[r for r in evidence if r['year']==year])
    scores=pd.concat(predictions,ignore_index=True)
    scores.to_parquet(root/'predictions.parquet',index=False)
    coverage=scores.assign(qualified=scores.long_probability.notna()).groupby('year').agg(
        candidates=('symbol','size'),qualified=('qualified','sum'),symbols=('symbol','nunique')).reset_index()
    save_new(root/'training-report.json',dict(status='FITTED_RESEARCH_ONLY',elapsed_seconds=time.monotonic()-started,
        training_source_sha256=digest(__file__),
        coverage=coverage.to_dict('records'),models_fitted=sum(r['status']=='FITTED' for r in evidence),
        model_attempts=len(evidence),predictions_sha256=digest(root/'predictions.parquet'),
        available_models_are_not_production_promotions=True))
    atomic_json(root/'progress.json',dict(status='MODELS_READY',models_fitted=sum(r['status']=='FITTED' for r in evidence)))
    return coverage


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','train'],required=True)
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    print({'prepare':prepare,'train':train}[args.phase](args.root))
