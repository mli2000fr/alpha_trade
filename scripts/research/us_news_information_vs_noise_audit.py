"""Reproduce source, receipt, sampling and review checks offline, without outcomes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from event_sentiment import news_archive as archive
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_news_event_qualification import evidence_items
from scripts.research.us_news_information_vs_noise_feasibility import READ, pick, validate_reviews


def snapshot_integrity(snapshot, cutoff):
    """Validate actual archived content/mapping hashes and strictly prior receipts."""
    raw = {r['id']: r for r in snapshot['raw_versions']}
    maps = {r['id']: r for r in snapshot['mapping_versions']}
    if len(raw) != len(snapshot['raw_versions']) or len(maps) != len(snapshot['mapping_versions']):
        raise ValueError('Duplicate version IDs')
    for row in raw.values():
        if archive.canonical_hash({k: row.get(k) for k in ('headline', 'summary', 'content')}) != row['text_hash']:
            raise ValueError('Raw text hash mismatch')
    for row in maps.values():
        if row['raw_version_id'] not in raw:
            raise ValueError('Mapping raw version absent')
        payload = dict(raw_version_id=row['raw_version_id'], rows=archive.decode_json(row['mapping_rows']),
            context=archive.decode_json(row['mapping_context']), complete=bool(row['payload_scope_complete']))
        if archive.canonical_hash(payload) != row['snapshot_hash']:
            raise ValueError('Mapping snapshot hash mismatch')
    ids = set()
    for row in snapshot['observations']:
        if row['id'] in ids:
            raise ValueError('Duplicate observation')
        ids.add(row['id'])
        available = pd.to_datetime(row['available_at'], utc=True)
        observed = pd.to_datetime(row['observed_at'], utc=True)
        if pd.isna(available) or pd.isna(observed) or available >= cutoff or observed >= cutoff or available < observed:
            raise ValueError('Receipt outside causal cutoff')
    return dict(raw_versions=len(raw), mapping_versions=len(maps), sealed_observations=len(ids))


def audit(root):
    if (root / 'audit.json').exists():
        raise ValueError('Audit immutable')
    verify_hashes(Path('.'), READ(root / 'protocol.json')['sources'])
    for panel in ('historical', 'prospective'):
        verify_hashes(root, READ(root / (panel + '-report.json'))['files'])
        source_name = 'historical-article-pairs.json' if panel == 'historical' else 'prospective-current-pairs.json'
        items = READ(root / source_name); pack = READ(root / (panel + '-review-pack.json'))
        if pick(items) != pack:
            raise ValueError('Prespecified review sample differs')
    readout = root / 'readout-v1'
    verify_hashes(Path('.'), READ(readout / 'protocol.json')['sources'])
    verify_hashes(readout, READ(readout / 'report.json')['files'])
    notes = READ(readout / 'review-notes.json')
    for panel in ('historical', 'prospective'):
        validate_reviews(READ(root / (panel + '-review-pack.json')), notes[panel])
    frame = pd.read_parquet(root / 'historical-top10.parquet')
    assert len(frame) == 200 and not frame.duplicated(['date', 'symbol']).any()
    assert frame.groupby('date').oracle_rank.apply(lambda r: set(r) == set(range(1, 11))).all()
    availability = pd.read_parquet(root / 'historical-availability.parquet')
    assert len(availability) == len(frame) and availability.strict_current_version_guards.eq(0).all()
    recent = READ(root / 'prospective-report.json'); snapshot = READ(root / 'prospective-archive-snapshot.json')
    cutoff = pd.Timestamp(recent['cutoff']); since = cutoff.to_pydatetime() - pd.Timedelta(days=30)
    current = READ(root / 'prospective-current-pairs.json'); context = READ(root / 'prospective-prior-context.json')
    symbols = {p['symbol'] for p in current + context} | set(recent['symbols_without_current_pairs'])
    integrity = snapshot_integrity(snapshot, cutoff)
    restored, diagnostics = evidence_items(snapshot, symbols, since, cutoff.to_pydatetime())
    restored_current = [r for r in restored if r['publication_utc'] is not None
        and pd.Timestamp(recent['publication_start']) <= pd.Timestamp(r['publication_utc']) < cutoff]
    assert {(r['article_id'], r['symbol'], r['raw_version_id'], r['mapping_version_id']) for r in restored_current} == {
        (r['article_id'], r['symbol'], r['raw_version_id'], r['mapping_version_id']) for r in current}
    assert all(not r['temporal_reservations'] for r in restored_current)
    assert len(current) == 5 and len(context) == 75 and not snapshot['truncated']
    details = READ(readout / 'review-details.json')
    mismatch = [r for r in details if r['panel'] == 'prospective' and r['symbol'] == 'TXG']
    assert len(mismatch) == 1 and mismatch[0]['subject'] == 'OTHER_ISSUER'
    repeats = [r for r in details if r['panel'] == 'prospective' and r['novelty'] == 'REPEAT_CONFIRMED']
    for row in repeats:
        prior = row['predecessor']
        assert prior and prior['publication_utc'].startswith('2026-10-15') and not prior['temporal_reservations']
    report = dict(status='PASS_OFFLINE_FEASIBILITY_AND_REVIEW_AUDIT', created_at_utc=datetime.now(timezone.utc).isoformat(),
        historical_decisions=200, historical_review_pairs=30, historical_pit_occurrences=0,
        recent_current_pairs=5, recent_context_pairs=75, recent_review_pairs=5, recent_archive_integrity=integrity,
        recent_receipts_before_cutoff=True, bounded_sample_reproduced=True, exact_quotes_validated=True,
        txg_tex_subject_reserve_confirmed=True, prior_fmc_release_referenced=len(repeats),
        no_news_certified=0, fully_qualified_new_announcements=0, independent_human_review=False,
        prices_read=False, provider_calls=0, llm_calls=0, sql_writes=False, training=False, orders=False,
        files={str(Path(__file__)): digest(Path(__file__)), 'readout-v1/report.json': digest(readout / 'report.json')})
    atomic_json(root / 'audit.json', report); return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    print(audit(parser.parse_args().root))
