"""Matched five-session-exit counterfactual of the sealed causal Q051 vol20 witness.

Replays every original candidate and capital path; never truncate only old trades.
Frozen inputs, no inference, SQL, provider, broker or production-setting writes.
"""
from copy import deepcopy
from dataclasses import asdict,replace
from datetime import datetime,timezone
import json
import logging
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import requests
from scripts.research import us_winner_continuous_q051_q088_20261108 as shared
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_vol20_regime_h5/20261115-v1')
WITNESS=Path('artifacts/research/us_q051_global_rank_h10/20261115-v1/cases/Q051_REFERENCE')
GLOBAL_ARCHIVE=WITNESS.parent.parent
EXT=Path('artifacts/research/us_winner_vol20_extensions/20261109-v1')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def configuration():
    from backtesting.risk_overlay import RegimeFilterConfig
    base=read(shared.ROOT/'protocol.json')
    cfg=shared.configuration(base['reference'],shared.CASES['Q051_050'])
    cfg.risk_overlay.regime_filter=RegimeFilterConfig(enabled=True,sma_window=200,bear_threshold=-.02)
    before=json.loads(json.dumps(asdict(cfg),default=str))
    if before!=read(WITNESS/'result/configuration.json')['portfolio']:raise ValueError('Reference configuration differs')
    cfg.exec_config=replace(cfg.exec_config,winner_pyramiding=replace(cfg.exec_config.winner_pyramiding,horizon_sessions=5))
    expected=deepcopy(before);expected['exec_config']['winner_pyramiding']['horizon_sessions']=5
    if json.loads(json.dumps(asdict(cfg),default=str))!=expected:raise ValueError('Difference outside horizon_sessions')
    return cfg


def market_data():
    pivots,sectors,actions=shared.market_data(shared.ROOT)
    extra=pd.read_parquet(EXT/'inputs/daily.parquet')
    for name in pivots:
        p=extra.pivot(index='date',columns='symbol',values=name)
        if set(p)&set(pivots[name]):raise ValueError('Market supplement would overwrite original prices')
        pivots[name]=pd.concat([pivots[name],p],axis=1).sort_index()
    sectors=pd.concat([sectors,pd.read_parquet(EXT/'inputs/sectors.parquet')],ignore_index=True)
    actions=pd.concat([actions,pd.read_parquet(EXT/'inputs/actions.parquet')],ignore_index=True)
    if sectors.symbol.duplicated().any():raise ValueError('Duplicate sector snapshot')
    return pivots,sectors,actions


