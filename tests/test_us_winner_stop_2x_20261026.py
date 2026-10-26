import pytest
from scripts.research import us_winner_stop_2x_20261026 as s


def command(kind,phase=None,target=None):
    result=['python','-m',s.LEGACY,'--target',target or sorted(s.TARGETS)[1],'--kind',kind]
    return result+(['--phase',phase] if phase else [])


@pytest.mark.parametrize('phase',[None,'year','resume','qualify'])
def test_no_1x_process_is_a_stop_target(phase):assert s.role(command('1x',phase)) is None


def test_exact_2x_commands_and_shared_parent_only():
    assert s.role(command('2x'))=='2x_supervisor'
    assert s.role(command('2x','year'))=='2x_worker'
    assert s.role(command('2x','resume'))=='2x_worker'
    assert s.role(['python','-m',s.SHARED,'--phase','supervise'])=='shared_supervisor'
    assert s.role(['python','-m',s.SHARED,'--phase','consolidate']) is None
    assert s.role(command('2x','year','unrelated')) is None


def test_2x_queued_jobs_excluded():
    assert s.eligible('1x-2023')
    assert not s.eligible('2x-2020')
    assert not s.eligible('top50-2017')
