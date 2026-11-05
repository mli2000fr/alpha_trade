"""Re-run daily rules and matched confirmation/DD15 arms with TOP5 LONG scores."""
from pathlib import Path
import json
import logging
import time
import pandas as pd
from common.daily_bar_sources import select_daily_bars
from scripts.research.us_selected_universe_per_symbol_selection_20261104 import OUT,PREVIOUS,ORACLE,BASE
from scripts.research.us_selected_universe_oracle_20261104 import (
    CASES,END,POLICY,digest,save,replay,prepare_prices,nyse_sessions)
from scripts.research import us_selected_universe_winner_dd15_20261104 as native

LOG=logging.getLogger(__name__)


def check_selection():
    r=json.loads((OUT/'selection-report.json').read_text())
    assert r['status']=='COMPLETED' and r['models']==207
    assert all(digest(p)==h for p,h in r['source_hashes'].items())
    return r


def daily():
    selection=check_selection()
    calendar=nyse_sessions(pd.Timestamp('2016-01-01').date(),END.date())
    rows=[]
    for case,(horizon,_) in CASES.items():
        top=pd.read_csv(OUT/case/'daily-top5.csv',parse_dates=['date'])
        names=selection['cases'][case]['universe']
        raw={s:select_daily_bars(pd.read_parquet(BASE/'symbols'/s/'source-bars.parquet')) for s in names}
        prices=prepare_prices(raw,calendar)
        for period in ('2024','2025','2026','continuous'):
            path=OUT/'daily'/case/period
            if (path/'report.json').exists():
                r=json.loads((path/'report.json').read_text())
            else:
                path.mkdir(parents=True,exist_ok=False)
                start='2024-01-01' if period=='continuous' else f'{period}-01-01'
                end=END if period in ('2026','continuous') else pd.Timestamp(f'{period}-12-31')
                r,curve,trades,audit=replay(top,prices,calendar,start,end,horizon)
                curve.to_csv(path/'equity.csv',index=False)
                trades.to_csv(path/'trades.csv',index=False)
                audit.to_csv(path/'entry-audit.csv',index=False)
                save(path/'report.json',r)
            rows.append(dict(case=case,period=period,selection='ORACLE_TOP20_PER_SYMBOL_LONG_TOP5',
                **{k:v for k,v in r.items() if k not in ('policy','open_positions','audit_status_counts')}))
            LOG.info('DAILY %s %s return=%.2f DD=%.2f trades=%s',case,period,r['return_pct'],r['max_drawdown_pct'],r['closed_trades'])
    pd.DataFrame(rows).to_csv(OUT/'daily-comparison.csv',index=False)
    save(OUT/'daily-report.json',dict(status='COMPLETED_RETROSPECTIVE',cases=rows,sql_writes=False,orders=0))


def intraday():
    selection=check_selection()
    mixed=OUT/'mixed-cohort'
    mixed.mkdir(exist_ok=True)
    save(mixed/'report.json',dict(cases=selection['cases']))
    methods={'ORACLE_TOP5':{},'PER_SYMBOL_LONG_TOP5':{}}
    for case in CASES:
        before=pd.read_csv(ORACLE/case/'daily-top5.csv',parse_dates=['date'])
        after=pd.read_csv(OUT/case/'daily-top5.csv',parse_dates=['date'])
        for key,frame in [('ORACLE_TOP5',before),('PER_SYMBOL_LONG_TOP5',after)]:
            methods[key][case]={d:g.sort_values('oracle_rank').to_dict('records') for d,g in frame.groupby('date')}
        path=mixed/case;path.mkdir(exist_ok=True)
        pd.concat([after,before]).drop_duplicates(['date','symbol']).to_csv(path/'daily-top5.csv',index=False)
    # Native adapter code is unchanged. Only file roots and candidate membership change.
    native.OUT=OUT;native.PRIOR=mixed
    tape=native.Tape()
    union_masks={case:pd.read_csv(OUT/f'{case}-matched-entry-quality.csv',parse_dates=['entry_date','signal_date']) for case in CASES}
    for method in methods:
        for case in CASES:
            keys={(d,r['symbol']) for d,rows in methods[method][case].items() for r in rows}
            a=union_masks[case]
            chosen=[(d,s) in keys for d,s in zip(a.signal_date,a.symbol)]
            a.loc[chosen].to_csv(OUT/f'{case}-{method}-entry-quality.csv',index=False)
    dependencies=[Path(__file__),Path(native.__file__),OUT/'selection-report.json',OUT/'models-reused.json',
        OUT/'inputs/manifest.json',OUT/'recovery/report.json',OUT/'tail-recovery/report.json',
        OUT/'split-qualification/report.json',Path('config.yaml'),PREVIOUS/'protocol.json']
    proto=dict(sources={str(p):digest(p) for p in dependencies},
        strategy='Dedicated Oracle TOP20 -> independent annual per-symbol calibrated P(LONG) -> TOP5',
        original_model_universes=selection['cases'],new_training=False,oracle_models_reused=6,per_symbol_models_reused=207,
        ranking_uses_daily_long_probability=True,minimum_long_probability=None,
        native_confirmation='2 completed closes above prior high, delay930s, next observed IOC open capped1%',
        dd15='Native B4, half the positions, rearm; not a hard15% cap',
        same_intraday_tape_and_quality_gate_for_both_selection_methods=True,
        primary_years=[2024,2025,2026],additional_continuous=True,end=str(END.date()),
        universe_selection_uses_2026=True,future_data_gate=True,independent_validation=False,
        full_live_parity=False,sql_writes=False,orders=0,production_changed=False)
    if (OUT/'protocol.json').exists():
        p=json.loads((OUT/'protocol.json').read_text())
        assert p['sources']==proto['sources'],'Changed experiment sources: fresh campaign required'
    else:save(OUT/'protocol.json',proto)
    rows=[];start=time.monotonic()
    for method,top in methods.items():
        tape.top=top
        native.OUT=OUT/'intraday'/method
        native.OUT.mkdir(parents=True,exist_ok=True)
        for case in CASES:
            for period in ('2024','2025','2026','continuous'):
                for arm in native.ARMS:
                    r=native.run_case(tape,case,period,arm)
                    rows.append(dict(selection=method,**{k:v for k,v in r.items() if k not in ('files','liquidation','open_positions')}))
                    pd.DataFrame(rows).to_csv(OUT/'intraday-comparison.csv',index=False)
                    save(OUT/'progress.json',dict(status='RUNNING',phase='MATCHED_INTRADAY',completed=len(rows),total=64,
                        selection=method,case=case,period=period,arm=arm,elapsed_seconds=time.monotonic()-start))
    assert all(digest(p)==h for p,h in proto['sources'].items())
    save(OUT/'report.json',dict(status='COMPLETED_RETROSPECTIVE_WITH_COVERAGE_LIMITS',cases=selection['cases'],
        daily_replays=8,intraday_replays=64,new_fits=0,per_symbol_models_reused=207,
        selection_report_sha256=digest(OUT/'selection-report.json'),
        daily_report_sha256=digest(OUT/'daily-report.json'),
        elapsed_intraday_seconds=time.monotonic()-start,sql_writes=False,broker_calls=0,production_changed=False))
    save(OUT/'progress.json',dict(status='COMPLETED_RETROSPECTIVE_WITH_COVERAGE_LIMITS',completed=72,total=72))


if __name__=='__main__':
    import argparse
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['daily','intraday'],required=True)
    a=p.parse_args()
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('HTTP forbidden during frozen financial simulations')
    requests.Session.request=forbidden
    daily() if a.phase=='daily' else intraday()
