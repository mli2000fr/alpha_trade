"""Tests pour :mod:`event_sentiment.relevance` (Niveau 2/3).

Vérifie le comportement déterministe du scorer : présence du nom société,
présence du ticker dans le texte, bonus primary, pénalité multi-tickers,
bornes [0, 1], reproductibilité, audit components.
"""

from __future__ import annotations

import pytest

from event_sentiment.relevance import (
    DEFAULT_WEIGHTS,
    RELEVANCE_VERSION,
    RelevanceWeights,
    score_article_symbol,
)


def test_score_is_deterministic_and_bounded() -> None:
    out1 = score_article_symbol(
        symbol="AAPL",
        headline="Apple unveils new chip",
        company_name="Apple Inc.",
        is_primary=True,
        ticker_count=1,
    )
    out2 = score_article_symbol(
        symbol="AAPL",
        headline="Apple unveils new chip",
        company_name="Apple Inc.",
        is_primary=True,
        ticker_count=1,
    )
    assert out1.score == out2.score
    assert 0.0 <= out1.score <= 1.0
    assert out1.components["version"] == RELEVANCE_VERSION


def test_company_name_match_dominates_irrelevant_ticker() -> None:
    high = score_article_symbol(
        symbol="AAPL",
        headline="Apple unveils new chip in Cupertino event",
        summary="Tim Cook announced ...",
        company_name="Apple Inc.",
        is_primary=True,
        ticker_count=1,
    )
    low = score_article_symbol(
        symbol="AAPL",
        headline="Tesla cuts prices across global lineup",
        summary="Tesla announced ...",
        company_name="Apple Inc.",
        is_primary=False,
        ticker_count=8,
    )
    assert high.score > low.score
    assert high.components["name_in_headline"] is True
    assert low.components["name_in_headline"] is False


def test_ticker_in_text_contributes_to_score() -> None:
    with_ticker = score_article_symbol(
        symbol="MSFT",
        headline="MSFT beats revenue expectations",
        company_name=None,
        is_primary=False,
        ticker_count=3,
    )
    without_ticker = score_article_symbol(
        symbol="MSFT",
        headline="Cloud providers report mixed results",
        company_name=None,
        is_primary=False,
        ticker_count=3,
    )
    assert with_ticker.score > without_ticker.score
    assert with_ticker.components["ticker_in_text"] is True
    assert without_ticker.components["ticker_in_text"] is False


def test_dollar_sign_ticker_variant_is_recognised() -> None:
    res = score_article_symbol(
        symbol="NVDA",
        headline="$NVDA hits an all-time high",
        company_name=None,
        is_primary=True,
        ticker_count=1,
    )
    assert res.components["ticker_in_text"] is True


def test_primary_bonus_applies_only_if_primary() -> None:
    primary = score_article_symbol(
        symbol="AAPL",
        headline="Apple posts strong earnings",
        company_name="Apple Inc.",
        is_primary=True,
        ticker_count=1,
    )
    secondary = score_article_symbol(
        symbol="AAPL",
        headline="Apple posts strong earnings",
        company_name="Apple Inc.",
        is_primary=False,
        ticker_count=1,
    )
    assert primary.score > secondary.score
    assert primary.components["is_primary"] is True
    assert secondary.components["is_primary"] is False


def test_multi_ticker_penalty_lowers_score_with_more_tickers() -> None:
    base = score_article_symbol(
        symbol="AAPL",
        headline="Apple posts strong earnings",
        company_name="Apple Inc.",
        is_primary=True,
        ticker_count=1,
    )
    noisy = score_article_symbol(
        symbol="AAPL",
        headline="Apple posts strong earnings",
        company_name="Apple Inc.",
        is_primary=True,
        ticker_count=20,
    )
    assert noisy.score < base.score
    assert noisy.components["multi_ticker_penalty"] > base.components["multi_ticker_penalty"]


def test_minimum_score_floor_applies() -> None:
    weights = RelevanceWeights(minimum_score=0.1)
    res = score_article_symbol(
        symbol="ZZZ",
        headline="No mention here at all",
        company_name=None,
        is_primary=False,
        ticker_count=15,
        weights=weights,
    )
    assert res.score >= 0.1
    assert res.score <= 1.0


def test_components_carry_full_audit_trail() -> None:
    res = score_article_symbol(
        symbol="AAPL",
        headline="Apple wins court ruling",
        company_name="Apple Inc.",
        is_primary=True,
        ticker_count=2,
    )
    expected_keys = {
        "version",
        "name_in_headline",
        "name_in_summary",
        "ticker_in_text",
        "is_primary",
        "ticker_count",
        "multi_ticker_penalty",
        "company_name_resolved",
        "weights",
    }
    assert set(res.components) >= expected_keys
    assert res.components["weights"]["name_in_headline"] == DEFAULT_WEIGHTS.name_in_headline


def test_corporate_suffix_stripping_allows_match() -> None:
    res = score_article_symbol(
        symbol="MSFT",
        headline="Microsoft signs cloud deal",
        company_name="Microsoft Corporation",
        is_primary=True,
        ticker_count=1,
    )
    assert res.components["name_in_headline"] is True


@pytest.mark.parametrize(
    "tcount",
    [1, 2, 5, 10, 25, 50],
)
def test_score_stays_in_unit_interval_for_various_ticker_counts(tcount: int) -> None:
    res = score_article_symbol(
        symbol="AAPL",
        headline="Apple unveils chip",
        company_name="Apple",
        is_primary=True,
        ticker_count=tcount,
    )
    assert 0.0 <= res.score <= 1.0

