import pandas as pd

from scripts.research.us_news_embeddings_audit import admission_mask


def test_missing_future_outcome_does_not_promote_a_later_signal():
    days=pd.bdate_range('2026-01-01',periods=30)
    source=pd.DataFrame(dict(date=days[[0,1,6,7]],symbol=['A']*4))
    mask=admission_mask(source,days,5)
    assert mask=={(days[0],'A'),(days[6],'A')}
    # Suppose the first future path is unqualified: the signal at J+1 is NOT
    # substituted after reading outcomes, unlike selecting from qualified rows.
    surviving={(days[1],'A'),(days[6],'A'),(days[7],'A')}
    assert surviving & mask=={(days[6],'A')}


def test_nonoverlap_admission_is_independent_per_symbol_and_order():
    days=pd.bdate_range('2026-01-01',periods=30)
    source=pd.DataFrame(dict(date=days[[5,0,1,2]],symbol=['A','A','B','B']))
    assert admission_mask(source,days,10)=={(days[0],'A'),(days[1],'B')}
