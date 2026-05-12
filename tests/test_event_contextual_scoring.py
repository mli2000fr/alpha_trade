"""Tests Niveau 4 — re-scoring FinBERT contextualisé par couple (article, symbol).

Le scoring réel FinBERT est mocké : on remplace ``_infer_probabilities`` par
un stub déterministe pour ne charger ni ``torch`` ni ``transformers`` en
environnement de test.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from event_sentiment.models import ContextualSentimentRecord, NormalizedNewsArticle
from event_sentiment.scoring import (
    CONTEXTUAL_SCORING_VERSION,
    ContextualFinBERTScorer,
    _choose_contextual_text,
)


def _make_article(article_id: str = "a1", headline: str = "Apple beats earnings") -> NormalizedNewsArticle:
    now = datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc)
    return NormalizedNewsArticle(
        article_id=article_id,
        headline=headline,
        summary="Strong iPhone sales drive record quarter",
        content=None,
        source="Reuters",
        author=None,
        url=None,
        published_at_utc=now,
        event_timestamp_utc=now,
        event_timestamp_ny=now,
        effective_trade_date=date(2026, 1, 2),
        market_session_tag="regular",
        tickers=[],
        raw_payload={},
        is_major_event=0,
    )


def test_choose_contextual_text_with_company_name() -> None:
    article = _make_article()
    text, strategy = _choose_contextual_text(article, "AAPL", "Apple Inc.")
    assert strategy == "contextual_company"
    assert text.startswith("For Apple Inc. (AAPL):")
    assert "iPhone" in text


def test_choose_contextual_text_falls_back_to_symbol_only() -> None:
    article = _make_article()
    text, strategy = _choose_contextual_text(article, "aapl", None)
    assert strategy == "contextual_symbol_only"
    assert text.startswith("For AAPL:")


def test_choose_contextual_text_handles_empty_body() -> None:
    article = NormalizedNewsArticle(
        article_id="x",
        headline="",
        summary=None,
        content=None,
        source="",
        author=None,
        url=None,
        published_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        event_timestamp_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        event_timestamp_ny=datetime(2026, 1, 1, tzinfo=timezone.utc),
        effective_trade_date=date(2026, 1, 1),
        market_session_tag="regular",
    )
    text, strategy = _choose_contextual_text(article, "MSFT", None)
    assert strategy == "contextual_headline_only"
    assert text == "For MSFT: MSFT"


def test_choose_contextual_text_falls_back_to_content_when_summary_missing() -> None:
    now = datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc)
    article = NormalizedNewsArticle(
        article_id="x2",
        headline="Apple extends rally",
        summary=None,
        content="Full body from EODHD provider",
        source="EODHD",
        author=None,
        url=None,
        published_at_utc=now,
        event_timestamp_utc=now,
        event_timestamp_ny=now,
        effective_trade_date=date(2026, 1, 2),
        market_session_tag="regular",
    )
    text, strategy = _choose_contextual_text(article, "AAPL", None)
    assert strategy == "contextual_symbol_only"
    assert text.startswith("For AAPL:")
    assert "Full body from EODHD provider" in text


class _StubProbabilities:
    """Mime un tenseur `(batch, 3)` minimal : .tolist() + indexation + argmax."""

    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = rows

    def __getitem__(self, idx: int) -> "_StubProbabilities":
        return _StubProbabilities([self._rows[idx]])

    def tolist(self) -> list[float]:
        # Niveau "ligne" → renvoie 3 floats.
        return list(self._rows[0])


class _StubTorchModule:
    @staticmethod
    def argmax(prob_row: _StubProbabilities) -> SimpleNamespace:
        row = prob_row.tolist()
        max_index = max(range(len(row)), key=lambda i: row[i])
        return SimpleNamespace(item=lambda: max_index)


def _patch_scorer(monkeypatch: pytest.MonkeyPatch, scorer: ContextualFinBERTScorer, fixed_probs: list[float]) -> list[list[str]]:
    """Évite de charger FinBERT ; capture les batchs envoyés au tokenizer."""
    captured_batches: list[list[str]] = []

    scorer.model = object()  # type: ignore[assignment]
    scorer.tokenizer = object()  # type: ignore[assignment]
    scorer.device = "cpu"
    scorer.id2label = {0: "positive", 1: "neutral", 2: "negative"}

    def fake_ensure() -> None:
        return None

    def fake_torch() -> _StubTorchModule:
        return _StubTorchModule()

    def fake_infer(batch_texts: list[str]):
        captured_batches.append(list(batch_texts))
        rows = [list(fixed_probs) for _ in batch_texts]
        token_counts = [10 for _ in batch_texts]
        return _StubProbabilities(rows), token_counts

    monkeypatch.setattr(scorer, "_ensure_model_loaded", fake_ensure)
    monkeypatch.setattr(scorer, "_get_torch_module", fake_torch, raising=False)
    monkeypatch.setattr(scorer, "_infer_probabilities", fake_infer)
    return captured_batches


def test_score_pairs_returns_one_record_per_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    scorer = ContextualFinBERTScorer(batch_size=4, max_length=64)
    captured = _patch_scorer(monkeypatch, scorer, fixed_probs=[0.7, 0.2, 0.1])

    article = _make_article()
    pairs = [
        (article, "AAPL", "Apple Inc."),
        (article, "MSFT", "Microsoft Corp."),
        (article, "TSLA", None),
    ]

    records = scorer.score_pairs(pairs)
    assert len(records) == 3
    assert {r.symbol for r in records} == {"AAPL", "MSFT", "TSLA"}
    assert all(isinstance(r, ContextualSentimentRecord) for r in records)
    assert all(r.scoring_version == CONTEXTUAL_SCORING_VERSION for r in records)
    assert all(r.sentiment_label == "positive" for r in records)
    # Hash distinct par symbole car le prompt change.
    assert len({r.text_hash for r in records}) == 3
    # Les stratégies reflètent la présence ou non de company_name.
    strategies = {r.symbol: r.text_strategy for r in records}
    assert strategies["AAPL"] == "contextual_company"
    assert strategies["TSLA"] == "contextual_symbol_only"
    # Une seule passe d'inférence (3 paires < batch_size=4).
    assert len(captured) == 1
    assert len(captured[0]) == 3


def test_score_pairs_empty_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    scorer = ContextualFinBERTScorer()
    # Pas besoin de patch : le early-return doit court-circuiter.
    assert scorer.score_pairs([]) == []

