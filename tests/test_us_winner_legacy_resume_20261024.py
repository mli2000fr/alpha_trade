"""Legacy resumes cannot import the newly changed economic replay core."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.research import us_winner_legacy_resume_20261024 as resume


def test_exact_source_resolution_only_redirects_the_two_archived_cores():
    paths=resume.legacy_paths()
    for current,archived,sha in paths.values():
        assert resume.effective_source(current,paths)==archived
        assert resume.digest(archived)==sha
    other=resume.ROOT/'risk_management/config.py'
    assert resume.effective_source(other,paths)==other


@pytest.mark.parametrize('target',list(resume.TARGETS.values()))
def test_only_known_research_children_inherit_isolated_engine(target):
    command=[sys.executable,'-u','-m',target,'--phase','year','--kind','1x']
    actual=resume.child_command(command)
    assert actual==[sys.executable,'-u','-m',resume.MODULE,'--target',target,'--phase','year','--kind','1x']


def test_unknown_research_child_is_not_silently_run_against_new_engine():
    with pytest.raises(ValueError,match='Unexpected legacy research child'):
        resume.child_command([sys.executable,'-m','scripts.research.unknown'])
    command=['an-unrelated-program','--version']
    assert resume.child_command(command)==command


def test_fresh_subprocess_replays_with_archived_classes_and_without_global_dd():
    done=subprocess.run([sys.executable,'-u','-m',resume.MODULE,'--phase','probe'],
        cwd=resume.ROOT,text=True,capture_output=True,timeout=60)
    assert done.returncode==0,done.stderr
    result=json.loads(done.stdout)
    assert result['status']=='PASS_ISOLATED_LEGACY_NATIVE_REPLAY'
    assert result['final_equity']>0
    for name,path in result['core'].items():
        assert Path(path)==resume.legacy_paths()[name][1]
