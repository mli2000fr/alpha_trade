"""C/D continuation: immutable T0 reference and matched historical fit rows."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime,timezone
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests
from sqlalchemy import text,bindparam

from scripts.research import us_q051_feature_groups_20261116 as base
from scripts.research import us_q051_feature_groups_replay_20261116 as replay
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_q051_features173_20261116 import read,link,shared
from scripts.research.us_q051_features173_sip_replay_20261116 import ROOT as PRICE_EVIDENCE,provider_frame
from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices,ROOT as EXT

REFERENCE=base.ROOT
ROOT=Path('artifacts/research/us_q051_feature_groups/20261116-lot2-cd')
AB=deepcopy(base.GROUPS)
GROUPS={'C':['sma20_minus_sma50','sma50_minus_sma200','ema20_minus_sma20'],
        'D':['cmf_20','volume_ratio_20','volume_zscore_20','daily_return_times_volume_ratio_20']}
_original_common=base.common_panel
_original_fit=base.fit_variants


def common_panel(bars,benchmark,calendar):
    """Preserve the original A/B common mask; retain C/D as extra columns."""
    from common.daily_bar_sources import select_daily_bars
    from modelFactory.features import compute_features
    from modelFactory.oracle_path.directional import INPUTS,DELTAS
    bars=select_daily_bars(bars.copy()).sort_values('date');symbol=str(bars.symbol.iloc[0])
    grid=bars.set_index('date').reindex(calendar).rename_axis('date').reset_index();grid['symbol']=symbol
    for c in ['open','high','low','close','adj_close','volume','is_filled']:grid[c]=pd.to_numeric(grid[c],errors='coerce')
    if 'vwap' not in grid:grid['vwap']=grid.close
    good=(grid[['open','high','low','close']].notna().all(axis=1)&grid[['open','high','low','close']].gt(0).all(axis=1)
        &grid.is_filled.eq(0)&grid.volume.gt(0)&grid.instrument_id.notna())
    grid.loc[~good,['open','high','low','close','adj_close','volume','vwap']]=np.nan
    f=compute_features(grid,benchmark_df=benchmark,feature_set='expert',include_factors=True).set_index('date').reindex(calendar)
    for c in DELTAS:f[c+'_delta5']=(f[c]-f[c].shift(5)).where(f[c].notna().rolling(6).sum().eq(6))
    prior=list(dict.fromkeys(AB['A']+AB['B']));new=list(dict.fromkeys(GROUPS['C']+GROUPS['D']))
    eligible=(good.rolling(60,min_periods=60).sum().eq(60).to_numpy()
        &f[INPUTS].notna().mean(axis=1).ge(.8).to_numpy()&np.isfinite(f[prior].to_numpy(float)).all(axis=1))
    result=f.loc[eligible,[*INPUTS,*prior,*new]].rename_axis('date').reset_index();result['symbol']=symbol
    with patch.object(base,'GROUPS',AB):expected=_original_common(bars,benchmark,calendar)
    pd.testing.assert_frame_equal(result[expected.columns],expected,rtol=0,atol=1e-12)
    return result


def prepare():
    if (ROOT/'protocol.json').exists():return read(ROOT/'protocol.json')
    ROOT.mkdir(parents=True,exist_ok=True)
    if read(REFERENCE/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Reference not complete')
    plan=deepcopy(read(REFERENCE/'protocol.json'))
    for file,h in plan['sources'].items():
        if digest(Path(file))!=h:raise ValueError('Reference source changed: '+file)
    from modelFactory.oracle_path.directional import INPUTS
    plan.update(groups=GROUPS,features={v:[*INPUTS,*extra] for v,extra in GROUPS.items()},
        reference_root=str(REFERENCE),common_model_eligibility='Frozen T0 cohort; new C/D constant models abstain separately',
        study='Add C/D independently to the exact 24 compact inputs; preserve reference 2021-2026',
        eligibility_mask='Exact lot1 T0/A/B common input mask; C/D missing columns are past-only imputed, never used to drop rows',
        reference_refits=0,created_at_utc=datetime.now(timezone.utc).isoformat())
    plan['sources'][str(Path(__file__))]=digest(Path(__file__))
    review=Path('scripts/research/us_q051_feature_groups_cd_review_20261116.py')
    plan['sources'][str(review)]=digest(review)
    for file in ['protocol.json','comparison.csv','annual-comparison.csv','capital-curves.csv','inputs/manifest.json']:
        path=REFERENCE/file;plan['sources'][str(path)]=digest(path)
    for file,h in read(REFERENCE/'inputs/manifest.json')['files'].items():
        if digest(Path(file))!=h:raise ValueError('Frozen reference market changed: '+file)
        plan['sources'][file]=h
    for profile in ['SIMPLE','VOL20_REGIME']:
        folder=REFERENCE/'variants/T0/cases'/('T0_'+profile)
        for name in ['report.json','equity-daily.csv','equity-5m.parquet','annual-summary.csv','trades.csv','configuration.json']:
            file=folder/'result'/name;plan['sources'][str(file)]=digest(file)
    for variant in ['T0']:
        for file in ['signals.parquet','models.json','rankings.parquet']:
            path=REFERENCE/'variants'/variant/file;plan['sources'][str(path)]=digest(path)
    for year in range(2021,2027):
        for name in ['oracle.parquet','pool.parquet']:
            source=REFERENCE/'years'/str(year)/name;target=ROOT/'years'/str(year)/name;link(source,target)
            plan['sources'][str(target)]=digest(target)
    for task in plan['tasks']:
        source=REFERENCE/'jobs'/task['key']
        done=read(source/'done.json')
        for name in ['models.json','T0-probabilities.parquet','labels.parquet']:
            if digest(source/name)!=done['outputs'][name]:raise ValueError('Changed reference training output')
            plan['sources'][str(source/name)]=done['outputs'][name]
        for r in read(source/'models.json')['models']:
            if r['variant']=='T0':
                if digest(Path(r['file']))!=r['sha256']:raise ValueError('Reference model changed')
                plan['sources'][r['file']]=r['sha256']
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'progress.json',dict(status='READY',variants=list(GROUPS),training_jobs=len(plan['tasks']),reference_refits=0))
    return plan


def worker(key):
    import joblib
    from modelFactory.oracle_path.directional_metrics import predict
    folder=REFERENCE/'jobs'/key
    records={(r['symbol'],r['model_year']):r for r in read(folder/'models.json')['models'] if r['variant']=='T0'}
    prior_predictions=pd.read_parquet(folder/'T0-probabilities.parquet');audits=[];missing=[]
    def matched_fit(panel,year,seed):
        symbol=str(panel.symbol.iloc[0]) if len(panel) else None
        record=records.get((symbol,int(year)))
        if record is None:return {},dict(reason='NO_QUALIFIED_REFERENCE_T0_MODEL')
        # Every scored stock/date must exactly reproduce the reference inputs.
        old=prior_predictions[prior_predictions.symbol.eq(symbol)&prior_predictions.date.dt.year.eq(year)]
        a=old[['date','symbol','long_probability']].merge(panel,on=['date','symbol'],validate='one_to_one')
        if len(a)!=len(old):raise ValueError('Reference prediction eligibility changed')
        expected=predict(joblib.load(record['file']),a)
        if not np.allclose(expected,a.long_probability,rtol=0,atol=1e-12):raise ValueError('Reference T0 prediction changed')
        weights={};metrics={};metadata=None
        for variant,cols in GROUPS.items():
            with patch.object(base,'GROUPS',{variant:cols}):w,m=_original_fit(panel,year,seed)
            if not w:
                missing.append(dict(symbol=symbol,year=int(year),variant=variant,**m));continue
            for field in ['fit_rows','calibration_rows','fit_start','fit_end','calibration_start','calibration_end','available']:
                if m[field]!=record[field]:raise ValueError('Reference training membership differs: '+field)
            weights.update(w);metrics.update(m['metrics']);metadata={k:v for k,v in m.items() if k!='metrics'}
        audits.append(dict(symbol=symbol,year=int(year),reference_predictions_checked=len(a),max_prediction_difference=float(np.max(np.abs(expected-a.long_probability))) if len(a) else 0.,reference_refit=False))
        if not weights:return {},dict(reason='NEW_VARIANTS_CONSTANT_OR_UNQUALIFIED')
        return weights,{**metadata,'metrics':metrics}
    with patch.object(base,'ROOT',ROOT),patch.object(base,'GROUPS',GROUPS),patch.object(base,'common_panel',common_panel),patch.object(base,'fit_variants',matched_fit):
        base.worker(key)
    target=ROOT/'jobs'/key
    atomic_json(target/'reference-equivalence.json',dict(status='PASS',records=audits,new_model_abstentions=missing,reference_refits=0))


class ReferencePrices(ExtendedPrices):
    @lru_cache(maxsize=6)
    def day(self,day):
        groups=dict(super().day(day));extra=pd.read_parquet(REFERENCE/'inputs/intraday'/(str(day)+'.parquet'))
        for symbol,g in extra.groupby('symbol') if not extra.empty else []:
            if symbol in groups:raise ValueError('Reference tape overwrites original group')
            groups[symbol]=g
        return groups


def missing_pairs(day,wanted,present):
    # Keep previously queried empty responses empty, preserving the exact T0 tape.
    queried=set(read(REFERENCE/'inputs/intraday'/(str(day)+'.json'))['requested'])
    return sorted(set(wanted)-set(present)-queried)


def prepare_market():
    from database.connection import get_sqlalchemy_engine
    from backtesting.winner_data import daily_bars
    from backtesting.winner_campaign_replay import SqlIntradaySource
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    inputs=ROOT/'inputs';inputs.mkdir(exist_ok=True)
    ready=inputs/'manifest.json'
    if ready.exists():
        for file,h in read(ready)['files'].items():
            if digest(Path(file))!=h:raise ValueError('Changed prepared market input')
    else:
        pivots={c:pd.read_parquet(REFERENCE/'inputs'/(c+'.parquet')) for c in ['open','high','low','close','volume']}
        sectors=pd.read_parquet(REFERENCE/'inputs/sectors.parquet');actions=pd.read_parquet(REFERENCE/'inputs/actions.parquet')
        signals=[pd.read_parquet(ROOT/'variants'/v/'signals.parquet') for v in GROUPS]
        names=set().union(*(set(f.symbol) for f in signals));extra=sorted(names-set(pivots['close']))
        sessions=[d.date() for d in pivots['close'].index if '2021-01-01'<=str(d.date())<='2026-10-01']
        windows=shared.supplemental_windows(signals,sessions,set(),horizon=10)
        old=ReferencePrices(EXT);tape=inputs/'intraday';tape.mkdir(exist_ok=True)
        engine=get_sqlalchemy_engine(db_name='alpha_trade')
        with ReadOnlyReplay(ROOT).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),engine.connect() as conn,conn.begin():
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            if extra:
                pieces=[daily_bars(conn,extra[i:i+100],pivots['close'].index.min().date(),date_from_end()) for i in range(0,len(extra),100)]
                daily=pd.concat(pieces,ignore_index=True);daily.to_parquet(inputs/'additional-daily.parquet',index=False)
                query=lambda sql:pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,params=dict(symbols=extra))
                sec=query('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols')
                ca=query("SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events WHERE symbol IN :symbols AND ex_date BETWEEN '2021-01-01' AND '2026-10-01'")
                for c in pivots:pivots[c]=pd.concat([pivots[c],daily.pivot(index='date',columns='symbol',values=c)],axis=1).sort_index()
                sectors=pd.concat([sectors,sec],ignore_index=True);actions=pd.concat([actions,ca],ignore_index=True)
            if names-set(sectors.symbol):raise ValueError('Missing symbol sector identity')
            source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
            for i,day in enumerate(sessions):
                path=tape/(str(day)+'.parquet');receipt=tape/(str(day)+'.json')
                if not receipt.exists():
                    missing=missing_pairs(day,windows[day],old.day(day))
                    pieces=[source(day,missing[j:j+100]) for j in range(0,len(missing),100)];pieces=[f for f in pieces if not f.empty]
                    f=pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame();f.to_parquet(path,index=False)
                    atomic_json(receipt,dict(day=str(day),requested=missing,rows=len(f),reference_empty_responses_preserved=True))
                atomic_json(ROOT/'progress.json',dict(status='FREEZING_COMMON_MARKET_READ_ONLY',completed=i+1,total=len(sessions),last_date=str(day)))
        for c,f in pivots.items():f.to_parquet(inputs/(c+'.parquet'))
        sectors.to_parquet(inputs/'sectors.parquet',index=False);actions.to_parquet(inputs/'actions.parquet',index=False)
        atomic_json(ready,dict(files={str(p):digest(p) for p in inputs.rglob('*') if p.is_file() and p!=ready},provider_calls=0,SQL_writes=0))
    # Create case plans even when resuming a completed market snapshot.
    plan=read(ROOT/'protocol.json');sources={**plan['sources'],**read(ready)['files']}
    from scripts.research import us_q051_features173_replay_20261116 as native
    sources[str(Path(native.__file__))]=digest(Path(native.__file__))
    for variant in GROUPS:
        vroot=ROOT/'variants'/variant;link(vroot/'signals.parquet',vroot/'inputs/signals.parquet')
        annual=read(vroot/'models.json')
        for item in annual.values():item.update(model_manifest_sha256=digest(vroot/'models.json'),model_protocol_sha256=digest(ROOT/'protocol.json'))
        file=vroot/'inputs/signals.parquet'
        atomic_json(vroot/'replay-protocol.json',dict(start=plan['start'],end=plan['end'],initial_equity=4000.,annual_models=annual,
            reference=plan['reference'],sources={**sources,str(file):digest(file)},selection=plan['selection'],group=variant,
            research_features=plan['features'][variant],provider_calls=0,SQL_writes=0,orders=0,production_changes=False))


def date_from_end():
    return pd.Timestamp('2026-10-01').date()


def run_case(key):
    with patch.object(replay,'ROOT',ROOT),patch.object(replay,'GROUPS',GROUPS),\
        patch('scripts.research.us_winner_vol20_extensions_20261109.ExtendedPrices',ReferencePrices):
        replay.run_case(key)


def launch(tasks,limit,phase):
    waiting=list(tasks);active=[]
    try:
        while waiting or active:
            while waiting and len(active)<limit:
                key=waiting.pop(0);logs=ROOT/'logs';logs.mkdir(exist_ok=True)
                out=(logs/(key+'.stdout.log')).open('ab');err=(logs/(key+'.stderr.log')).open('ab')
                process=subprocess.Popen([sys.executable,'-X','utf8','-u','-m',__spec__.name,'--phase',phase,'--key',key],
                    cwd=Path.cwd(),stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                active.append((key,process,out,err))
            for item in active[:]:
                key,p,out,err=item
                if p.poll() is None:continue
                out.close();err.close();active.remove(item)
                if p.returncode:raise RuntimeError('Worker failed: '+key+'; inspect logs')
            atomic_json(ROOT/'progress.json',dict(status='TRAINING' if phase=='worker' else 'REPLAYING',completed=len(tasks)-len(waiting)-len(active),
                total=len(tasks),active=[x[0] for x in active],reference_refits=0,updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if active:time.sleep(2)
    finally:
        for key,p,out,err in active:
            if p.poll() is None:p.terminate();p.wait()
            out.close();err.close()


def finish():
    from scripts.research.us_q051_feature_groups_cd_review_20261116 import finish_review
    with patch.object(replay,'ROOT',ROOT),patch.object(replay,'GROUPS',GROUPS):replay.finish()
    finish_review()


def run():
    plan=prepare()
    try:
        # Completed chunks are verified by base.worker and not fitted again.
        pending=[t['key'] for t in plan['tasks'] if not (ROOT/'jobs'/t['key']/'done.json').exists()]
        launch(pending,4,'worker')
        with patch.object(base,'ROOT',ROOT),patch.object(base,'GROUPS',GROUPS):base.assemble()
        prepare_market()
        cases=[v+'_'+p for v in GROUPS for p in ['SIMPLE','VOL20_REGIME']]
        pending=[n for n in cases if not (ROOT/'variants'/n.split('_')[0]/'cases'/n/'ihm.json').exists()]
        launch(pending,3,'case');finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['all','prepare','worker','case'],required=True);parser.add_argument('--key')
    args=parser.parse_args()
    if args.phase=='all':run()
    elif args.phase=='prepare':prepare()
    elif args.phase=='worker':worker(args.key)
    else:run_case(args.key)
