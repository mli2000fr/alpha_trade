import pandas as pd
import pytest

from scripts.research.us_news_materiality_feasibility import (
    audit_panel, guarded_reasons, headline_screen, raw_publication_reason)


def article(**overrides):
    row=dict(article_id='a',symbol='TEST',headline='Test launches public offering',
        ingestion_source='eodhd',content_chars=1000,provider_publication='2025-01-02T15:00:00Z',
        headline_screen=True, content_sha256='hash',published_at_utc=pd.Timestamp('2025-01-02T15:00Z'))
    row.update({key:pd.Timestamp('2025-01-02T15:01Z') for key in
        ('created_at','updated_at','map_created_at','map_updated_at')})
    row.update(overrides)
    return row


@pytest.mark.parametrize('value,expected',[
    ('2025-01-02','PUBLICATION_DATE_ONLY_OR_MISSING'),
    ('2025-01-02 15:00:00','PUBLICATION_TIMEZONE_UNKNOWN'),
    ('2025-01-02T16:00:00+01:00',None),
    ('2025-01-03T15:00:00Z','PUBLICATION_NORMALIZATION_MISMATCH'),
    (None,'PUBLICATION_DATE_ONLY_OR_MISSING')])
def test_publication_precision(value,expected):
    assert raw_publication_reason(value,pd.Timestamp('2025-01-02T15:00Z'))==expected


def test_each_mutable_timestamp_must_precede_decision():
    cutoff=pd.Timestamp('2025-01-02T21:00Z')
    assert guarded_reasons(article(),cutoff)==[]
    for key in ('created_at','updated_at','map_created_at','map_updated_at'):
        assert key.upper()+'_NOT_BEFORE_DECISION' in guarded_reasons(article(**{key:cutoff}),cutoff)
    assert 'BODY_MISSING_OR_SHORT' in guarded_reasons(article(content_chars=None),cutoff)
    with pytest.raises(ValueError,match='Timezone-aware'):
        guarded_reasons(article(),pd.Timestamp('2025-01-02'))


def test_historical_backfill_never_becomes_causal_news():
    cutoff=pd.Timestamp('2025-01-02T21:00Z')
    candidates=pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'),symbol='TEST',year=2025,oracle_rank=1)])
    news=pd.DataFrame([article(created_at=pd.Timestamp('2026-05-01T15:00Z'))])
    panel=audit_panel(candidates,news,{pd.Timestamp('2025-01-02'):cutoff})
    assert panel.iloc[0].screened_last_24h==1
    assert panel.iloc[0].screened_guarded_last_24h==0
    assert panel.iloc[0].available_novelty_context_count==0


def test_absence_is_not_an_event_or_novelty():
    cutoff=pd.Timestamp('2025-01-02T21:00Z')
    candidates=pd.DataFrame([dict(date=pd.Timestamp('2025-01-02'),symbol='OTHER',year=2025,oracle_rank=1)])
    panel=audit_panel(candidates,pd.DataFrame([article()]),{pd.Timestamp('2025-01-02'):cutoff})
    assert panel.iloc[0].recent_article_mappings==0
    assert panel.iloc[0].screened_last_24h==0
    assert panel.iloc[0].available_novelty_context_count==0


def test_keyword_screen_is_only_retrieval():
    assert headline_screen('Company announces public offering')
    assert headline_screen('Shareholder secondary public offering')  # Requires manual exclusion.
    assert not headline_screen('Strong positive sentiment and a new price target')


def test_exact_reprints_do_not_fill_the_novelty_context():
    cutoff=pd.Timestamp('2025-01-04T21:00Z')
    candidates=pd.DataFrame([dict(date=pd.Timestamp('2025-01-04'),symbol='TEST',year=2025,oracle_rank=1)])
    news=pd.DataFrame([article(article_id=str(i)) for i in range(12)])
    panel=audit_panel(candidates,news,{pd.Timestamp('2025-01-04'):cutoff})
    assert panel.iloc[0].recent_guarded_mappings==12
    assert panel.iloc[0].available_novelty_context_count==1
