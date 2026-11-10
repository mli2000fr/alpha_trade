"""Validate completed replay after a false in-memory-vs-CSV float rejection.

No replay/order/SQL/provider calls. Recompute metrics from the actual exported
artifacts; retain runtime metadata only after proving identical event outputs.
"""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
import shutil

from scripts.research import us_q051_range_support_a2_20261109 as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def run():
    from backtesting.simulator import BacktestResult
    from backtesting.winner_campaign_replay import metrics
    from scripts.research.us_winner_q051_risk_budget_20261109 import daily_metrics
    root=pilot.ROOT;folder=root/'cases/BASELINE_ALL';out=folder/'result';old=pilot.CONTROL
    source=pilot.read(root/'request.json')['source_hashes']
    saved=root/'source-before-validator-fix.py'
    expected=next(v for k,v in source.items() if Path(k).resolve()==Path(pilot.__file__).resolve())
    if digest(saved)!=expected:raise ValueError('Original executed source snapshot mismatch')
    identical={}
    for name in ['equity-daily.csv','equity-5m.parquet','trades.csv','events.csv','risk-5m.csv','portfolio-risk-decisions.csv']:
        if digest(out/name)!=digest(old/name):raise ValueError('Replay reference artifact differs: '+name)
        identical[name]=digest(out/name)
    if pilot.read(out/'configuration.json')['portfolio']!=pilot.read(old/'configuration.json')['portfolio']:
        raise ValueError('Portfolio configuration differs')
    new_gate=pd.read_csv(out/'regime-decisions.csv',float_precision='round_trip')
    old_gate=pd.read_csv(old/'regime-decisions.csv',float_precision='round_trip').rename(columns={'sma200':'sma'})
    pd.testing.assert_frame_equal(new_gate,old_gate[new_gate.columns],check_exact=True)
    original=pilot.read(old/'report.json')
    daily=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True,float_precision='round_trip').iloc[:,0]
    trades=pd.read_csv(out/'trades.csv',float_precision='round_trip');marks=pd.read_parquet(out/'equity-5m.parquet')
    # Metadata is explicitly inherited from the reference only after proving
    # identical configurations, fills, financing, protection events and risk.
    meta=deepcopy(original)
    result=BacktestResult(equity_curve=daily,closed_trades_df=trades,intraday_equity_curve=marks,
        tracker_snapshot={'winner_replay':meta})
    report=metrics(result,4000.);report.update(daily_metrics(daily))
    for key in ['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','win_pct',
        'average_gross_capital','maximum_gross_capital']:
        if not np.isclose(report[key],original[key],atol=1e-10,rtol=0):raise ValueError('Recomputed metric mismatch: '+key)
    for row in pd.read_csv(out/'annual-summary.csv').to_dict('records'):
        selected=trades[pd.to_datetime(trades.exit_date,utc=True).dt.year.eq(row['year'])]
        assert len(selected)==row['closed_lot_trades'] and int(selected.pnl.gt(0).sum())==row['winners']
    report.update(profile='BASELINE_ALL',case='BASELINE_ALL',reference_reproduction='BYTE_IDENTICAL_CURVES_TRADES_EVENTS_RISK',
        finished_at_utc=datetime.now(timezone.utc).isoformat(),
        postvalidation=dict(reason='CSV parser ULP difference in strict in-memory comparison, not a changed replay',
            replay_restarted=False,metrics_recomputed_from_exported_results=True,
            runtime_metadata_inherited_from_verified_identical_reference=str(old),
            executed_source_snapshot_sha256=digest(saved),validator_source_sha256=digest(Path(__file__))))
    proof=dict(status='PASS',files_byte_identical=identical,regime_decisions='IDENTICAL_AFTER_COLUMN_RENAME',
        native_portfolio_configuration='IDENTICAL',annual_trade_counts='PASS',replay_restarted=False,
        original_source_sha256=digest(saved),fixed_research_runner_sha256=digest(Path(pilot.__file__)))
    # Keep the original FAILED isolation receipt intact. Publish a separate
    # export only after a new isolated validation completes without violations.
    from backtesting.isolation import ReadOnlyReplay
    published=root/'reference-postvalidated';published.mkdir(exist_ok=False)
    target=published/'result';target.mkdir()
    shutil.copyfile(folder/'protocol.json',published/'protocol.json')
    shutil.copyfile(folder/'isolation.json',published/'original-replay-isolation.json')
    for file in out.iterdir():
        if file.is_file() and file.name!='report.json':shutil.copyfile(file,target/file.name)
    with ReadOnlyReplay(published).install():
        for name,sha in identical.items():
            if digest(target/name)!=sha:raise ValueError('Export artifact changed: '+name)
        proof.update(original_failed_isolation_receipt_preserved=True,original_replay_folder=str(folder),
            publication_kind='POSTVALIDATED_IDENTICAL_REPLAY_OUTPUTS_NO_SIMULATION_RERUN')
        atomic_json(target/'report.json',report)
        atomic_json(published/'validation.json',proof)
        atomic_json(published/'progress.json',dict(status='COMPLETED_EXPLORATORY'))
    from ihm.services.backtesting_import import import_continuous_winner
    record=import_continuous_winner(published,run_id='20261109_a2_baseline_all_v1',
        label='Q051 vol20/régime — témoin reproduit pour pilote A2',result_subdir='result')
    atomic_json(published/'progress.json',dict(status='COMPLETED_EXPLORATORY',ihm_run_id=record['run_id']))
    active=Path('artifacts/research/us_q051_range_support_a2/20261109-v2')
    validation=pilot.read(active/'validation.json');validation.update(reference_status='PASS_BYTE_IDENTICAL',reference_validation=str(published/'validation.json'))
    atomic_json(active/'validation.json',validation)
    final=pilot.read(active/'report.json');final.update(reference_reproduction=dict(status='PASS_BYTE_IDENTICAL',
        final_equity=report['final_equity'],return_pct=report['return_pct'],max_drawdown_pct=report['max_drawdown_pct'],
        closed_trades=report['closed_lot_trades'],ihm_run_id=record['run_id']),connection_tests=109,production_changes=False)
    atomic_json(active/'report.json',final);atomic_json(active/'progress.json',final)
    print({k:report[k] for k in ['final_equity','return_pct','max_drawdown_pct','win_pct','reference_reproduction']})


if __name__=='__main__':run()
