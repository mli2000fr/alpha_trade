import pandas as pd
import pytest
from scripts.research import fr_p0_p1_directional_review_20261026 as s


def frame():
    return pd.DataFrame([dict(symbol=symbol,entry_day='2026-10-06',horizon=20,
        feature_available_at='2026-10-05T20:00Z',entry_at='2026-10-06T07:00Z',status='NOT_MATURE')
        for symbol in ['PERR.PA','ALPER.PA']])


def test_current_provider_alias_scope_does_not_modify_frozen_frame():
    f=frame();r=s.scoped_labels(f,{'ALPER.PA'})
    assert r.symbol.tolist()==['ALPER.PA'] and len(f)==2


def test_future_observation_is_refused():
    f=frame();f.loc[:,'feature_available_at']='2026-10-06T08:00Z'
    with pytest.raises(ValueError,match='Future'):s.scoped_labels(f,{'ALPER.PA'})


def test_cannot_promote_partial_h20_or_duplicate_samples():
    f=frame();f.loc[:,'status']='DIAGNOSTIC_LABEL'
    with pytest.raises(ValueError,match='maturity'):s.scoped_labels(f,{'ALPER.PA'})
    f=frame()
    with pytest.raises(ValueError,match='Duplicate'):s.scoped_labels(pd.concat([f,f]),{'ALPER.PA'})
