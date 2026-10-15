"""New frozen Oracle baseline, SELECT-only preparation and offline portfolios.

One writer per output. No production training, SQL writes or broker calls.
Annual portfolios restart with USD 4000; end-2026 decisions are immature.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from functools import partial
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event, text

from common.config_loader import load_config
from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle_barrier import SCORES
from modelFactory.oracle_barrier.labels import load_bars
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_comparison import SECTORS, freeze_candidates, read, readonly_statement
from scripts.research.us_oracle_barrier_exit_grid import GridLedger
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from scripts.research.us_oracle_h20_dataset_audit import readonly_begin, restore_ranks
from service.market import parse_market_regimes

MODEL = Path('artifacts/models/model-factory-20261012183840-6d6569/oracle_barrier')
COUNTS = (10, 20, 50)
YEARS = (2024, 2025, 2026)
END = '2026-09-03'
AS_OF = '2026-10-09'
LOG = logging.getLogger(__name__)


def code_hashes():
    paths = {Path(__file__), Path('config.yaml'), SECTORS}
    for folder in ('backtesting', 'risk_management', 'execution_engine', 'service/market', 'modelFactory'):
        paths.update(Path(folder).rglob('*.py'))
    paths.update(Path('scripts/research').glob('us_oracle_tp20_sl10*.py'))
    paths.update(Path('scripts/research')/name for name in (
        'us_concentrated_contract_audit.py', 'us_concentrated_live_portfolio.py',
        'us_oracle_barrier_exit_grid.py', 'us_oracle_merger_ledger.py'))
    return {str(p): digest(p) for p in sorted(paths)}


def model_contract(model):
    protocol, profile, report = [read(model/name) for name in
        ('protocol.json', 'feature_profile.json', 'report.json')]
    if report['status'] != 'completed' or protocol['barriers'] != {
        'take_profit_pct': .2, 'stop_loss_pct': .1, 'max_sessions': 20}:
        raise ValueError('Completed TP20/SL10 model required')
    folds = sorted((model/'folds').iterdir())
    fold = folds[-1]
    done = read(fold/'done.json')
    verify_hashes(fold, done['files'])
    for head in done['metrics']['heads'].values():
        if head['status'] != 'TRAINED' or pd.Timestamp(head['val_available_max']) >= pd.Timestamp('2024-01-01'):
            raise ValueError('Base model selection uses external labels')
    return protocol, profile, fold


def checkpoint(root, name, builder):
    path, marker = root/name, root/(name+'.json')
    if marker.exists():
        verify_hashes(root, read(marker)['files'])
        return pd.read_parquet(path)
    result = builder()
    result.to_parquet(path, index=False)
    atomic_json(marker, dict(rows=len(result), files={name:digest(path)}))
    return result


def prepare(root, model=MODEL):
    import lightgbm as lgb
    root, model = Path(root), Path(model)
    root.mkdir(parents=True, exist_ok=True)
    protocol, profile, fold = model_contract(model)
    symbols, columns = sorted(protocol['universe']), profile['feature_columns']
    source_paths = [model/'protocol.json', model/'feature_profile.json', model/'report.json',
                    fold/'done.json', fold/'long_model.txt', fold/'short_model.txt', SECTORS]
    frozen = dict(batch_id=protocol['batch_id'], model=str(model), frozen_fold=fold.name,
        model_files={str(p):digest(p) for p in source_paths}, columns=columns,
        universe=symbols, years=YEARS, counts=COUNTS, start='2024-01-01',
        decision_end=END, as_of=AS_OF, take_profit_pct=.2, stop_loss_pct=.1,
        trailing=False, expiry='open of holding session 21', side='LONG',
        annual_initial_equity=4000, currency='USD', primary_count=10,
        experiment_fit='OOF 2018-2021 fit; 2022 validation; freeze before 2024; no test tuning',
        sql_writes=False, broker_calls=False, current_sectors_non_pit=True,
        limitations=['static survivor universe', 'current adjusted provider OHLC, not raw fills',
            'macro and selector vintage availability not independently certified',
            '2024-2026 already explored in earlier studies; not virgin holdouts',
            'baseline native ATR sizing retained despite fixed SL10',
            'annual decision cohorts include January exit tails; no inter-year compounding'])
    marker=root/'protocol.json'
    serial=json.loads(json.dumps(frozen, default=str))
    if marker.exists() and read(marker)!=serial:
        raise ValueError('Frozen protocol differs: use a new directory')
    atomic_json(marker, frozen)
    verify_hashes(Path('.'), frozen['model_files'])
    if (root/'ready.json').exists():
        verify_hashes(root, read(root/'ready.json')['files'])
        return
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':
        raise ValueError('US database required')
    event.listen(engine,'begin',readonly_begin)
    event.listen(engine,'before_cursor_execute',readonly_statement)
    needed=list(dict.fromkeys([c for c in columns if not c.endswith('_xs_rank')] +
        [c.removesuffix('_xs_rank') for c in columns if c.endswith('_xs_rank')]))
    parts, price_parts=[],[]
    options={**profile['generator_options'],'enable_cross_sectional_ranks':False}
    try:
        for i, offset in enumerate(range(0,len(symbols),25)):
            atomic_json(root/'progress.json', dict(status='RUNNING',phase='features_and_prices',
                completed_chunks=i,total_chunks=(len(symbols)+24)//25))
            chunk=symbols[offset:offset+25]
            def features():
                frame=build_feature_matrix(engine,chunk,start_date='2016-01-01',
                    end_date=END,generator_options=options)
                return frame.loc[frame.date.ge('2024-01-01'),['date','symbol',*needed]].copy()
            parts.append(checkpoint(root,f'features-{i:03d}.parquet',features))
            price_parts.append(checkpoint(root,f'prices-{i:03d}.parquet',
                lambda chunk=chunk:load_bars(engine,chunk,'2023-01-01',AS_OF)))
            LOG.info('Preparation %s/%s',i+1,(len(symbols)+24)//25)
        price_parts.append(checkpoint(root,'benchmark.parquet',
            lambda:load_bars(engine,['SPY','VMRK'],'2023-01-01',AS_OF)))
        checkpoint(root,'macro.parquet',lambda:pd.read_sql(text(
            'SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN :start AND :end'),
            engine,params=dict(start='2023-01-01',end=AS_OF),parse_dates=['trade_date']))
    finally:
        engine.dispose()
    features=pd.concat(parts,ignore_index=True).sort_values(['date','symbol'])
    if features.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate feature keys')
    features=restore_ranks(features,columns)
    features[columns]=features[columns].replace([np.inf,-np.inf],np.nan).astype(np.float32)
    scores=features[['date','symbol']].copy()
    for side in ('long','short'):
        booster=lgb.Booster(model_file=str(fold/f'{side}_model.txt'))
        if booster.feature_name()!=columns:
            raise ValueError('Feature contract differs')
        scores[SCORES[side]]=booster.predict(features[columns],num_threads=3)
    prices=pd.concat(price_parts,ignore_index=True)
    prices=prices.drop_duplicates(['date','symbol']) if 'SPY' in symbols else prices
    if prices.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate price keys')
    # Explicit reuse of qualified research-only OHLC/volume corrections. No SQL mutation.
    repairs=Path('artifacts/research/us_oracle_barrier_comparison/repaired-volume-grid-20261012-v1')
    verify_hashes(repairs,read(repairs/'prepared.json')['files'])
    repaired=pd.read_parquet(repairs/'prices.parquet')
    # Override only documented affected instruments, never silently all refreshed data.
    affected={'AVB','EQR','VMRK','BAND','GPRE','ATEX'}
    overlay=repaired.loc[repaired.symbol.isin(affected)]
    keys=pd.MultiIndex.from_frame(overlay[['date','symbol']])
    prices=pd.concat([prices.loc[~pd.MultiIndex.from_frame(prices[['date','symbol']]).isin(keys)],overlay],ignore_index=True)
    # These adjusted archived bars must not be adjusted a second time.
    native=~pd.MultiIndex.from_frame(prices[['date','symbol']]).isin(keys)
    factor=prices.adj_close.where(prices.adj_close.notna(),prices.close)/prices.close
    prices.loc[native,['open','high','low','close']]=prices.loc[native,['open','high','low','close']].mul(factor[native],axis=0)
    prices['instrument_id']=prices.instrument_id.astype('string')
    # Scoring uses current SQL feature history, not the overlaid replay OHLC.
    # Record this limitation rather than passing repaired features off as identical.
    atomic_json(root/'correction-audit.json',dict(overlay_symbols=sorted(affected),
        source=str(repairs),source_manifest_sha256=digest(repairs/'prepared.json'),
        feature_replay_price_parity_certified=False,
        limitation='Current SQL features; qualified replay corrections are retrospective and may differ'))
    prices.to_parquet(root/'prices.parquet',index=False)
    scores.to_parquet(root/'scores.parquet',index=False)
    features.to_parquet(root/'features.parquet',index=False)
    verify_hashes(Path('.'),frozen['model_files'])
    names=['prices.parquet','scores.parquet','features.parquet','macro.parquet','correction-audit.json']
    atomic_json(root/'ready.json',dict(files={n:digest(root/n) for n in names},
        rows=len(scores),sessions=int(scores.date.nunique()),symbols=int(scores.symbol.nunique())))
    atomic_json(root/'progress.json',dict(status='READY_BASELINE',rows=len(scores)))


def annual_metrics(result,trades,daily,year):
    # Partial legs before/after a qualified ticker change belong to one entry.
    if len(trades):
        trades=trades.copy()
        trades['entry_identity']=trades['entry_symbol'].where(trades.entry_symbol.notna(),trades.symbol) \
            if 'entry_symbol' in trades else trades.symbol
        grouped=trades.groupby(['entry_identity','entry_date']).pnl.sum()
    else:grouped=pd.Series(dtype=float)
    winners,losers=grouped[grouped>0],grouped[grouped<0]
    n=len(grouped)
    cutoff=pd.Timestamp(f'{year}-12-31' if year!=2026 else END)
    marked=daily.loc[pd.to_datetime(daily.date).le(cutoff)] if 'date' in daily else pd.DataFrame()
    return dict(initial_capital_usd=4000.,final_capital_usd=float(daily.equity.iloc[-1]),
        net_pnl_usd=float(daily.equity.iloc[-1]-4000), winning_amount_usd=float(winners.sum()),
        losing_amount_usd=float(losers.sum()),closed_positions=n,winning_positions=len(winners),
        losing_positions=len(losers),flat_positions=int(grouped.eq(0).sum()),
        winning_pct=100*len(winners)/n if n else None,losing_pct=100*len(losers)/n if n else None,
        return_pct=100*result['return_pct'],max_drawdown_pct=100*result['max_drawdown'],
        profit_factor=float(winners.sum()/-losers.sum()) if len(losers) else None,
        margin_interest_usd=result['margin_interest'],cash_reconciliation_error=result['cash_reconciliation_error'],
        calendar_mark_to_market_capital=float(marked.equity.iloc[-1]) if len(marked) else None,
        pnl_scope='position PnL after canonical costs; account net also subtracts margin interest')


def run_case(root,year,count,*,experiment='BASELINE',scores_override=None,
             ledger_factory=None,session_factory=None,daily_exit_policy=None):
    root=Path(root)
    verify_hashes(root,read(root/'ready.json')['files'])
    output=root/experiment/f'{year}-TOP{count}'
    output.mkdir(parents=True,exist_ok=True)
    marker=output/'case-report.json'
    if marker.exists() and read(marker)['status']=='COMPLETED_EXPLORATORY':
        saved=read(marker)
        verify_hashes(output,saved['files'])
        return saved
    scores=pd.read_parquet(root/'scores.parquet') if scores_override is None else scores_override
    candidates=freeze_candidates(scores.loc[scores.date.dt.year.eq(year)],count,'NEW_BARRIER_LONG')
    # Experiment filters are applied after ranking; never replace rejected candidates.
    if 'entry_allowed' in scores:
        flags=scores[['date','symbol','entry_allowed']]
        candidates=candidates.merge(flags,on=['date','symbol'],validate='one_to_one')
        candidates['selected']=candidates.entry_allowed.fillna(False).astype(bool)
    prices=pd.read_parquet(root/'prices.parquet')
    required=set(candidates.symbol)|{'SPY','VMRK'}
    from scripts.research.us_oracle_tp20_sl10_lifecycle import load_events
    events=load_events(root)
    sectors=pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict()
    sectors['VMRK']=sectors['EQR']
    for event_ in events:
        if event_['source'] in required:
            required.add(event_['target'])
            if event_.get('event_type') == 'NAME_CHANGE':
                sectors[event_['target']]=sectors[event_['source']]
    subset=prices.loc[prices.symbol.isin(required)]
    if required-{'SPY'}-set(sectors):
        raise ValueError(f'Missing candidate sectors {required-set(sectors)}')
    calendar=nyse_sessions(pd.Timestamp('2023-01-01').date(),pd.Timestamp(AS_OF).date())
    final=calendar[calendar<=pd.Timestamp(f'{year}-12-31' if year!=2026 else END)][-1]
    end=calendar[calendar.get_loc(final)+21]
    frames={key:subset.pivot(index='date',columns='symbol',values=col).reindex(calendar)
        for key,col in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    kwargs={}
    if session_factory is not None:kwargs['session_factory']=session_factory
    if daily_exit_policy is not None:kwargs['daily_exit_policy']=daily_exit_policy
    try:
        result=run_portfolio(frames=frames,scores=candidates,sectors=sectors,
            macro=ArchivedMacro(pd.read_parquet(root/'macro.parquet')),
            market_config=parse_market_regimes(load_config().get('market_regimes')),
            policy='selected',variant='CURRENT_NO_EXPIRY',output=output,
            start_date=f'{year}-01-01',end_date=str(end.date()),decision_end_date=str(final.date()),
            quality=subset[['date','symbol','is_filled','instrument_id']],
            ledger_factory=ledger_factory or partial(GridLedger,tp_pct=.2,sl_pct=.1,cash_policy='STRICT',events=events),
            expiry_open_sessions=20,protection_options=dict(take_profit_enabled=True,trailing_enabled=False),**kwargs)
        trades=pd.read_parquet(output/'trades.parquet')
        audit=verify_trade_contract(trades,.2,.1,calendar) if experiment!='PERSONAL_TP_SL' else {}
        if not result.get('account_wealth_complete',True):
            raise ValueError('Unvalued corporate-action receivable; not a completed economic result')
        result.update(status='COMPLETED_EXPLORATORY',year=year,count=count,experiment=experiment,
            annual_metrics=annual_metrics(result,trades,pd.read_parquet(output/'daily.parquet'),year),
            protection_audit=audit,files={p.name:digest(p) for p in output.glob('*.parquet')},
            baseline_model=read(root/'protocol.json')['batch_id'])
    except Exception as exc:
        result=dict(status='FAILED',year=year,count=count,experiment=experiment,
                    error_type=type(exc).__name__,error=str(exc))
    atomic_json(marker,result)
    return result


def baseline(root):
    root=Path(root)
    manifest_path=root/'baseline-source-manifest.json'
    if manifest_path.exists():verify_hashes(Path('.'),read(manifest_path)['files'])
    else:atomic_json(manifest_path,dict(files={p:h for p,h in code_hashes().items()
        if not p.endswith('us_oracle_tp20_sl10_models.py')}))
    reports=[]
    for year in YEARS:
        annual=[]
        for count in COUNTS:
            atomic_json(root/'progress.json',dict(status='RUNNING',phase='baseline',year=year,count=count,
                completed_runs=len(reports),total_runs=9))
            result=run_case(root,year,count)
            reports.append(result);annual.append(result)
            atomic_json(root/f'baseline-{year}.json',dict(year=year,portfolios=annual))
            LOG.info('Baseline %s TOP%s: %s',year,count,result['status'])
        # No suppression of one failed variant to start fitting the experiments.
    failed=[r for r in reports if r['status']=='FAILED']
    atomic_json(root/'baseline-report.json',dict(status='FAILED' if failed else 'COMPLETED_EXPLORATORY',
        portfolios=reports,failed=len(failed),completed=len(reports)-len(failed)))
    lines=['# Baseline LONG TP20 / SL10, sans trailing','',
        '| Année | TOP | Capital final $ | Gains $ | Pertes $ | Gagnants % | Perdants % | Rendement % | DD max % |',
        '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in reports:
        if r['status']=='FAILED':
            lines.append(f"| {r['year']} | {r['count']} | FAILED : {r['error']} | | | | | | |")
        else:
            m=r['annual_metrics']
            vals=[m[k] for k in ('final_capital_usd','winning_amount_usd','losing_amount_usd','winning_pct',
                'losing_pct','return_pct','max_drawdown_pct')]
            lines.append(f"| {r['year']} | {r['count']} | "+' | '.join(f'{v:.2f}' if v is not None else '—' for v in vals)+' |')
    # Generated research report, not source editing.
    (root/'baseline-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if failed:raise RuntimeError(f'{len(failed)} baseline portfolios failed; experiments not started')
    verify_hashes(Path('.'),read(manifest_path)['files'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model',type=Path,default=MODEL)
    p.add_argument('--phase',choices=('prepare','baseline','experiments','all'),default='all')
    args=p.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        if args.phase in ('prepare','all'):prepare(args.output,args.model)
        if args.phase in ('baseline','all'):baseline(args.output)
        if args.phase in ('experiments','all'):
            from scripts.research.us_oracle_tp20_sl10_models import experiments
            experiments(args.output,args.model)
        atomic_json(args.output/'progress.json',dict(status='COMPLETED',phase=args.phase))
    except Exception as exc:
        atomic_json(args.output/'progress.json',dict(status='FAILED',phase=args.phase,
            error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
