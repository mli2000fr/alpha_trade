import pandas as pd

from scripts.research.us_extreme50_capture import freeze_selection
from scripts.research.us_concentrated_historical_tapes import decision_rows


def test_intersection_top10_is_ranked_within_top20_percent_pool_not_atr_ten_names():
    scores = pd.DataFrame(dict(date=pd.Timestamp('2025-01-02'),
        symbol=[f'S{i:02}' for i in range(100)], proba_extreme=list(range(100))))
    atr = scores[['date', 'symbol']].copy()
    atr['atr20_pct'] = [float(i+1) for i in range(100)]
    panel = freeze_selection(scores, atr)
    assert panel.INTERSECTION_ORACLE_TOP10.sum() == 10
    assert panel.ORACLE_TOP10.equals(panel.INTERSECTION_ORACLE_TOP10)
    panel['fold_start'] = pd.Timestamp('2024-01-01')
    assert decision_rows(panel).INTERSECTION_ORACLE_TOP10.sum() == 10


def test_intersection_excludes_low_atr_and_replenishes_only_inside_intersection():
    scores = pd.DataFrame(dict(date=pd.Timestamp('2025-01-02'),
        symbol=[f'S{i:02}' for i in range(100)], proba_extreme=list(range(100))))
    atr = scores[['date', 'symbol']].copy()
    atr['atr20_pct'] = [float(i+1) for i in range(100)]
    atr.loc[atr.symbol.eq('S99'), 'atr20_pct'] = .01
    panel = freeze_selection(scores, atr).set_index('symbol')
    assert panel.loc['S99', 'ORACLE_TOP10']
    assert not panel.loc['S99', 'INTERSECTION_ORACLE_TOP10']
    assert panel.loc['S89', 'INTERSECTION_ORACLE_TOP10']
    assert panel.INTERSECTION_ORACLE_TOP10.sum() == 10
