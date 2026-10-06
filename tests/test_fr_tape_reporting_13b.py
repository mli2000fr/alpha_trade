from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from service.fr.economic_preflight_11a import load_protocol
from service.fr.tape_reporting_13b import assemble_tape, ledger_metrics, prepare
from service.fr.portfolio_replay_12b import replay
from tests.test_fr_portfolio_replay_12b import fixture


def assembly_example(tmp_path):
    tape,_,_=fixture(tmp_path)
    tape.update(fold=6,evidence_state='QUALIFIED_EXECUTION_INPUT')
    day=tape['sessions'][0]
    available=tape.pop('candidates')[0]['available_at']
    tape['candidate_availability']={day:{'A':{'available_at':available,'evidence':'synthetic'}}}
    cfg=load_protocol(Path('config/research_fr/economic_references_11a_v1.yaml'))
    # Small explicitly synthetic test contract, not the frozen real campaign.
    cfg['folds']=[6]
    cfg['horizon']=1
    cfg['portfolio'].update(max_positions=1,initial_equity=1000)
    intents=pd.DataFrame([{'fold':6,'decision_session_date':day,'policy':p,'research_uid':'A',
        'candidate_rank':1,'future_label_used':False,'execution_state':'INTENT_NOT_FILL'} for p in cfg['policies']])
    return tape,cfg,intents


def test_assembly_preserves_all_intents_and_common_input(tmp_path):
    tape,cfg,intents=assembly_example(tmp_path)
    original=deepcopy(tape)
    tapes=[assemble_tape(tape,intents,cfg,6,p) for p in cfg['policies']]
    assert all(len(t['candidates'])==1 for t in tapes)
    assert all(t['bars']==original['bars'] for t in tapes)
    assert tape==original and 'candidates' not in tape


@pytest.mark.parametrize('change',['unqualified','amputated','availability','future','candidates'])
def test_assembly_fail_closed(tmp_path,change):
    tape,cfg,intents=assembly_example(tmp_path)
    day=tape['sessions'][0]
    if change=='unqualified': tape['evidence_state']='UNQUALIFIED_TEMPLATE_DO_NOT_REPLAY'
    if change=='amputated': tape['instruments']={}
    if change=='availability': tape['candidate_availability']={}
    if change=='future': tape['candidate_availability'][day]['A']['available_at']=day+'T09:00:00+00:00'
    if change=='candidates': tape['candidates']=[{}]
    with pytest.raises(ValueError): assemble_tape(tape,intents,cfg,6,cfg['policies'][0])


def test_reporting_synthetic_ledger_reconciles_costs_and_pnl(tmp_path):
    tape,cfg,tax=fixture(tmp_path)
    result=replay(tape,cfg,tax)
    out=ledger_metrics(result,data_kind='SYNTHETIC_TEST_ONLY')
    assert Decimal(out['net_pnl_eur'])==result['net_pnl']
    assert out['executed_orders']==2 and out['closed_trades']==1 and out['win_rate']==1
    assert out['net_return_pct']==pytest.approx(float(result['net_pnl'])/10)
    assert sum(Decimal(s['net_pnl_eur']) for s in out['by_semester'])==result['net_pnl']
    assert sum(Decimal(p) for p in out['by_symbol_net_pnl_eur'].values())==result['net_pnl']
    assert out['mean_gross_exposure_pct']==out['mean_net_exposure_pct']
    assert out['economic_go_allowed'] is False


def test_reporting_never_scores_blocked_or_unreconciled_ledger(tmp_path):
    tape,cfg,tax=fixture(tmp_path)
    result=replay(tape,cfg,tax)
    result['status']='BLOCKED_EXECUTION_EVIDENCE'
    with pytest.raises(ValueError,match='partiel'): ledger_metrics(result,data_kind='QUALIFIED_RESEARCH')
    result['status']='COMPLETED_ASSUMED_COST_RESEARCH'
    result['net_pnl']+=1
    with pytest.raises(ValueError,match='réconciliés'): ledger_metrics(result,data_kind='SYNTHETIC_TEST_ONLY')


def test_flat_ledger_zero_trades_has_no_artificial_sharpe(tmp_path):
    tape,cfg,tax=fixture(tmp_path)
    tape['candidates']=[]
    out=ledger_metrics(replay(tape,cfg,tax),data_kind='SYNTHETIC_TEST_ONLY')
    assert out['closed_trades']==0 and out['win_rate'] is None and out['daily_sharpe'] is None
    assert out['net_return_pct']==0 and out['turnover']==0


def test_existing_output_refused(tmp_path):
    with pytest.raises(ValueError,match='nouveau'): prepare(tmp_path,tmp_path/'absent')
