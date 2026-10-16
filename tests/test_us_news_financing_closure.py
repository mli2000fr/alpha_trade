from datetime import datetime,timezone
import pytest

from scripts.research import us_news_financing_closure_20261016 as closure

NOW=datetime(2026,10,16,tzinfo=timezone.utc)


def item(key,article,symbol='NVDA',text=None,screened=True,reservations=None):
    return dict(evidence_key=key,article_id=article,symbol=symbol,text_hash=text or article,
        screened=screened,temporal_reservations=reservations or [],
        fields={'content':'The issuer announced an equity financing today.'}, raw_version_id=1,
        text_available_at='2026-10-15T15:00:00Z',mapping_available_at='2026-10-15T16:00:00Z')


def test_closure_includes_all_alias_pairs_without_claiming_more_unread_texts():
    rows=[item('a','one'),item('b','one',symbol='BAC'),item('c','two'),
          item('d','reserved',reservations=['OLD_PUBLICATION']),item('e','control',screened=False)]
    eligible,remaining=closure.eligible_and_remaining(rows,[rows[0]],[rows[-1]])
    assert [r['evidence_key'] for r in eligible]==['a','b','c']
    assert remaining=={'two'}
    assert closure.eligible_and_remaining(list(reversed(rows)),[rows[0]],[rows[-1]])==(eligible,remaining)


def test_changed_parent_pair_is_refused():
    r=item('a','one')
    with pytest.raises(ValueError,match='same parent'):
        closure.eligible_and_remaining([r],[dict(r,symbol='OTHER')],[])


def test_rebinding_preserves_issuer_mismatch_and_does_not_backdate():
    r=item('a','one')
    note=dict(issuer='IonQ', identity_symbols=['IONQ'], event_type='PRIMARY_EQUITY_FINANCING',
        category='OTHER_ISSUER',quote='announced an equity financing', notes='Different issuer')
    row=closure.annotations([r],{'one':note},NOW)[0]
    assert row['identity_verified'] is False
    assert row['prior_comparison_complete'] is False
    assert row['reviewed_at_utc']==NOW.isoformat()
    decision=closure.evidence.qualify_review(r,row,NOW)
    assert decision['status']=='RESERVED'
    assert 'ISSUER_IDENTITY_UNVERIFIED' in decision['reasons']
    with pytest.raises(ValueError,match='Exact quotation'):
        closure.annotations([r],{'one':dict(note,quote='Invented text')},NOW)


def test_repeats_do_not_merge_different_issuers_and_keep_actual_availability(monkeypatch):
    monkeypatch.setattr(closure,'REPEATS',dict(FIRST=dict(issuer='Issuer One',issuer_symbols=['ONE'],
        instrument='COMMON',articles=['a','b'],rationale='Same reviewed transaction')))
    rows=[item('1','a'),item('2','a',symbol='BAC'),item('3','b'),item('4','c')]
    notes={r['article_id']:dict(quote='announced an equity financing') for r in rows}
    groups=closure.repeat_groups(rows,notes,{'NVDA','BAC'},NOW)
    assert len(groups)==1 and groups[0]['mapped_pair_count']==3
    assert groups[0]['source_article_count']==2
    assert groups[0]['issuer_symbols_in_frozen_file']==[]
    assert groups[0]['earliest_selected_pair_available_at'].isoformat()=='2026-10-15T16:00:00+00:00'
    assert groups[0]['annotation_available_at']==NOW
    assert groups[0]['first_ever_announcement_or_syndication_certified'] is False
    with pytest.raises(ValueError,match='Missing repeat'):
        closure.repeat_groups(rows[:2],notes,set(),NOW)


def test_existing_interpretation_cannot_be_changed_silently():
    r=item('a','one')
    note=dict(issuer='IonQ', identity_symbols=['IONQ'], event_type='PRIMARY_EQUITY_FINANCING',
        category='OTHER_ISSUER',quote='announced an equity financing', notes='Different issuer')
    rows=closure.annotations([r],{'one':note},NOW)
    closure.check_note_lineage([r],rows,{'one':note})
    with pytest.raises(ValueError,match='Changed prior interpretation'):
        closure.check_note_lineage([r],rows,{'one':dict(note,identity_symbols=['NVDA'])})
