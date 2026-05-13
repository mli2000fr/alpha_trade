import logging
from datetime import date, datetime

import torch

from event_sentiment.models import NormalizedNewsArticle
from event_sentiment.scoring import HF_TOKEN_ENV_VAR, FinBERTSentimentService


class _FakeTensor:
    def __init__(self, values):
        self.values = values

    def to(self, device):
        return self


class _FakeTokenizer:
    def tokenize(self, text: str):
        return text.split()

    def __call__(self, texts, truncation, max_length, padding, return_tensors):
        return {
            "input_ids": _FakeTensor([[101, 102] for _ in texts]),
            "attention_mask": _FakeTensor([[1, 1] for _ in texts]),
        }


class _FakeModel:
    def __init__(self) -> None:
        self.current_device = "cuda"
        self.config = type("Config", (), {"id2label": {0: "positive", 1: "neutral", 2: "negative"}})()

    def to(self, device):
        self.current_device = device
        return self

    def eval(self):
        return self

    def __call__(self, **kwargs):
        if self.current_device == "cuda":
            raise RuntimeError("CUDA error: no kernel image is available for execution on the device")
        return type("Output", (), {"logits": torch.tensor([[3.0, 1.0, 0.2]])})()


def test_finbert_uses_headline_summary_when_content_missing() -> None:
    svc = FinBERTSentimentService(batch_size=1, max_length=64)
    article = NormalizedNewsArticle(
        article_id="alpaca:1",
        headline="Apple beats estimates",
        summary="Revenue was above consensus",
        content=None,
        source="Reuters",
        author=None,
        url=None,
        published_at_utc=datetime(2026, 1, 1),
        event_timestamp_utc=datetime(2026, 1, 1),
        event_timestamp_ny=datetime(2026, 1, 1),
        effective_trade_date=date(2026, 1, 2),
        market_session_tag="post_market",
    )
    text, strategy = svc._choose_text(article)
    assert strategy == "headline_summary"
    assert "Apple beats estimates" in text


def test_finbert_uses_content_when_summary_missing() -> None:
    svc = FinBERTSentimentService(batch_size=1, max_length=64)
    article = NormalizedNewsArticle(
        article_id="eodhd:1",
        headline="Apple beats estimates",
        summary=None,
        content="Full article body from EODHD",
        source="EODHD",
        author=None,
        url=None,
        published_at_utc=datetime(2026, 1, 1),
        event_timestamp_utc=datetime(2026, 1, 1),
        event_timestamp_ny=datetime(2026, 1, 1),
        effective_trade_date=date(2026, 1, 2),
        market_session_tag="post_market",
    )
    text, strategy = svc._choose_text(article)
    assert strategy == "content_full"
    assert "Apple beats estimates" in text
    assert "Full article body from EODHD" in text


def test_finbert_falls_back_to_cpu_after_cuda_failure(monkeypatch, caplog) -> None:
    svc = FinBERTSentimentService(batch_size=1, max_length=64)
    svc.tokenizer = _FakeTokenizer()
    svc.model = _FakeModel()
    svc.device = "cuda"
    svc.id2label = {0: "positive", 1: "neutral", 2: "negative"}

    monkeypatch.setattr(svc, "_ensure_model_loaded", lambda: None)
    monkeypatch.setattr(svc, "_get_torch_module", lambda: torch)

    def _fake_load_model_for_device(device: str, force_reload: bool = False) -> None:
        svc.device = device
        svc.model.to(device)

    monkeypatch.setattr(svc, "_load_model_for_device", _fake_load_model_for_device)

    article = NormalizedNewsArticle(
        article_id="alpaca:2",
        headline="Fed signals dovish pause",
        summary="Markets rally",
        content=None,
        source="Reuters",
        author=None,
        url=None,
        published_at_utc=datetime(2026, 1, 1),
        event_timestamp_utc=datetime(2026, 1, 1),
        event_timestamp_ny=datetime(2026, 1, 1),
        effective_trade_date=date(2026, 1, 2),
        market_session_tag="post_market",
    )

    caplog.set_level(logging.WARNING)
    records = svc.score_articles([article])

    assert len(records) == 1
    assert svc.device == "cpu"
    assert records[0].sentiment_label == "positive"
    assert "device=cpu (fallback after CUDA failure)" in caplog.text


# ---------------- Phase 4.1.c — fingerprint FinBERT ----------------

def test_fingerprint_stable_across_calls() -> None:
    svc = FinBERTSentimentService(batch_size=1, max_length=64)
    fp1 = svc.model_fingerprint
    fp2 = svc.model_fingerprint
    assert fp1 == fp2
    assert isinstance(fp1, str) and len(fp1) == 16


