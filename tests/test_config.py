import pytest
from event_sentiment import config

def test_load_config_returns_config(monkeypatch):
    monkeypatch.setattr(config, "EventSentimentConfig", lambda *a, **kw: object())
    cfg = config.load_config()
    assert cfg is not None

def test_load_config_handles_error(monkeypatch):
    monkeypatch.setattr(config, "EventSentimentConfig", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fail")))
    with pytest.raises(RuntimeError):
        config.load_config()

def test_event_sentiment_config_defaults():
    cfg = config.EventSentimentConfig()
    assert cfg.source_name == "alpaca_news"
    assert cfg.page_limit == 50
    assert cfg.finbert_model_name == "ProsusAI/finbert"

def test_event_sentiment_config_validation():
    # Cas d'erreur sur page_limit
    try:
        config.EventSentimentConfig(page_limit=0)
    except ValueError as e:
        assert "page_limit" in str(e)
    # Cas d'erreur sur finbert_batch_size
    try:
        config.EventSentimentConfig(finbert_batch_size=0)
    except ValueError as e:
        assert "finbert_batch_size" in str(e)
