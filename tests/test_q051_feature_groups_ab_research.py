"""The AB variant is one 33-feature model, preserving the original panel."""
import os

import pandas as pd
import pytest

from modelFactory.oracle_path.directional import INPUTS
from scripts.research import us_q051_feature_groups_ab_20261116 as ab
from scripts.research import us_q051_feature_groups_20261116 as base


def test_union_is_nine_additions_without_duplicates():
    assert ab.GROUPS['AB']==base.GROUPS['A']+base.GROUPS['B']
    assert len(INPUTS+ab.GROUPS['AB'])==33
    assert len(set(INPUTS+ab.GROUPS['AB']))==33


def test_joint_model_panel_preserves_exact_reference(monkeypatch):
    expected=pd.DataFrame({'date':[pd.Timestamp('2021-01-04')],'symbol':['TEST'],'rsi_14':[50.]})
    def original(bars,benchmark,calendar):
        assert base.GROUPS==ab.cd.AB
        return expected
    monkeypatch.setattr(ab.cd,'_original_common',original)
    with ab.scope():
        assert ab.cd.GROUPS==ab.GROUPS
        result=ab.common_panel(None,None,None)
    pd.testing.assert_frame_equal(result,expected)
    assert base.GROUPS==ab.cd.AB


def test_publication_lock_reuses_file_identity(tmp_path):
    source=tmp_path/'cd'/'lock';target=tmp_path/'ab'/'lock'
    ab.publication_lock(source,target)
    assert os.path.samefile(source,target)
    assert source.read_bytes()==b'0'
    ab.publication_lock(source,target)
    assert source.read_bytes()==b'0'


def test_publication_lock_refuses_independent_existing_file(tmp_path):
    source=tmp_path/'cd.lock';target=tmp_path/'ab.lock';target.write_bytes(b'keep')
    with pytest.raises(ValueError,match='same file identity'):ab.publication_lock(source,target)
    assert target.read_bytes()==b'keep'
