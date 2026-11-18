"""Read completed local Global/Q051 experiment; validate lineage and accounting."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.q051_global_rank_selection import POLICIES


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_market(root):
    root=Path(root);plan=read(root/'request.json');checks=[]
    for key in ['reference_root','market_extension_root']:
        base=Path(plan[key]);manifest=base/'inputs/manifest.json';m=read(manifest)
        for relative,sha in m['files'].items():
            file=base/'inputs'/relative
            if digest(file)!=sha:raise ValueError('Changed frozen market input: '+str(file))
        checks.append(dict(root=str(base),manifest_sha256=digest(manifest),files_checked=len(m['files'])))
    result=dict(status='PASS',checks=checks,SQL_writes=0,provider_calls=0,orders=0)
    atomic_json(root/'market-validation.json',result)
    return result


def qualify_case_protocols(root):
    """Complete display/replay provenance, without changing numerical settings."""
    root=Path(root);changed=[]
    for policy in POLICIES:
        file=root/'cases'/policy/'protocol.json'
        if not file.exists():continue
        p=read(file)
        if (file.parent/'ihm.json').exists():continue
        if not (file.parent/'protocol-before-provenance-qualification.json').exists():
            atomic_json(file.parent/'protocol-before-provenance-qualification.json',p)
        p['replay_command']=[sys.executable,'-X','utf8','-m','scripts.research.us_q051_global_rank_h10_20261115',
            '--output-dir',str(root),'--phase','replay','--policy',policy]
        p['reference']['global_ranking_comparison']=dict(selection=policy,oracle_top_n=179,final_top_n=5,
            min_long_probability_strict=.5,min_long_auc_inclusive=.5,refill=False,
            global_model_receipts=str(root/'years'),model_timing_oos=True,strict_pit=False)
        p['reference']['per_symbol_selection']=dict(oracle_top_n=179,long_top_n=5,allow_long=True,allow_short=False,
            min_long_probability=.5,min_long_auc=.5)
        p['reference']['drawdown_controller']={'enabled':False}
        atomic_json(file,p);changed.append(policy)
    return dict(qualified=changed,numerical_settings_changed=False)


def validate(root):
    root=Path(root);plan=read(root/'request.json');annual=[];economics=[]
    market=read(root/'market-validation.json')
    if market['status']!='PASS':raise ValueError('Frozen market not validated')
    for check in market['checks']:
        if digest(Path(check['root'])/'inputs/manifest.json')!=check['manifest_sha256']:
            raise ValueError('Frozen market manifest changed')
    for year in range(2021,2027):
        folder=root/'years'/str(year);r=read(folder/'receipt.json')
        for name,sha in r['outputs'].items():
            if digest(folder/name)!=sha:raise ValueError('Changed model output: '+name)
        if not (pd.Timestamp(r['fit_label_available_max'])<pd.Timestamp(r['validation_start'])
            and pd.Timestamp(r['validation_label_available_max'])<=pd.Timestamp(r['model_available_date'])
            and pd.Timestamp(r['model_available_date'])<pd.Timestamp(r['first_signal'])):
            raise ValueError('Noncausal annual model')
        if r['parameters']!=plan['model']['parameters'] or r['features']!=plan['model']['features']:
            raise ValueError('Changed annual training configuration')
        f=pd.read_parquet(folder/'scores.parquet')
        if f.duplicated(['date','symbol']).any() or not f.global_rank_10.between(0,1).all():raise ValueError('Invalid score')
        if not f.global_model_sha256.eq(r['model_sha256']).all():raise ValueError('Wrong model lineage')
        if not f.date.gt(pd.to_datetime(f.global_model_available_date)).all():raise ValueError('Future model')
        expected=f.groupby('date').raw_global_score.rank(pct=True)
        if not np.allclose(f.global_rank_10,expected,rtol=0,atol=1e-12):raise ValueError('Imputed/non-genuine percentile')
        annual.append({k:r[k] for k in ['year','fit_rows','validation_rows','best_iteration','model_available_date','first_signal',
            'validation_daily_rank_ic_mean','oracle_pool_rows','oracle_pool_missing']})
    reference_configuration=None
    for policy in POLICIES:
        folder=root/'cases'/policy;report=read(folder/'result/report.json')
        isolation=read(folder/'isolation.json')
        if isolation['status']!='COMPLETED' or isolation.get('violations'):raise ValueError('Isolation not clean')
        if report['SQL_writes'] or report['provider_calls'] or report['orders']:raise ValueError('External side effects')
        config=read(folder/'result/configuration.json')['portfolio']
        if reference_configuration is None:reference_configuration=config
        elif config!=reference_configuration:raise ValueError('Protection configuration differs between sorters')
        signals=pd.read_parquet(root/'inputs'/f'signals-{policy}.parquet')
        if not (signals.long_probability.gt(.5).all() and signals.long_auc.ge(.5).all()
                and pd.to_datetime(signals.long_auc_available_date).lt(pd.to_datetime(signals.trade_date)).all()):
            raise ValueError('Selection gate not respected')
        if signals.groupby('trade_date').size().max()>5:raise ValueError('More than TOP5 selected')
        curve=pd.read_csv(folder/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
        trades=pd.read_csv(folder/'result/trades.csv');yearly=pd.read_csv(folder/'result/annual-summary.csv')
        if not np.isclose(curve.iloc[-1],report['final_equity'],atol=1e-7):raise ValueError('Final capital mismatch')
        if not np.isclose(100*(curve.iloc[-1]/4000-1),report['return_pct'],atol=1e-8):raise ValueError('Return mismatch')
        compounded=4000*np.prod(1+yearly.return_pct/100)
        if not np.isclose(compounded,curve.iloc[-1],atol=1e-6):raise ValueError('Annual compounding mismatch')
        if len(trades)!=report['closed_lot_trades'] or int(trades.pnl.gt(0).sum())!=report['winners']:
            raise ValueError('Closed trade count mismatch')
        if report['winners']+report['losers']+report['flat']!=len(trades):raise ValueError('Trade reconciliation mismatch')
        history_id=read(folder/'ihm.json')['run_id']
        history=read(Path('artifacts/ihm_backtesting_runs/run')/history_id/'artifacts/report.json')
        for exported,native in [('final_value','final_equity'),('total_return_pct','return_pct'),('win_rate_pct','win_pct')]:
            if not np.isclose(history['summary'][exported],report[native],rtol=1e-10,atol=1e-7):
                raise ValueError('IHM financial parity mismatch')
        if history['params']['drawdown_controller']['enabled'] is not False:raise ValueError('Wrong IHM controller disclosure')
        if history['params']['global_ranking_comparison']['selection']!=policy:raise ValueError('Wrong IHM selector disclosure')
        economics.append(dict(policy=policy,final_equity=report['final_equity'],return_pct=report['return_pct'],
            max_drawdown_pct=report['max_drawdown_pct'],win_pct=report['win_pct'],trades=len(trades),
            average_gross_capital=report['average_gross_capital'],
            average_gross_exposure_pct=100*report['average_gross_equity_ratio']))
    if read(root/'economic-baseline-validation.json')['status']!='PASS':raise ValueError('Reference parity failed')
    result=dict(status='PASS',annual_models=annual,results=economics,model_timing_oos=True,strict_pit=False,
        limitations=plan['limitations'],SQL_writes=0,orders=0,provider_calls=0)
    atomic_json(root/'validation.json',result)
    pd.DataFrame(economics).to_csv(root/'comparison-validated.csv',index=False)
    pd.DataFrame(annual).to_csv(root/'annual-global-models.csv',index=False)
    # The driver exports the native ratio under its native name in each report.
    # Fill the presentation-only percent column; preserve the initial export.
    comparison=pd.read_csv(root/'comparison.csv')
    ratios={r['policy']:r['average_gross_exposure_pct'] for r in economics}
    if comparison.average_gross_exposure_pct.isna().all():
        if not (root/'comparison-before-exposure-formatting.csv').exists():
            (root/'comparison-before-exposure-formatting.csv').write_bytes((root/'comparison.csv').read_bytes())
        comparison['average_gross_exposure_pct']=comparison.policy.map(ratios)
        comparison.to_csv(root/'comparison.csv',index=False)
    summary=read(root/'report.json')
    if any(r.get('average_gross_exposure_pct') is None for r in summary['results']):
        atomic_json(root/'report-before-exposure-formatting.json',summary)
        for row in summary['results']:row['average_gross_exposure_pct']=ratios[row['policy']]
        summary.update(validation='PASS',validation_file='validation.json')
        atomic_json(root/'report.json',summary);atomic_json(root/'progress.json',summary)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',default='artifacts/research/us_q051_global_rank_h10/20261115-v1')
    p.add_argument('--market-only',action='store_true');p.add_argument('--qualify-protocols-only',action='store_true');args=p.parse_args()
    if args.qualify_protocols_only:result=qualify_case_protocols(args.output_dir)
    elif args.market_only:result=validate_market(args.output_dir)
    else:result=validate(args.output_dir)
    print(json.dumps(result,ensure_ascii=False))
