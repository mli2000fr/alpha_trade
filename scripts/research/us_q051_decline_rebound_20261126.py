"""Matched frozen Q051 TOP10: prior decline followed by daily-close recovery.

No new models, SQL, provider/LLM calls or production settings. The original
15,237.79 USD witness must be reproduced before interpreting the variants.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
import json
import logging
from multiprocessing import get_context
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests

from scripts.research import us_q051_classic_top10_20261115 as classic
from scripts.research.us_q051_vol20_regime_h5_20261115 import market_data, EXT, shared
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT = Path('artifacts/research/us_q051_decline_rebound/20261126-v2')
BASE = classic.ROOT/'cases/TOP10'
CASES = {
    'REFERENCE': 'Q051 témoin — TOP10',
    'DECLINE_ONLY': 'Baisse préalable seule',
    'REBOUND_1': 'Baisse puis une clôture en hausse',
    'REBOUND_2': 'Baisse puis deux clôtures en hausse',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def pattern_features(close):
    """At close J: decline J-22→J-2, recovery J-1/J. No forward fill."""
    if close.index.has_duplicates or close.columns.has_duplicates or not close.index.is_monotonic_increasing:
        raise ValueError('Prix journaliers dupliqués ou non ordonnés')
    c = close.where(np.isfinite(close) & close.gt(0))
    valid = c.notna().rolling(23, min_periods=23).sum().eq(23)
    decline = c.shift(2)/c.shift(22)-1
    up1 = c.shift(1).gt(c.shift(2))
    up2 = c.gt(c.shift(1))
    return dict(history_qualified=valid, prior_return_20=decline,
                rise_j_minus_1=up1, rise_j=up2,
                decline_qualified=valid & decline.le(-.10+1e-12))


def screen(signals, close):
    features = pattern_features(close)
    if signals.duplicated(['trade_date','symbol']).any():
        raise ValueError('Signaux TOP10 dupliqués')
    out = signals.copy()
    days = pd.DatetimeIndex(pd.to_datetime(out.trade_date))
    rows = close.index.get_indexer(days)
    columns = close.columns.get_indexer(out.symbol)
    if (rows<0).any() or (columns<0).any():
        raise ValueError('Signal hors des archives journalières de référence')
    for name, frame in features.items():
        out[name] = frame.to_numpy()[rows,columns]
    out['REFERENCE'] = True
    out['DECLINE_ONLY'] = out.decline_qualified
    out['REBOUND_1'] = out.decline_qualified & out.rise_j
    out['REBOUND_2'] = out.decline_qualified & out.rise_j_minus_1 & out.rise_j
    return out


def configuration():
    cfg = shared.configuration(read(shared.ROOT/'protocol.json')['reference'], shared.CASES['Q051_050'])
    # New PAPER-only time-in-force defaults did not exist in the old replay.
    # They are unused by the replay (which has no broker order submission).
    expected = read(BASE/'result/configuration.json')['portfolio']
    snapshot = json.loads(json.dumps(asdict(cfg),default=str))
    for name in ('paper_entry_time_in_force','paper_exit_time_in_force'):
        if name not in expected['exec_config']:snapshot['exec_config'].pop(name,None)
    if classic.meaningful(snapshot) != classic.meaningful(expected):
        raise ValueError('Configuration numérique différente du témoin TOP10 historique')
    return cfg


def prepare():
    ROOT.mkdir(parents=True,exist_ok=False)
    inputs=ROOT/'inputs';inputs.mkdir()
    cfg=configuration()
    old=read(classic.ROOT/'validation-independent.json')
    if old['status']!='PASS':raise ValueError('Référence non validée')
    protocol=read(BASE/'protocol.json')
    sources={p:digest(Path(p)) for p in protocol['sources']}
    for p in (Path(__file__),BASE/'result/report.json',BASE/'result/configuration.json',
              BASE/'result/equity-daily.csv',classic.ROOT/'validation-independent.json'):
        sources[str(p)]=digest(p)
    signals_path=classic.SELECTION/'inputs/signals-TOP10_SCORE050.parquet'
    sources[str(signals_path)]=digest(signals_path)
    signals=pd.read_parquet(signals_path)
    if len(signals)!=9890:raise ValueError('9890 sélections TOP10 attendues')
    pivots,sectors,actions=market_data()
    marked=screen(signals,pivots['close'])
    marked.to_parquet(inputs/'candidate-audit.parquet',index=False)
    counts=[]
    for case in CASES:
        selected=marked.loc[marked[case],signals.columns].copy()
        selected.to_parquet(inputs/f'signals-{case}.parquet',index=False)
        for year in range(2021,2027):
            # Annual comparison follows the entry year frozen in the original
            # scores, not the civil year of the preceding signal day.
            part=marked[marked.entry_year.eq(year)]
            kept=part[part[case]]
            counts.append(dict(case=case,year=year,candidates=len(part),signals=len(kept),
                symbols=int(kept.symbol.nunique()),missing_history=int((~part.history_qualified).sum())))
    for name,frame in pivots.items():frame.to_parquet(inputs/(name+'.parquet'))
    sectors.to_parquet(inputs/'sectors.parquet',index=False)
    actions.to_parquet(inputs/'actions.parquet',index=False)
    pd.DataFrame(counts).to_csv(ROOT/'selection-counts.csv',index=False)
    market_hashes={}
    for base in (shared.ROOT,EXT):
        manifest=base/'inputs/manifest.json';sources[str(manifest)]=digest(manifest)
        files=read(manifest)['files']
        for i,(relative,checksum) in enumerate(files.items()):
            path=base/'inputs'/relative
            if digest(path)!=checksum:raise ValueError('Prix archivés modifiés : '+str(path))
            market_hashes[str(path)]=checksum
            if i%100==0:atomic_json(ROOT/'progress.json',dict(status='VERIFYING_FROZEN_MARKET',completed=i,total=len(files)))
    files={str(p):digest(p) for p in inputs.iterdir() if p.is_file()}
    sources.update(files)
    plan=dict(start='2021-01-01',end='2026-10-01',initial_equity=4000.,annual_reset=False,
        reference=protocol['reference'],annual_models=protocol['annual_models'],cases=CASES,
        frozen_pattern=dict(primary='REBOUND_2',lookback_sessions=20,decline_threshold=-.10,
            decline_end='J-2',decline_start='J-22',confirmation_closes=['J-1>J-2','J>J-1'],
            observation='clôture J',entry='ouverture J+1',refill=False),
        original_signal_count=len(signals),sources=sources,market_files=market_hashes,
        baseline_root=str(BASE),configuration=asdict(cfg),provider_calls=0,SQL_writes=0,orders=0,
        ignored_archive_fields=['exec_config.paper_entry_time_in_force','exec_config.paper_exit_time_in_force'],
        training=False,new_inference=False,production_changes=False,
        limitations='Période déjà étudiée ; univers rétrospectif ; archives 5m partielles/repli OHLC hérité.',
        prepared_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'progress.json',dict(status='READY',cases=list(CASES),
        selection_counts={c:int(marked[c].sum()) for c in CASES}))


def run_case(case):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    plan=read(ROOT/'protocol.json')
    folder=ROOT/'cases'/case;folder.mkdir(parents=True,exist_ok=False)
    out=folder/'result';out.mkdir()
    try:
        for name,checksum in plan['sources'].items():
            if digest(Path(name))!=checksum:raise ValueError('Source figée modifiée : '+name)
        cfg=configuration()
        atomic_json(folder/'protocol.json',{**plan,'case':case})
        atomic_json(out/'configuration.json',dict(profile=case,portfolio=asdict(cfg)))
        atomic_json(folder/'progress.json',dict(status='LOADING_MARKET_INPUTS'))
        inputs=ROOT/'inputs'
        pivots={k:pd.read_parquet(inputs/(k+'.parquet')) for k in ('open','high','low','close','volume')}
        sectors=pd.read_parquet(inputs/'sectors.parquet');actions=pd.read_parquet(inputs/'actions.parquet')
        signals=pd.read_parquet(inputs/f'signals-{case}.parquet')
        class VerifiedPrices(ExtendedPrices):
            @lru_cache(maxsize=6)
            def day(self,day):
                for file in (shared.ROOT/'inputs/base/intraday'/f'{day}.parquet',
                             shared.ROOT/'inputs/extra-intraday'/f'{day}.parquet',
                             EXT/'inputs/intraday'/f'{day}.parquet'):
                    if digest(file)!=plan['market_files'].get(str(file)):
                        raise ValueError('Archive intraday modifiée : '+str(file))
                return super().day(day)
        def no_http(*args,**kwargs):raise ValueError('Réseau interdit dans ce replay figé')
        with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
            def progress(done,total,day):
                atomic_json(folder/'progress.json',dict(status='REPLAYING',completed=done,total=total,last_date=str(day),case=case))
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=VerifiedPrices(EXT),winner_research_assumptions=True,winner_progress=progress,
                winner_corporate_actions=actions.to_dict('records'))
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False)
            result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            report=metrics(result,4000.);annual=[];opening=4000.
            for year in range(2021,2027):
                curve=result.equity_curve[result.equity_curve.index.year==year]
                trades=result.closed_trades_df;marks=result.intraday_equity_curve
                part=BacktestResult(equity_curve=curve,
                    closed_trades_df=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)],
                    intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row.update(year=year,model=plan['annual_models'][str(year)]['batch_id'])
                annual.append(row);opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case=case,selected_signals=len(signals),annual_reset=False,provider_calls=0,SQL_writes=0,orders=0,
                annual_models=plan['annual_models'],model_timing_oos=True,strict_pit=False,
                finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(out/'report.json',report)
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        return dict(case=case,final_equity=report['final_equity'],max_drawdown_pct=report['max_drawdown_pct'])
    except BaseException as exc:
        atomic_json(folder/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


def finalize():
    from scripts.research.report_q051_selection_variants_20261115 import fr
    from ihm.services.backtesting_import import import_continuous_winner
    original=read(BASE/'result/report.json');control=read(ROOT/'cases/REFERENCE/result/report.json')
    old_curve=pd.read_csv(BASE/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
    new_curve=pd.read_csv(ROOT/'cases/REFERENCE/result/equity-daily.csv',index_col=0,parse_dates=True).equity
    keys=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','costs','average_gross_capital']
    differences={k:[original[k],control[k]] for k in keys if not np.isclose(original[k],control[k],rtol=1e-10,atol=1e-6)}
    match=old_curve.index.equals(new_curve.index) and np.allclose(old_curve,new_curve,rtol=1e-10,atol=1e-6)
    atomic_json(ROOT/'baseline-reproduction.json',dict(status='PASS' if not differences and match else 'DIFFERENT',
        differences=differences,every_daily_equity_equal=bool(match)))
    if differences or not match:raise ValueError('Témoin historique non reproduit : diagnostic requis avant comparaison')
    plan=read(ROOT/'protocol.json');audit=pd.read_parquet(ROOT/'inputs/candidate-audit.parquet')
    selected=pd.read_parquet(ROOT/'inputs/signals-REFERENCE.parquet')
    close=pd.read_parquet(ROOT/'inputs/close.parquet')
    independent=screen(selected,close)
    for key in ['history_qualified','prior_return_20','rise_j_minus_1','rise_j','decline_qualified',*CASES]:
        if not independent[key].equals(audit[key]):raise ValueError('Filtre non reproductible : '+key)
    rows=[];annual=[];curves=[]
    for case,label in CASES.items():
        folder=ROOT/'cases'/case;out=folder/'result';r=read(out/'report.json')
        t=pd.read_csv(out/'trades.csv');m=pd.read_parquet(out/'equity-5m.parquet')
        e=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
        expected=t.qty*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends
        if not np.allclose(expected,t.pnl,rtol=1e-10,atol=1e-7):raise ValueError('PnL non réconcilié')
        if not np.isclose(r['settled_cash']+r['unsettled_cash']+r['gross'],r['final_equity'],atol=1e-7):
            raise ValueError('Capital non réconcilié')
        dd=100*(pd.concat([pd.Series([4000.]),m.equity],ignore_index=True).pipe(lambda v:v/v.cummax()-1)).min()
        if not np.isclose(dd,r['max_drawdown_pct'],atol=1e-7):raise ValueError('DD non réconcilié')
        s=pd.read_parquet(ROOT/'inputs'/f'signals-{case}.parquet')
        if not s[['trade_date','symbol','rank']].reset_index(drop=True).equals(audit.loc[audit[case],['trade_date','symbol','rank']].reset_index(drop=True)):
            raise ValueError('Sélection/remplissage différent du filtre figé')
        wins=t[t.pnl.gt(0)];losses=t[t.pnl.lt(0)]
        row={k:r[k] for k in keys+['win_pct','average_winning_pnl','average_losing_pnl','average_gross_equity_ratio',
            'maximum_gross_capital','margin_interest','selected_signals']}
        row.update(case=case,label=label,profit_factor=float(wins.pnl.sum()/-losses.pnl.sum()) if len(losses) else None,
            winning_holding_calendar_days=float(wins.holding_days.mean()),losing_holding_calendar_days=float(losses.holding_days.mean()),
            symbols=int(t.symbol.nunique()),stop_exits=int(t.exit_reason.str.contains('STOP',case=False).sum()),
            open_positions_final=len(r.get('open_positions',[])))
        rows.append(row);curves.append(e.rename(case))
        a=pd.read_csv(out/'annual-summary.csv');a['case']=case;annual.append(a)
        record=import_continuous_winner(folder,run_id='20261126_q051_rebound_'+case.lower(),
            label=label+' — baisse20j/10% — 2021–2026',result_subdir='result')
        atomic_json(folder/'ihm.json',dict(run_id=record['run_id']))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.concat(curves,axis=1).to_csv(ROOT/'capital-curves.csv')
    atomic_json(ROOT/'comparison.json',dict(cases=rows))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,(ax,ddax)=plt.subplots(2,1,sharex=True,figsize=(13,8),gridspec_kw={'height_ratios':[2,1]})
    for case,label,color in zip(CASES,CASES.values(),['#2455cc','#999999','#e8851c','#138b6c']):
        e=pd.read_csv(ROOT/'cases'/case/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
        r=next(r for r in rows if r['case']==case)
        ax.plot(e.index,e,color=color,label=label+f" : {r['return_pct']:+.2f} %")
        ddax.plot(e.index,100*(e/e.cummax().clip(lower=4000.)-1),color=color)
    ax.set_title('Q051 TOP10 — baisse préalable puis début de reprise')
    ax.set_ylabel('Capital ($), départ 4 000');ax.legend(fontsize=9);ax.grid(alpha=.2)
    ddax.set_ylabel('DD aux clôtures (%)');ddax.grid(alpha=.2)
    fig.text(.07,.01,'2021–1 octobre 2026. SL5/open11, frais inclus, achat J+1. Aucun remplacement après filtre.\nRésultats exploratoires : univers rétrospectif, intraday partiel/repli OHLC ; DD du tableau mesuré en intraday.',fontsize=9)
    fig.tight_layout(rect=(0,.055,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=150);plt.close(fig)
    table=['| Variante | Capital final | Rendement | DD max intraday | Trades | Gagnants | Capital engagé moyen |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        table.append('| '+r['label']+' | '+fr(r['final_equity'])+' $ | '+fr(r['return_pct'],percent=True)+' | '+
            fr(r['max_drawdown_pct'],percent=True)+' | '+str(r['closed_lot_trades'])+' | '+fr(r['win_pct'],percent=True)+' | '+fr(r['average_gross_capital'])+' $ |')
    (ROOT/'results.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
    atomic_json(ROOT/'validation.json',dict(status='PASS',baseline_exact=True,all_1443_daily_closes_equal=True,
        filters_reproduced=True,accounting_and_drawdowns_checked=True,review='same assistant; no independent human review'))
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',validation='PASS',completed=4,total=4))
    print(json.dumps(rows,ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['prepare','case','finalize','all'],required=True)
    parser.add_argument('--case',choices=list(CASES));parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args();logging.basicConfig(level=logging.WARNING)
    if args.phase in ('prepare','all'):prepare()
    if args.phase=='case':run_case(args.case)
    if args.phase=='all':
        with ProcessPoolExecutor(max_workers=args.workers,mp_context=get_context('spawn')) as pool:
            futures={pool.submit(run_case,case):case for case in CASES}
            for count,future in enumerate(as_completed(futures),1):
                print(json.dumps(future.result()),flush=True)
                atomic_json(ROOT/'progress.json',dict(status='REPLAYING',completed=count,total=4,last=futures[future]))
    if args.phase in ('finalize','all'):finalize()


if __name__=='__main__':main()