def test_fingerprint_changes_with_revision() -> None:
    svc_no_rev = FinBERTSentimentService(batch_size=1, max_length=64)
    svc_rev_a = FinBERTSentimentService(batch_size=1, max_length=64, model_revision="abc123")
    svc_rev_b = FinBERTSentimentService(batch_size=1, max_length=64, model_revision="def456")
    assert svc_no_rev.model_fingerprint != svc_rev_a.model_fingerprint
    assert svc_rev_a.model_fingerprint != svc_rev_b.model_fingerprint


def test_fingerprint_changes_with_model_name() -> None:
    svc1 = FinBERTSentimentService(model_name="ProsusAI/finbert", batch_size=1, max_length=64)
    svc2 = FinBERTSentimentService(model_name="other/finbert", batch_size=1, max_length=64)
    assert svc1.model_fingerprint != svc2.model_fingerprint


def test_score_articles_propagates_fingerprint(monkeypatch) -> None:
    svc = FinBERTSentimentService(batch_size=1, max_length=64, model_revision="v1.0")
    svc.tokenizer = _FakeTokenizer()
    svc.model = _FakeModel()
    svc.device = "cuda"
    svc.id2label = {0: "positive", 1: "neutral", 2: "negative"}

    monkeypatch.setattr(svc, "_ensure_model_loaded", lambda: None)
    monkeypatch.setattr(svc, "_get_torch_module", lambda: torch)

    def _fake_load_model_for_device(device: str, force_reload: bool = False) -> None:
        svc.device = device
        svc.model.to(device)

    monkeypatch.setattr(svc, "_load_model_for_device", _fake_load_model_for_device)

    article = NormalizedNewsArticle(
        article_id="alpaca:fp",
        headline="X",
        summary="Y",
        content=None,
        source="src",
        author=None,
        url=None,
        published_at_utc=datetime(2026, 1, 1),
        event_timestamp_utc=datetime(2026, 1, 1),
        event_timestamp_ny=datetime(2026, 1, 1),
        effective_trade_date=date(2026, 1, 2),
        market_session_tag="post_market",
    )
    records = svc.score_articles([article])
    assert records[0].model_fingerprint == svc.model_fingerprint
    assert records[0].model_fingerprint != ""


def test_load_model_for_device_passes_env_hf_token(monkeypatch) -> None:
    captured_calls: list[tuple[str, str, dict[str, object]]] = []

    class _RecordingTokenizer:
        @staticmethod
        def from_pretrained(model_name: str, **kwargs):
            captured_calls.append(("tokenizer", model_name, dict(kwargs)))
            return _FakeTokenizer()

    class _RecordingModel(_FakeModel):
        @staticmethod
        def from_pretrained(model_name: str, **kwargs):
            captured_calls.append(("model", model_name, dict(kwargs)))
            return _RecordingModel()

    monkeypatch.setenv(HF_TOKEN_ENV_VAR, "hf_test_token")

    svc = FinBERTSentimentService(batch_size=1, max_length=64, model_revision="rev-1")
    monkeypatch.setattr(svc, "_get_transformers_classes", lambda: (_RecordingModel, _RecordingTokenizer))

    svc._load_model_for_device("cpu")

    assert len(captured_calls) == 2
    assert captured_calls[0][0] == "tokenizer"
    assert captured_calls[1][0] == "model"
    assert captured_calls[0][1] == "ProsusAI/finbert"
    assert captured_calls[1][1] == "ProsusAI/finbert"
    assert captured_calls[0][2]["token"] == "hf_test_token"
    assert captured_calls[1][2]["token"] == "hf_test_token"
    assert captured_calls[0][2]["revision"] == "rev-1"
    assert captured_calls[1][2]["revision"] == "rev-1"


def test_load_model_for_device_omits_hf_token_when_env_missing(monkeypatch) -> None:
    captured_calls: list[tuple[str, str, dict[str, object]]] = []

    class _RecordingTokenizer:
        @staticmethod
        def from_pretrained(model_name: str, **kwargs):
            captured_calls.append(("tokenizer", model_name, dict(kwargs)))
            return _FakeTokenizer()

    class _RecordingModel(_FakeModel):
        @staticmethod
        def from_pretrained(model_name: str, **kwargs):
            captured_calls.append(("model", model_name, dict(kwargs)))
            return _RecordingModel()

    monkeypatch.delenv(HF_TOKEN_ENV_VAR, raising=False)

    svc = FinBERTSentimentService(batch_size=1, max_length=64)
    monkeypatch.setattr(svc, "_get_transformers_classes", lambda: (_RecordingModel, _RecordingTokenizer))

    svc._load_model_for_device("cpu")

    assert len(captured_calls) == 2
    assert "token" not in captured_calls[0][2]
    assert "token" not in captured_calls[1][2]

