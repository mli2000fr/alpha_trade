import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts.research import us_news_event_pilot_review as study
from scripts.research import us_news_event_qualification as pilot


def fixture_pack(root):
    root.mkdir()
    available = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    rows = []
    for article in study.ANNOTATIONS:
        symbols = ['FIXTURE']
        if article == 'eodhd:d28dc83d1e4bbae0dd8cc510':
            symbols = ['SNPS','KEYS','SIEGY']
        elif article == 'eodhd:38c4c1181538420664ffd179':
            symbols = ['KEYS']
        elif article == 'eodhd:44f4b155343298fdc697b8a1':
            symbols = ['SCCO','SO']
        elif article == 'eodhd:3cb646b70cc16de0f4492dae':
            symbols = ['KEYS','NVDA']
        body = 'Keystone Law Group (AIM:KEYS). Companies discussed in this article include SCCO. ' + study.OLD_FINANCING_QUOTE
        for symbol in symbols:
            rows.append(dict(evidence_key=pilot.archive.canonical_hash([article,symbol]),article_id=article,
                symbol=symbol,fields=dict(headline='Synthetic review fixture, not a live article',summary='',content=body),
                screened=article=='eodhd:d28dc83d1e4bbae0dd8cc510',temporal_reservations=[],
                text_available_at=available,mapping_available_at=available))
    pilot.save(root/'evidence.json',rows)
    pilot.save(root/'review_template.json',[dict(evidence_key=r['evidence_key']) for r in rows])
    pilot.save(root/'report.json',dict(files={n:pilot.sha(root/n) for n in ['evidence.json','review_template.json']}))


def test_bounded_reading_stays_reserved_and_has_exact_citations(tmp_path):
    root=tmp_path/'fixture'
    fixture_pack(root)
    result=study.run(root)
    assert result['distinct_archived_articles_read']==9
    assert result['article_symbol_pairs_read']==13
    assert result['apparent_wrong_event_issuer_or_market_pairs']==4
    assert result['qualified_events']==0
    assert not result['independent_human_review']
    reviews=json.loads((root/'technical_review_filled.json').read_text())
    results=json.loads((root/'technical_review_result.json').read_text())['results']
    assert all(r['status']=='RESERVED' for r in results)
    assert all('EXACT_SOURCE_QUOTES_REQUIRED' not in r['reasons'] for r in results)
    assert all(r['new_announcement_verified'] is False for r in reviews)
    with pytest.raises(FileExistsError):
        study.run(root)


def test_this_manual_reading_cannot_be_reused_for_other_samples(tmp_path):
    root=tmp_path/'wrong'
    fixture_pack(root)
    (root/'review_template.json').unlink()
    pilot.save(root/'review_template.json',[])
    report=json.loads((root/'report.json').read_text())
    report['files']['review_template.json']=pilot.sha(root/'review_template.json')
    (root/'report.json').unlink()
    pilot.save(root/'report.json',report)
    with pytest.raises(ValueError,match='fixed nine'):
        study.run(root)
