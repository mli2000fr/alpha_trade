"""Régression S10.2 — `progress_callback` doit rester optionnel pour la pipeline.

Vérifie que :
- Si `progress_callback` n'est pas fourni à `EventSentimentPipeline`, la méthode
  `run` ne le transmet PAS au service d'ingestion (sinon les fakes minimaux des
  suites de tests échouent avec `TypeError`).
- Si `progress_callback` est fourni, il est bien forwardé au service.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest


class _StrictIngestionService:
    """Fake service qui REFUSE le kwarg `progress_callback` (signature minimale)."""

    def __init__(self, repository, config) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        start_utc,
        end_utc,
        symbols,
        symbol_start_overrides=None,
        symbol_resume_overrides=None,
        resume_checkpoints=True,
    ):
        self.calls.append(
            {
                "start_utc": start_utc,
                "end_utc": end_utc,
                "symbols": symbols,
                "resume_checkpoints": resume_checkpoints,
            }
        )
        return {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}


class _CapturingIngestionService:
    """Fake service qui ACCEPTE et capture le kwarg `progress_callback`."""

    def __init__(self, repository, config) -> None:
        self.captured_kwargs: dict[str, Any] | None = None

    def run(self, **kwargs):
        self.captured_kwargs = dict(kwargs)
        cb = kwargs.get("progress_callback")
        if callable(cb):
            cb({"current_symbol_index": 1, "current_symbol_total": 1, "current_symbol": "AAPL"})
        return {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}


class _Repo:
    def load_candidate_symbols(self):
        return ["AAPL"]

    def get_checkpoints(self, source, symbols):
        return {}

    def load_pending_articles(self, limit):
        return []

    def upsert_news_sentiment(self, records):
        return 0

    def upsert_macro_event_audit(self, records):
        return 0

    def load_feature_frames(self, start_date, end_date):
        import pandas as pd

        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def upsert_ticker_daily_features(self, records):
        return 0

    def upsert_sector_daily_features(self, records):
        return 0


def _make_config():
    return SimpleNamespace(
        finbert_model_name="ProsusAI/finbert",
        finbert_model_version="v1",
        finbert_batch_size=4,
        finbert_max_length=128,
        finbert_model_revision=None,
        macro_rule_version="v1",
        source_name="alpaca",
        initial_backfill_days=7,
        candidate_reactivation_backfill_days=30,
        checkpoint_overlap_minutes=30,
        sentiment_pending_limit=100,
        feature_history_buffer_days=30,
        feature_version="v1",
        feature_rolling_windows=(3, 7),
    )


@pytest.fixture
def patched_pipeline_module(monkeypatch):
    """Monkeypatche les services lourds du module pipeline."""
    from event_sentiment import pipeline

    class _NoOpFinBERT:
        model_fingerprint = "stub"

        def __init__(self, *args, **kwargs):
            pass

        def score_articles(self, articles):
            return []

    monkeypatch.setattr(pipeline, "FinBERTSentimentService", _NoOpFinBERT)
    return pipeline


def test_pipeline_does_not_pass_progress_callback_when_none(patched_pipeline_module, monkeypatch):
    pipeline = patched_pipeline_module
    monkeypatch.setattr(pipeline, "NewsIngestionService", _StrictIngestionService)

    pipe = pipeline.EventSentimentPipeline(_Repo(), _make_config())
    stats = pipe.run(end_utc=datetime(2026, 1, 1, tzinfo=UTC), symbols=["AAPL"])

    assert stats["resolved_symbols"] == 1
    # Le service strict aurait levé TypeError si progress_callback avait été passé.
    assert pipe.ingestion.calls and "progress_callback" not in pipe.ingestion.calls[0]


def test_pipeline_forwards_progress_callback_when_provided(patched_pipeline_module, monkeypatch):
    pipeline = patched_pipeline_module
    monkeypatch.setattr(pipeline, "NewsIngestionService", _CapturingIngestionService)

    received: list[dict[str, Any]] = []
    pipe = pipeline.EventSentimentPipeline(
        _Repo(), _make_config(), progress_callback=lambda payload: received.append(payload)
    )
    pipe.run(end_utc=datetime(2026, 1, 1, tzinfo=UTC), symbols=["AAPL"])

    assert pipe.ingestion.captured_kwargs is not None
    assert "progress_callback" in pipe.ingestion.captured_kwargs
    # Le callback de pipeline a été invoqué (au moins l'init ingestion + finbert + agrégation).
    assert received, "progress_callback aurait dû être invoqué au moins une fois"


