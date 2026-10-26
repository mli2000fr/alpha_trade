import pandas as pd

from scripts.research.us_winner_gpt_veto_1_4_august_2026 import apply_cutoff, filtered_signals


def fixture():
    scores = [1, 2, 3, 4, 5, 7, 10, None, 4]
    return pd.DataFrame(dict(date=[pd.Timestamp('2026-08-03')] * len(scores),
        symbol=[f'S{i}' for i in range(len(scores))], oracle_rank=list(range(1, len(scores)+1)),
        gpt_score=scores, gpt_status=['VALID']*8+['INVALID'], selected=[True]*len(scores)))


def test_four_inclusive_invalid_and_null_do_not_veto():
    original = fixture()
    result = apply_cutoff(original)
    assert result.gpt_veto.tolist() == [True]*4 + [False]*5
    assert 'gpt_veto' not in original
    pd.testing.assert_frame_equal(result.drop(columns='gpt_veto'), original)


def test_common_eligibility_rank_and_no_replacement():
    cohort = apply_cutoff(fixture())
    cohort.loc[4, 'selected'] = False
    result = filtered_signals(cohort)
    assert len(result) == len(cohort)
    assert result['rank'].tolist() == cohort.oracle_rank.tolist()
    assert result.selected.tolist() == [False]*5 + [True]*4
    assert result.side.eq('long').all()
