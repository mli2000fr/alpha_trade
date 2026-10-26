"""One SL3 no-pause replay; reuse audited SL1/SL5 and consolidate comparison.

Reuse the sealed SL1 execution/audit runner through process-local adapters only.
No edits to that runner, no global-liquidation policy, SQL, provider or orders.
"""
from contextlib import contextmanager
from dataclasses import asdict,replace
from datetime import datetime,timezone
import logging
import os
from pathlib import Path

from scripts.research import us_winner_sl1_min70_20261025 as runner

ROOT=Path('artifacts/research/us_winner_sl3_min70/20261025-v1')
ARM='FIXED_SL3_H20_MIN70'
DOC=Path('doc/ml/winner_sl3_min70_protocole_20261025.md')
TEST=Path('tests/test_us_winner_sl3_min70_20261025.py')
SL1=Path('artifacts/research/us_winner_sl1_min70/20261025-v1')
SL5=runner.COMPARATOR


def actual_sl3(policy):
    if policy.stop_loss_pct!=.05 or policy.take_profit_pct is not None or policy.trailing_stop_pct is not None:
        raise ValueError('Expected SL5/noTP/noTR comparator')
    changed=replace(policy,stop_loss_pct=.03)
    before,after=asdict(policy),asdict(changed)
    after['stop_loss_pct']=before['stop_loss_pct']
    if before!=after:raise ValueError('Non-stop campaign field changed')
    return changed


def verified_reference(base,root):
    report=base.read(root/'report.json')
    if report['status']!='COMPLETED_AUDITED_EXPLORATORY':raise ValueError('Incomplete comparator')
    base.verify(report['sources']);base.verify(report['files'])
    case=report['case']
    if case['initial_equity']!=4000. or case['minimum_notional']!=70.:
        raise ValueError('Wrong reference capital/minimum')
    if case['audit']['status']!='PASS_EXPLICIT_DEPOSIT_CASH_FEES_SCALAR_EXITS_ENTRIES_COVERAGE':
        raise ValueError('Comparator not independently audited')
    return report


def prepare(study,audit,repair,legacy,treatment):
    base=study.capacity.grid.base
    parent=base.read(SL5/'protocol.json');base.verify(parent['sources'])
    cfg=treatment.minimum_only(study.configuration(parent['reference_config'],study.inputs.START))
    if not runner.archived_config_equal(cfg,parent['after']):raise ValueError('Reference configuration drift')
    original=study.profile_policy(cfg.exec_config,study.REFERENCE)
    if asdict(original)!=parent['actual_campaign_policy']:raise ValueError('Reference SL5 policy drift')
    policy=actual_sl3(original)
    references={};sources=dict(parent['sources'])
    for name,root in [('SL1',SL1),('SL5',SL5)]:
        reference=verified_reference(base,root);references[name]=reference['case']
        sources.update(reference['sources']);sources.update(reference['files'])
        sources[str(root/'report.json')]=base.digest(root/'report.json')
    prior=base.read(SL1/'protocol.json')
    if prior['effective_config']!=parent['after']:raise ValueError('SL1/SL5 configuration mismatch')
    for path in [Path(__file__),Path(runner.__file__),DOC,TEST,SL5/'protocol.json',SL1/'protocol.json']:
        sources[str(path)]=base.digest(path)
    base.verify(sources)
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        reference_config=parent['reference_config'],effective_config=asdict(cfg),
        actual_campaign_policy=asdict(policy),comparator_campaign_policy=asdict(original),
        references=references,changed_from_min70_control=['actual_campaign_policy.stop_loss_pct'],
        initial_equity=4000.,currency='USD',minimum_notional=70.,TOP=20,
        start='2020-01-02',end='2024-12-31',gross_cap=1.,full_position=True,fee_per_leg=.0008,
        no_reinforcement=True,no_new_pause_or_global_liquidation=True,
        historical_SL3_admission_and_quantity_ceiling_preserved=True,no_upsize_beyond_original_admission=True,
        original_native_risk_B4_preserved=True,no_annual_reset=True,
        loaded_core=parent['loaded_core'],SQL_reads=0,SQL_writes=0,provider_calls=0,LLM_calls=0,
        training=False,orders=False,production_changed=False,full_live_parity=False,
        independent_holdout=False,future_coverage_selection_bias=True,current_sectors_non_PIT=True)
    ROOT.mkdir(parents=True,exist_ok=False);base.save_new(ROOT/'protocol.json',protocol)
    study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol,cfg


@contextmanager
def installed():
    names=('ROOT','ARM','DOC','TEST','prepare','actual_sl1')
    originals={name:getattr(runner,name) for name in names}
    runner.ROOT,runner.ARM,runner.DOC,runner.TEST=ROOT,ARM,DOC,TEST
    runner.prepare,runner.actual_sl1=prepare,actual_sl3
    try:yield
    finally:
        for name,value in originals.items():setattr(runner,name,value)


def consolidate(base):
    import pandas as pd
    records={label:verified_reference(base,root)['case'] for label,root in [('SL1',SL1),('SL3',ROOT),('SL5',SL5)]}
    keys=['initial_equity','final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers',
        'win_pct','loss_pct','gross_winning_pnl','gross_losing_pnl','average_winning_pnl','average_losing_pnl',
        'average_gross_capital','average_gross_equity_ratio','costs']
    rows=[dict(variant=label,**{k:case[k] for k in keys},open_positions=len(case['open_positions']))
        for label,case in records.items()]
    annual=[dict(variant=label,**row) for label,case in records.items() for row in case['annual']]
    pd.DataFrame(rows).to_csv(ROOT/'comparison-sl1-sl3-sl5.csv',index=False)
    pd.DataFrame(annual).to_csv(ROOT/'annual-comparison-sl1-sl3-sl5.csv',index=False)
    base.save_new(ROOT/'comparison-sl1-sl3-sl5.json',dict(status='COMPLETED_AUDITED_EXPLORATORY_COMPARISON',
        cases=records,summary=rows,annual=annual,currency='USD',no_pause_all_three=True,
        full_live_parity=False,independent_holdout=False,
        note='Only SL3 newly simulated; SL1/SL5 reused after checksum/audit/configuration checks'))


def main():
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    legacy.install_legacy()
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from scripts.research import us_winner_start_state_audit_20261025 as audit
    from scripts.research import us_winner_min70_4000_20261025 as treatment
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('HTTP forbidden in SL3 replay'))
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    try:
        with installed():runner.run(repair.study,audit,repair,legacy,treatment)
        consolidate(repair.study.capacity.grid.base)
    except BaseException as exc:
        if ROOT.exists():
            repair.study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',
                error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