def compare(root):
    from math import prod
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[];annual=[];fig,ax=plt.subplots(figsize=(12,6))
    cols=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','winners','losers',
          'average_winning_pnl','average_losing_pnl','average_gross_capital','average_gross_equity_ratio','costs','margin_interest']
    for label,folder in [('H10 — open11',WITNESS),('H5 — open6',root)]:
        r=read(folder/'result/report.json')
        curve=pd.read_csv(folder/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
        a=pd.read_csv(folder/'result/annual-summary.csv');a['variant']=label;annual.append(a)
        if not np.isclose(4000*prod(1+a.return_pct/100),r['final_equity'],atol=1e-6):raise ValueError('Annual compounding mismatch')
        if not np.isclose(curve.iloc[-1],r['final_equity'],atol=1e-7):raise ValueError('Final marked capital mismatch')
        rows.append(dict(variant=label,**{c:r[c] for c in cols}))
        ax.plot(curve.index,curve,label=label)
    pd.DataFrame(rows).to_csv(root/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(root/'annual-comparison.csv',index=False)
    ax.set_title('Q051 volatilité 20 % + régime — sortie H5 contre H10')
    ax.set_ylabel('Capital valorisé ($), départ 4 000');ax.grid(alpha=.2);ax.legend()
    fig.text(.06,.01,'2021 au 1 octobre 2026. SL5, sans TP/trailing. Frais inclus ; couverture 5m partielle, repli OHLC conservateur.',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(root/'capital-comparison.png',dpi=140);plt.close(fig)
    return rows


def run(root=ROOT):
    from backtesting.simulator import BacktestEngine,BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from backtesting.winner_portfolio_budget import replay_protections
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    root=Path(root);root.mkdir(parents=True,exist_ok=False);out=root/'result';out.mkdir()
    try:
        cfg=configuration();witness=read(WITNESS/'protocol.json')
        frozen=read(GLOBAL_ARCHIVE/'request.json')
        for file,sha in frozen['sources'].items():
            if digest(Path(file))!=sha:raise ValueError('Reference source changed: '+file)
        validation=read(GLOBAL_ARCHIVE/'validation.json')
        if validation['status']!='PASS' or read(GLOBAL_ARCHIVE/'economic-baseline-validation.json')['status']!='PASS':
            raise ValueError('Reference not validated')
        reference=deepcopy(witness['reference']);reference.pop('global_ranking_comparison',None)
        reference['winner_policy']=asdict(cfg.exec_config.winner_pyramiding)
        reference['risk']=asdict(cfg.risk_config);reference['drawdown_controller']={'enabled':False}
        reference['arguments']['horizon_sessions']=5
        reference['horizon_experiment']=dict(horizon_sessions=5,other_configuration='IDENTICAL_TO_SEALED_Q051_WITNESS')
        signals_path=GLOBAL_ARCHIVE/'inputs/signals-Q051_REFERENCE.parquet'
        signals=pd.read_parquet(signals_path)
        if len(signals)!=6073:raise ValueError('Reference signals changed')
        sources={str(Path(__file__)):digest(Path(__file__)),str(signals_path):digest(signals_path),
            str(WITNESS/'result/report.json'):digest(WITNESS/'result/report.json'),
            str(WITNESS/'result/configuration.json'):digest(WITNESS/'result/configuration.json')}
        protocol=dict(start=witness['start'],end=witness['end'],initial_equity=4000.,annual_reset=False,
            annual_models=witness['annual_models'],reference=reference,sources=sources,baseline_root=str(WITNESS),
            sole_change='exec_config.winner_pyramiding.horizon_sessions: 10 -> 5',
            selection='Unchanged TOP10% Oracle -> TOP5 per-symbol LONG -> score>.50 and calibration AUC>=.50, no refill',
            collision_policy='Native conservative STOP first if both SL/TP touch the same qualified 5m or fallback daily bar',
            capital='Full continuous replay, exits release capital and change subsequent position sizes/candidate admission',
            provider_calls=0,SQL_writes=0,orders=0,production_changes=False,
            replay_command=[sys.executable,'-X','utf8','-m','scripts.research.us_q051_vol20_regime_h5_20261115'])
        atomic_json(root/'protocol.json',protocol)
        atomic_json(out/'configuration.json',dict(profile='Q051_VOL20_REGIME_H5',portfolio=asdict(cfg)))
        atomic_json(root/'progress.json',dict(status='VERIFYING_FROZEN_MARKET_INPUTS'))
        for base in [shared.ROOT,EXT]:
            for relative,sha in read(base/'inputs/manifest.json')['files'].items():
                if digest(base/'inputs'/relative)!=sha:raise ValueError('Changed market input: '+relative)
        pivots,sectors,actions=market_data();budget,gate=replay_protections(pivots['close'],daily_entry=True,target=.20,regime=True)
        def no_http(*args,**kwargs):raise ValueError('HTTP forbidden in H5 counterfactual')
        with ReadOnlyReplay(root).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),patch.object(requests.Session,'request',no_http):
            def tick(done,total,day):
                state=dict(status='REPLAYING_H5',completed=done,total=total,last_date=str(day))
                atomic_json(root/'progress.json',state);atomic_json(out/'progress.json',state)
            result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                intraday_source=ExtendedPrices(EXT),winner_research_assumptions=True,winner_progress=tick,
                winner_corporate_actions=actions.to_dict('records'),winner_selection_source=gate,winner_entry_risk_policy=budget)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv');result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            pd.DataFrame(budget.receipts).to_csv(out/'portfolio-risk-decisions.csv',index=False)
            pd.DataFrame(gate.receipts).to_csv(out/'regime-decisions.csv',index=False)
            report=metrics(result,4000.);annual=[];opening=4000.
            for year in range(2021,2027):
                curve=result.equity_curve[result.equity_curve.index.year==year];trades=result.closed_trades_df;marks=result.intraday_equity_curve
                closed=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(year)] if len(trades) else trades
                part=BacktestResult(equity_curve=curve,closed_trades_df=closed,
                    intraday_equity_curve=marks[pd.to_datetime(marks.timestamp,utc=True).dt.year.eq(year)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                row=metrics(part,opening);row.update(year=year,model=witness['annual_models'][str(year)]['batch_id']);annual.append(row)
                opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case='Q051_VOL20_REGIME_H5',annual_models=witness['annual_models'],annual_reset=False,
                selected_signals=len(signals),sole_change=protocol['sole_change'],exit_reasons=result.closed_trades_df.exit_reason.value_counts().to_dict(),
                strict_pit=False,model_timing_oos=True,provider_calls=0,SQL_writes=0,orders=0,
                finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(out/'report.json',report);atomic_json(root/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
        rows=compare(root)
        from ihm.services.backtesting_import import import_continuous_winner
        record=import_continuous_winner(root,run_id='20261115_q051_vol20_regime_h5',
            label='Q051 vol20 + régime — H5 / SL5 / open6 — annuel 2021–2026',result_subdir='result')
        atomic_json(root/'ihm.json',dict(run_id=record['run_id']))
        atomic_json(root/'validation.json',dict(status='PASS',sole_configuration_delta='horizon_sessions',signals=len(signals),
            annual_compounding=True,history_import=record['run_id'],results=rows))
        print(json.dumps(dict(status='COMPLETED_EXPLORATORY',results=rows),ensure_ascii=False),flush=True)
    except BaseException as exc:
        atomic_json(root/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    run()
