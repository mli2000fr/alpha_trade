from datetime import datetime,timezone

import pytest
from sqlalchemy import create_engine

from event_sentiment import news_archive as archive
from scripts.research import us_news_financing_completion_20261016 as completion

SINCE=datetime(2026,10,14,tzinfo=timezone.utc)
CUTOFF=datetime(2026,10,16,tzinfo=timezone.utc)


def test_partition_union_includes_boundaries_and_non_eodhd_ids():
    engine=create_engine('sqlite://')
    archive.META.create_all(engine)
    ids=['alpaca:fixture','eodhd:0','eodhd:4','eodhd:8','eodhd:c','eodhd:ffff']
    with engine.begin() as conn:
        for index,article in enumerate(ids,1):
            raw=archive.raw_snapshot(dict(article_id=article,headline='Synthetic fixture',summary=None,content='Fixture',
                source='fixture',author=None,url='https://fixture.test',published_at_utc=SINCE.replace(tzinfo=None),
                ingestion_source='eodhd',raw_payload={'created_at':SINCE.isoformat()}),
                article,SINCE.replace(tzinfo=None))
            conn.execute(archive.RAW_VERSIONS.insert(),dict(raw,id=index))
            conn.execute(archive.OBSERVATIONS.insert(),dict(id=index,article_id=article,
                stream_key='article',batch_id='fixture',origin='PROVIDER_COLLECTION',
                raw_version_id=index,
                observed_at=SINCE.replace(tzinfo=None),available_at=SINCE.replace(tzinfo=None)))
        merged=completion.complete_snapshot(conn,SINCE,CUTOFF,cap=2)
        assert set(merged['article_ids'])==set(ids)
        assert len(merged['article_ids'])==len(set(merged['article_ids']))
        assert merged['partition_manifest']['sql_distinct_articles']==6
        with pytest.raises(ValueError,match='truncated'):
            completion.complete_snapshot(conn,SINCE,CUTOFF,cap=1)


def test_review_selection_is_price_blind_bounded_and_excludes_reserved():
    items=[dict(evidence_key=f'{i:03}',screened=i<40,temporal_reservations=[]) for i in range(60)]
    items+=[dict(evidence_key='0000',screened=True,temporal_reservations=['OLD_PUBLICATION'])]
    selected=completion.select_review(items)
    assert len(selected)==30 and sum(r['screened'] for r in selected)==20
    assert all(not r['temporal_reservations'] for r in selected)
    assert completion.select_review(list(reversed(items)))==selected
