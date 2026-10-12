import pandas as pd
import pytest

from scripts.research.us_oracle_barrier_volume_prepare import apply_volume_proofs, volume_proofs
from scripts.research import us_oracle_barrier_volume_prepare as preparation


def fixture():
    frame=pd.DataFrame([dict(date=pd.Timestamp('2026-06-18'),symbol='FIXTURE',
                            open=100.,high=102.,low=99.,close=101.,volume=0.),
                       dict(date=pd.Timestamp('2026-06-18'),symbol='OTHER',
                            open=50.,high=51.,low=49.,close=50.,volume=123.)])
    proof=dict(symbol='FIXTURE',date='2026-06-18',original_volume=0.,replacement_volume=10000.,
               original=dict(open=100.,high=102.,low=99.,close=101.))
    return frame,proof


def test_volume_repair_preserves_prices_and_other_rows():
    frame,proof=fixture()
    fixed=apply_volume_proofs(frame,[proof])
    assert frame.volume.iloc[0]==0
    assert fixed.volume.iloc[0]==10000
    pd.testing.assert_frame_equal(frame.drop(columns='volume'),fixed.drop(columns='volume'))
    pd.testing.assert_frame_equal(frame.iloc[1:],fixed.iloc[1:])


def test_volume_repair_is_idempotent_if_already_exactly_corrected():
    frame,proof=fixture()
    fixed=apply_volume_proofs(frame,[proof])
    pd.testing.assert_frame_equal(fixed,apply_volume_proofs(fixed,[proof]))


@pytest.mark.parametrize('column,value',[('volume',2.),('open',101.)])
def test_repair_refuses_changed_price_or_volume(column,value):
    frame,proof=fixture()
    frame.loc[0,column]=value
    with pytest.raises(ValueError):
        apply_volume_proofs(frame,[proof])


def test_repair_refuses_duplicate_or_missing_target():
    frame,proof=fixture()
    for bad in (frame.iloc[1:],pd.concat([frame,frame.iloc[:1]])):
        with pytest.raises(ValueError,match='missing, duplicated or changed'):
            apply_volume_proofs(bad,[proof])


def test_archived_proofs_are_positive_and_do_not_claim_historical_pit(monkeypatch):
    original=dict(open=100.,high=102.,low=99.,close=101.,volume=0.)
    refreshed=dict(original,date='2026-06-18',volume=10000.)
    def read(path):
        if path.name=='BAND_eod.json' or path.name=='provider-response.json':
            return [refreshed]
        if 'qualification-contract' in str(path):
            return dict(cases=[dict(symbol='BAND',archived=original,refreshed=refreshed,
                                   raw_payload_sha256='hash')])
        return dict(original=original,refreshed=refreshed,raw_sha256='hash')
    monkeypatch.setattr(preparation,'read',read)
    monkeypatch.setattr(preparation,'digest',lambda path:'hash')
    proofs,paths=volume_proofs()
    assert {p['symbol'] for p in proofs}=={'BAND','GPRE','ATEX'}
    assert all(p['replacement_volume']>0 and p['original_volume']==0 for p in proofs)
    assert not any(p['historical_pit_evidence'] for p in proofs)
    assert len(paths)==6
