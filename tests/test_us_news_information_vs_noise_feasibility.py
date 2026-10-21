import pytest

from scripts.research import us_news_information_vs_noise_feasibility as s


def item(i, screened=False, symbol='TEST', **extra):
    return dict(evidence_key=s.key(symbol, str(i)), article_id=str(i), decision_date='2026-01-02',
        symbol=symbol, screened=screened, headline='A reported fact', summary='', content='Some archived content', **extra)


def test_screen_is_a_route_not_an_event_verdict():
    assert s.screen('Why Shares Jumped After Results')
    assert not s.screen('Five Stocks to Buy Now')
    assert s.source_reserved('https://www.msci.com/a')


def test_sample_deterministic_bounded_with_unscreened_controls_no_returns():
    items = [item(i, i < 40) for i in range(80)]
    chosen = s.pick(items)
    assert chosen == s.pick(list(reversed(items)))
    assert len(chosen) == 30 and sum(r['screened'] for r in chosen) == 20


def test_repeat_pair_not_recounted_but_other_issuer_needs_own_review():
    assert len(s.pick([item(1), item(1), item(1, symbol='OTHER')])) == 2
    assert s.pick([item(1, rights_reserved=True)]) == []


def note(row):
    return dict(evidence_key=row['evidence_key'], category='MIXED_OR_UNRESOLVED', subject='UNKNOWN',
        novelty='UNKNOWN', note='Bounded excerpt cannot certify novelty', quotes=[dict(field='headline', text=row['headline'])])


def test_unknown_not_promoted_to_no_news_or_new():
    row = item(1); n = note(row)
    assert s.validate_reviews([row], [n])['fully_qualified_new_announcements'] == 0
    with pytest.raises(ValueError, match='promotion'):
        s.validate_reviews([row], [dict(n, novelty='NEW')])


def test_quote_and_complete_prespecified_review_membership():
    row = item(1); n = note(row)
    with pytest.raises(ValueError, match='accounted'):
        s.validate_reviews([row], [])
    with pytest.raises(ValueError, match='absent'):
        s.validate_reviews([row], [dict(n, quotes=[dict(field='content', text='invented assertion')])])


def test_repetition_requires_explicit_category():
    row = item(1); n = note(row)
    with pytest.raises(ValueError, match='Repeat'):
        s.validate_reviews([row], [dict(n, novelty='REPEAT_CONFIRMED')])
