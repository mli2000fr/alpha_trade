from datetime import datetime

import pandas as pd
import pytest

from event_sentiment import news_archive as a
from scripts.research.us_news_information_vs_noise_audit import snapshot_integrity
from scripts.research.us_news_information_vs_noise_feasibility import selected_snapshot


def snapshot():
    raw = dict(id=1, headline='Headline', summary='', content='A content')
    raw['text_hash'] = a.canonical_hash({k: raw[k] for k in ('headline', 'summary', 'content')})
    mapping = dict(id=2, raw_version_id=1, mapping_rows=[{'symbol':'TEST'}], mapping_context={}, payload_scope_complete=True)
    mapping['snapshot_hash'] = a.canonical_hash(dict(raw_version_id=1, rows=mapping['mapping_rows'], context={}, complete=True))
    return dict(raw_versions=[raw], mapping_versions=[mapping], observations=[dict(id=3,
        observed_at='2026-10-19T18:00Z', available_at='2026-10-19T18:01Z')])


def test_raw_mapping_and_receipt_proofs():
    result = snapshot_integrity(snapshot(), pd.Timestamp('2026-10-19T20:00Z'))
    assert result == dict(raw_versions=1, mapping_versions=1, sealed_observations=1)


@pytest.mark.parametrize('change,match', [('raw', 'text'), ('mapping', 'Mapping'), ('clock', 'cutoff'), ('future', 'cutoff'), ('duplicate', 'Duplicate')])
def test_corruption_or_noncausal_receipt_not_certified(change, match):
    data = snapshot()
    if change == 'raw': data['raw_versions'][0]['content'] = 'Changed'
    elif change == 'mapping': data['mapping_versions'][0]['mapping_rows'][0]['symbol'] = 'OTHER'
    elif change == 'clock': data['observations'][0]['available_at'] = '2026-10-19T17:00Z'
    elif change == 'future': data['observations'][0]['available_at'] = '2026-10-19T20:00Z'
    else: data['observations'].append(data['observations'][0])
    with pytest.raises(ValueError, match=match):
        snapshot_integrity(data, pd.Timestamp('2026-10-19T20:00Z'))


class Result:
    def __init__(self, rows): self.rows = rows
    def scalars(self): return self.rows
    def mappings(self): return self.rows


def test_query_overflow_is_not_an_empty_control_or_complete_archive():
    class Conn:
        def execute(self, query, values=None):
            if values is not None:
                assert values['cap'] == 2
                return Result(['a', 'b'])
            return Result([])
    result = selected_snapshot(Conn(), {'TEST'}, datetime(2026, 10, 1), datetime(2026, 10, 20), cap=1)
    assert result['truncated'] is True and result['article_ids'] == ['a']
    assert result['pending_receipts_not_counted'] is True
