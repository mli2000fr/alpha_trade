import pandas as pd

from scripts.research.analyst_revision_controls import rank_within


def test_conditional_rank_preserves_ties_and_excludes_small_groups():
    frame = pd.DataFrame({"sector":["A"]*4+["B"],"score":[0.,0.,1.,2.,100.]})
    result = rank_within(frame,"score",["sector"],min_size=4)
    assert result.iloc[0] == result.iloc[1] == .375
    assert result.iloc[3] == 1.
    assert pd.isna(result.iloc[4])
