import pandas as pd
import pytest

from service.fr.economic_preflight_11a import load_protocol
from service.fr.validation_protocol_13a import build_protocol, inspect_scope
from pathlib import Path


def example():
    cfg=load_protocol(Path('config/research_fr/economic_references_11a_v1.yaml'))
    paths=pd.DataFrame({'fold':[6,7],'research_uid':['a','b'],'entry_session':['2024-08-01','2025-02-01'],
        'exit_session':['2024-08-08','2025-02-08'],'economic_qualified':[False,False],
        'blockers':[['TAX_UNKNOWN'],['CA_UNKNOWN']]})
    intents=pd.concat([paths[['fold','research_uid','entry_session']].assign(policy=p,
        future_label_used=False,execution_state='INTENT_NOT_FILL') for p in cfg['policies']],ignore_index=True)
    return cfg,paths,intents


def test_freeze_inherits_old_policies_and_reserves_confirmation():
    cfg,_,_=example()
    out=build_protocol(cfg)
    assert out['comparison_policies']==cfg['policies']
    assert out['tax_stress'] is False
    assert out['cost_scenarios']=={'nominal':1,'execution_costs_x2':2}
    assert out['serving_enabled'] is False and out['economic_go_allowed'] is False
    assert 'NOT_READ' in out['confirmation_2026']


def test_blocked_population_never_dropped():
    cfg,paths,intents=example()
    out=inspect_scope(paths,intents,cfg)
    assert out['candidate_paths']==2 and out['intentions']==6
    assert out['qualified_common_paths']==0 and out['all_paths_qualified'] is False


@pytest.mark.parametrize('mutation',['future','duplicate','2026','extra_policy','missing_path'])
def test_reject_invalid_inputs(mutation):
    cfg,paths,intents=example()
    if mutation=='future': intents.loc[0,'future_label_used']=True
    if mutation=='duplicate': paths=pd.concat([paths,paths.iloc[:1]])
    if mutation=='2026': paths.loc[0,'exit_session']='2026-01-02'
    if mutation=='extra_policy': intents.loc[0,'policy']='new_policy'
    if mutation=='missing_path': intents.loc[0,'research_uid']='missing'
    with pytest.raises(ValueError): inspect_scope(paths,intents,cfg)
