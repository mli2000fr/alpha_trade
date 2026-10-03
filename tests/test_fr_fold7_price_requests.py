import pandas as pd

from modelFactory.fr_fold7_price_requests import requested_pairs


def test_requests_deduplicate_without_promoting_other_blockers():
    price = {"date": "2025-03-26", "reasons": ["INDEPENDENT_PRICE_CORROBORATION_MISSING"]}
    esma = {"date": "2025-03-25", "reasons": ["MISSING_DELTA_PUBLICATION_DAY"]}
    frame = pd.DataFrame([{"provider_symbol": "A", "feature_window_blockers": [price, esma],
                           "label_path_blockers": [price]}])
    assert requested_pairs(frame) == [("A", "2025-03-26")]
